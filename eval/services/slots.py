"""정성평가 동시성 한도 두 단계.

1) Job-level slot — 동시에 진행 가능한 정성평가 요청(Job) 수
   in_flight = COUNT(EvalJob WHERE status='running')  (DB-truth)
   초과 시 QUEUED 로 대기, 진행 중 job 종료 시 promote.

2) Pair-level concurrency (Job 내부) — 한 Job 안에서 동시 처리되는 pair 수
   run_eval_job actor 안의 ThreadPoolExecutor max_workers 가 이 한도를 enforce.
   별도 Redis counter 없음 — Python OS thread 가 진실 소스라 leak/race 자체 부재.

운영 의미:
  - max_concurrent_eval_jobs: "동시 trigger 가능한 사용자 수"
  - pair_workers_per_job: "한 사용자 평가에서 동시 LLM 호출 수"
  - 시스템 전체 동시 LLM 호출 ≤ max_jobs × pair_workers
  - dramatiq worker thread 는 RUNNING 인 run_eval_job 수만큼 필요 (각 actor 가 thread 1개 점유)
"""
from __future__ import annotations

import redis
from django.conf import settings

from ..models import EvalConfig, EvalJob, EvalJobStatus


_KEY_MAX = "eval:max_concurrent_jobs"
_KEY_PAIR_WORKERS = "eval:pair_workers_per_job"

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
    """pair_workers_per_job 변경 — Redis 갱신 + DB 영구화. 1-16 범위.

    이 값은 다음에 시작되는 run_eval_job 의 ThreadPoolExecutor max_workers 로 사용.
    이미 RUNNING 인 job 의 thread pool 은 그 job 종료까지 기존 값 유지.
    """
    value = max(1, min(16, int(value)))
    r = _redis()
    r.set(_KEY_PAIR_WORKERS, value)
    cfg = EvalConfig.get_singleton()
    cfg.pair_workers_per_job = value
    cfg.save(update_fields=["pair_workers_per_job", "updated_at"])
    return value
