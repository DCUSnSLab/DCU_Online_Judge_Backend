"""정성평가 동시성 한도 두 단계.

1) Job-level slot — 동시에 진행 가능한 정성평가 요청(Job) 수
   in_flight = COUNT(EvalJob WHERE status='running')  (DB-truth)
   초과 시 QUEUED 로 대기, 진행 중 job 종료 시 promote.

2) Pair-level slot (Job 내부) — 한 Job 안에서 동시 처리되는 pair 수
   per-job Redis counter (Lua atomic) — run_eval_job 진입 시 0 으로 reset.
   acquire 실패 시 evaluate_pair 는 즉시 delay-requeue 하여 dramatiq thread 점유 방지.

운영 의미:
  - max_concurrent_eval_jobs: "동시 trigger 가능한 사용자 수"
  - pair_workers_per_job: "한 사용자 평가에서 동시 LLM 호출 수"
  - 시스템 전체 동시 LLM 호출 ≤ max_jobs × pair_workers (그리고 dramatiq thread)
"""
from __future__ import annotations

import redis
from django.conf import settings

from ..models import EvalConfig, EvalJob, EvalJobStatus


_KEY_MAX = "eval:max_concurrent_jobs"
_KEY_PAIR_WORKERS = "eval:pair_workers_per_job"
_KEY_JOB_INFLIGHT_PREFIX = "eval:job_pair_inflight:"  # + job_id

# Dramatiq broker 와 다른 DB 번호 사용 — 충돌 회피. cache(1), session(2), dramatiq(4) 와 분리.
_DB = 5

# Job 별 in-flight pair counter 의 atomic check-and-incr. 한도 초과면 0 반환.
_LUA_TRY_ACQUIRE_PAIR = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_n = tonumber(ARGV[1])
if cur < max_n then
  return redis.call('INCR', KEYS[1])
end
return 0
"""


def _redis():
    return redis.from_url(f"{settings.REDIS_URL}/{_DB}")


def _job_inflight_key(job_id) -> str:
    return f"{_KEY_JOB_INFLIGHT_PREFIX}{job_id}"


def get_max() -> int:
    """현재 동시 진행 한도. Redis 우선, 비어있으면 DB EvalConfig 에서 복원."""
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
    """현재 진행 중인 Job 수. DB 가 진실 소스라 별도 동기화/leak 처리 불필요."""
    return EvalJob.objects.filter(status=EvalJobStatus.RUNNING).count()


# ─────────────────────────────────────────────────────────────────────
# Pair-level (Job 내부) — 한 Job 안에서 동시 LLM 호출 수 제어
# ─────────────────────────────────────────────────────────────────────

def get_pair_workers() -> int:
    """한 Job 안에서 동시 처리 가능한 pair 수. Redis 우선, 비어있으면 DB 에서 복원."""
    r = _redis()
    raw = r.get(_KEY_PAIR_WORKERS)
    if raw is not None:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    cfg = EvalConfig.get_singleton()
    r.set(_KEY_PAIR_WORKERS, cfg.pair_workers_per_job)
    return cfg.pair_workers_per_job


def set_pair_workers(value: int) -> int:
    """pair_workers_per_job 변경 — Redis 갱신 + DB 영구화. 1-16 범위."""
    value = max(1, min(16, int(value)))
    r = _redis()
    r.set(_KEY_PAIR_WORKERS, value)
    cfg = EvalConfig.get_singleton()
    cfg.pair_workers_per_job = value
    cfg.save(update_fields=["pair_workers_per_job", "updated_at"])
    return value


def try_acquire_pair_slot(job_id) -> bool:
    """Job 의 pair-level 슬롯 atomic 점유. 한도 초과면 False (즉시 반환).

    호출자는 False 시 evaluate_pair 메시지를 delay-requeue 해서 dramatiq thread
    를 즉시 해제하는 게 좋다 (polling wait 으로 thread 점유하지 말 것).
    """
    r = _redis()
    result = r.eval(_LUA_TRY_ACQUIRE_PAIR, 1, _job_inflight_key(job_id), get_pair_workers())
    return int(result) > 0


def release_pair_slot(job_id):
    """pair-level 슬롯 반환. 음수 가드 포함."""
    r = _redis()
    key = _job_inflight_key(job_id)
    cur = r.decr(key)
    if cur < 0:
        r.set(key, 0)


def reset_job_inflight(job_id):
    """run_eval_job 진입 시 호출 — 이전 실패/leak 한 counter 정리.

    Job 별 카운터라 다른 job 에 영향 없음.
    """
    _redis().delete(_job_inflight_key(job_id))
