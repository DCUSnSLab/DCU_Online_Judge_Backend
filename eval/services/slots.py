"""LLM 평가 동시성 제한.

DCUCODE Redis 의 db 5 에 in-flight counter / max 값 보관.
admin 이 GUI 로 변경하면 즉시 적용 (현재 in-flight 는 계속 실행, 새 actor 부터 한도 영향).

전략: Lua 스크립트로 한도 체크 + INCR 을 atomic 하게 처리.
대안인 "INCR → check → DECR" polling 은 race 사이 transient over-INCR 가 노출돼
admin UI 의 in_flight 표시가 들쭉날쭉해지는 문제가 있었음.
"""
from __future__ import annotations

import time

import redis
from django.conf import settings

from ..models import EvalConfig


_KEY_MAX = "eval:max_concurrent_jobs"
_KEY_INFLIGHT = "eval:in_flight"

# Dramatiq broker 와 다른 DB 번호 사용 — 충돌 회피. cache(1), session(2), dramatiq(4) 와 분리.
_DB = 5

# 한도 안에 있을 때만 INCR 하는 atomic check-and-incr. 한도 초과면 0 반환.
# Redis 단일 EVAL 실행 안에서 명령들이 atomic 하므로 transient over-INCR 가 발생하지 않음.
_LUA_TRY_ACQUIRE = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_n = tonumber(ARGV[1])
if cur < max_n then
  return redis.call('INCR', KEYS[1])
end
return 0
"""


def _redis():
    return redis.from_url(f"{settings.REDIS_URL}/{_DB}")


def get_max() -> int:
    """현재 동시 평가 한도. Redis 우선, 비어있으면 DB 의 EvalConfig 에서 가져와 캐싱."""
    r = _redis()
    raw = r.get(_KEY_MAX)
    if raw is not None:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    cfg = EvalConfig.get_singleton()
    r.set(_KEY_MAX, cfg.max_concurrent_eval_jobs)
    return cfg.max_concurrent_eval_jobs


def set_max(value: int) -> int:
    """슬롯 한도 변경 — Redis 갱신 + DB 영구화. 1-64 범위로 clamp."""
    value = max(1, min(64, int(value)))
    r = _redis()
    r.set(_KEY_MAX, value)
    cfg = EvalConfig.get_singleton()
    cfg.max_concurrent_eval_jobs = value
    cfg.save(update_fields=["max_concurrent_eval_jobs", "updated_at"])
    return value


def get_in_flight() -> int:
    r = _redis()
    raw = r.get(_KEY_INFLIGHT)
    try:
        return max(0, int(raw or 0))
    except ValueError:
        return 0


def reset_in_flight():
    """비상 시 / 서버 재시작 후 stuck counter 초기화."""
    _redis().set(_KEY_INFLIGHT, 0)


def acquire(timeout: float = 300.0, poll_interval: float = 0.5) -> bool:
    """슬롯 한 개 확보. 한도 초과면 short polling.

    반환:
        True  — slot 확보. 짝맞춰 release() 호출 필수.
        False — timeout 안에 못 확보.
    """
    r = _redis()
    deadline = time.monotonic() + timeout
    while True:
        n_max = get_max()
        result = r.eval(_LUA_TRY_ACQUIRE, 1, _KEY_INFLIGHT, n_max)
        if int(result) > 0:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


def release():
    """slot 반환. 음수로 떨어지지 않게 가드."""
    r = _redis()
    cur = r.decr(_KEY_INFLIGHT)
    if cur < 0:
        r.set(_KEY_INFLIGHT, 0)
