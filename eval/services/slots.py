"""정성평가 동시 진행 요청 한도.

슬롯의 의미: "동시에 진행 가능한 정성평가 요청(Job) 수".
한 사용자가 정성평가 버튼을 누르면 EvalJob 1개가 생성되고 슬롯 1개를 점유한다.
한도를 초과하면 새 요청은 QUEUED 로 대기하고, 진행 중 job 이 끝나는 즉시 promote 된다.

진실 소스(SoT): EvalJob.status.
  in_flight = COUNT(EvalJob WHERE status='running')
한도 max 만 Redis 에 캐시 (admin UI 갱신 즉시 반영용) + DB EvalConfig 에 영구화.

과거 모델: 슬롯 = LLM 동시 호출 수 (pair 단위). evaluate_pair 마다 INCR/DECR.
이 모델은 워커 SIGKILL 시 counter leak + race 사이 transient over-INCR 노이즈 + 운영자
멘탈모델 불일치 문제가 있었음. DB-truth 로 옮기면 모든 문제 자연 해소.
"""
from __future__ import annotations

import redis
from django.conf import settings

from ..models import EvalConfig, EvalJob, EvalJobStatus


_KEY_MAX = "eval:max_concurrent_jobs"

# Dramatiq broker 와 다른 DB 번호 사용 — 충돌 회피. cache(1), session(2), dramatiq(4) 와 분리.
_DB = 5


def _redis():
    return redis.from_url(f"{settings.REDIS_URL}/{_DB}")


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
