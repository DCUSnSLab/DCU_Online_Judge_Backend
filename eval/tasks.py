"""Dramatiq actors — LLM 호출.

운영 supervisord 의 dramatiq worker 는 default 큐만 처리하므로 actor 도 default 큐 사용
(별도 queue_name 지정 안 함). 동시성 한도는 worker process 수(MAX_WORKER_NUM)로 자연
스럽게 통제.

evaluate_pair: 1 (학생, 문제) 단위 정성평가 + AI 사용 평가 + EvalJob counter 증가
run_eval_job: contest 단위 orchestration — snapshot → evaluate_pair 다발 발행
finalize_stuck_job: 예상 완료시간 이후 호출되는 watchdog. counter 누락 시 강제 종결.
"""
from __future__ import annotations

import logging
import math

import dramatiq
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from utils.shortcuts import DRAMATIQ_WORKER_ARGS

from .models import (
    EvalAIUsage,
    EvalJob,
    EvalJobEvent,
    EvalJobEventType,
    EvalJobStatus,
    EvalQualitative,
    EvalSubmissionSnapshot,
)
from .services import scoreboard as sb_service
from .services import slots as slots_service
from .services.llm_client import LLMClient, LLMClientError
from .services.prompts import ai_usage as ai_usage_mod
from .services.prompts import llm as llm_mod
from .services.prompts import prompt as prompt_mod
from .services.prompts.models import EvalTask, FinalSubmissionRow, ProblemMeta
from .services.snapshot import snapshot_submissions

log = logging.getLogger(__name__)


# 단건 평가 actor time_limit (ms). 외부에서도 참조하므로 상수화.
PAIR_TIME_LIMIT_MS = 180_000


# ─────────────────────────────────────────────────────────────────────
# Job event helper
# ─────────────────────────────────────────────────────────────────────

def _emit(job_id, event_type, data=None):
    if not job_id:
        return
    try:
        EvalJobEvent.objects.create(job_id=job_id, event_type=event_type, data=data or {})
    except Exception as e:
        log.warning("emit failed (job=%s, type=%s): %s", job_id, event_type, e)


def _bump_job_counter(job_id, *, success, error_data=None):
    """evaluate_pair 한 건이 끝날 때마다 부모 job 의 counter 증가.

    F() expression 으로 race-condition 회피. 모두 끝났으면 status=done 으로 마킹.
    error_data 가 주어지면 동시에 ERROR 이벤트 기록 → UI 노출용.
    DONE 으로 전이되면 슬롯이 비므로 대기 중인 QUEUED job 을 promote 한다.
    """
    if not job_id:
        return
    with transaction.atomic():
        if success:
            EvalJob.objects.filter(id=job_id).update(n_done=F("n_done") + 1)
        else:
            EvalJob.objects.filter(id=job_id).update(n_failed=F("n_failed") + 1)
        # 완료 체크 — n_done + n_failed >= n_total 이면 done
        job = EvalJob.objects.filter(id=job_id).first()
        finished_now = False
        if (
            job
            and job.status == EvalJobStatus.RUNNING
            and (job.n_done + job.n_failed) >= job.n_total
        ):
            EvalJob.objects.filter(id=job_id, status=EvalJobStatus.RUNNING).update(
                status=EvalJobStatus.DONE, finished_at=timezone.now()
            )
            _emit(job_id, EvalJobEventType.DONE, {
                "n_done": job.n_done, "n_failed": job.n_failed, "n_total": job.n_total,
            })
            finished_now = True
    if job and not finished_now:
        _emit(job_id, EvalJobEventType.PROGRESS, {
            "n_done": job.n_done, "n_failed": job.n_failed, "n_total": job.n_total,
        })
    if error_data:
        _emit(job_id, EvalJobEventType.ERROR, error_data)
    if finished_now:
        try:
            promote_next_queued()
        except Exception:
            log.exception("promote_next_queued failed after job %s DONE", job_id)


def promote_next_queued():
    """슬롯 가용 시 가장 오래된 QUEUED job 을 RUNNING 으로 전이하고 run_eval_job 발행.

    한 번에 가용 슬롯 수만큼 promote 한다. SELECT FOR UPDATE 로 race 회피.
    호출 위치: trigger / cancel / job DONE/FAILED 직후.
    """
    promoted_ids = []
    max_n = slots_service.get_max()
    while True:
        with transaction.atomic():
            running = (
                EvalJob.objects.select_for_update()
                .filter(status=EvalJobStatus.RUNNING).count()
            )
            if running >= max_n:
                break
            nxt = (
                EvalJob.objects.select_for_update(skip_locked=True)
                .filter(status=EvalJobStatus.QUEUED)
                .order_by("enqueued_at").first()
            )
            if not nxt:
                break
            EvalJob.objects.filter(id=nxt.id, status=EvalJobStatus.QUEUED).update(
                status=EvalJobStatus.RUNNING, started_at=timezone.now()
            )
        # 트랜잭션 밖에서 actor 발행
        try:
            run_eval_job.send(nxt.id)
        except Exception as e:
            log.exception("promote_next_queued: dramatiq send failed job=%s: %s", nxt.id, e)
            _emit(nxt.id, EvalJobEventType.WARN, {"message": f"dramatiq dispatch failed: {e}"})
        promoted_ids.append(nxt.id)
    return promoted_ids


def _is_job_active(job_id):
    """Actor 진입 시 cancellation 체크용. job_id 가 None 이면 True (단발 호출 허용)."""
    if not job_id:
        return True
    status = EvalJob.objects.filter(id=job_id).values_list("status", flat=True).first()
    return status in EvalJobStatus.ACTIVE


# ─────────────────────────────────────────────────────────────────────
# Build EvalTask from DB snapshot + problem
# ─────────────────────────────────────────────────────────────────────

def _build_task(snapshot):
    from problem.models import Problem
    p = Problem.objects.get(id=snapshot.problem_id)
    pmeta = ProblemMeta(
        label=p._id,
        title=p.title,
        description=p.description or "",
        input_description=p.input_description or "",
        output_description=p.output_description or "",
        samples=p.samples or [],
        hint=p.hint,
        languages=p.languages or [],
        time_limit=p.time_limit,
        memory_limit=p.memory_limit,
        difficulty=p.difficulty,
        total_score=p.total_score or 0,
    )
    from submission.models import Submission
    sub = Submission.objects.filter(id=snapshot.submission_id).first()
    stat = (sub.statistic_info if sub else {}) or {}
    row = FinalSubmissionRow(
        submission_id=snapshot.submission_id,
        user_id=snapshot.user_id,
        username=snapshot.submission.username if sub is None else sub.username,
        problem_label=p._id,
        problem_id=p.id,
        language=snapshot.language,
        result=sub.result if sub else -1,
        result_label=sb_service.result_label(sub.result) if sub else "",
        score=stat.get("score"),
        time_cost_ms=stat.get("time_cost"),
        memory_cost_kb=stat.get("memory_cost"),
        create_time=sub.create_time.isoformat() if sub and sub.create_time else None,
    )
    return EvalTask(problem=pmeta, submission=row, code=snapshot.code)


# ─────────────────────────────────────────────────────────────────────
# Actors (default queue — supervisord rundramatiq 가 그대로 받음)
# ─────────────────────────────────────────────────────────────────────

@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(time_limit=PAIR_TIME_LIMIT_MS, max_retries=1, max_age=86400_000))
def evaluate_pair(snapshot_id, force=False, job_id=None):
    """1 (학생, 문제) 평가. 정성 + AI 사용 두 호출.

    호출 실패도 row 는 생성 — error 필드에 사유 기록.
    완료 후 부모 job 의 n_done/n_failed counter 증가 + 모두 끝났으면 status=done.

    모든 경로(정상/캐치된 LLM 에러/TimeLimit/Unknown)에서 counter 증가가 보장되도록
    최외곽 try/except/finally 로 감싼다. counter 누락 → 영구 RUNNING stuck 방지.
    """
    # Cancellation pre-check — job 이 CANCELLED/FAILED/DONE 이면 메시지 폐기.
    # counter 도 건드리지 않음 (cancel 시 별도 정리됨).
    if not _is_job_active(job_id):
        log.info("evaluate_pair: job %s not active, skip snapshot %s", job_id, snapshot_id)
        return

    success = False
    error_data = None
    try:
        snap = EvalSubmissionSnapshot.objects.select_related("submission").filter(id=snapshot_id).first()
        if not snap:
            log.error("evaluate_pair: snapshot %s not found", snapshot_id)
            error_data = {"snapshot_id": snapshot_id, "reason": "snapshot not found"}
            return  # finally bumps counter as failure

        has_qual = EvalQualitative.objects.filter(snapshot_id=snapshot_id).exists()
        has_ai = EvalAIUsage.objects.filter(snapshot_id=snapshot_id).exists()
        if has_qual and has_ai and not force:
            log.info("evaluate_pair: snapshot %s already evaluated, skip", snapshot_id)
            success = True
            return

        # 동시성 한도는 부모 Job 단위로 promote_next_queued 가 제어 — pair 단위 lock 없음.
        # 워커 thread 수가 곧 한 Job 내부 병렬 처리 상한.

        task = _build_task(snap)
        client = LLMClient()
        model_used = client.default_model
        had_error = False
        pair_errors = []

        # 정성평가
        try:
            parsed, raw, latency = llm_mod.call_with_retry(
                client,
                prompt_mod.build_messages(task),
                parser=lambda t: llm_mod.parse_response(t, total_score=task.problem.total_score),
                model=None,
                temperature=0.2,
                max_tokens=2048,
                retries=1,
            )
            EvalQualitative.objects.update_or_create(
                snapshot=snap,
                defaults=dict(
                    scores=parsed["scores"], comments=parsed["comments"],
                    overall=parsed["overall"], suggested_partial_score=parsed["suggested_partial_score"],
                    summary=parsed["summary"], model_used=model_used, llm_latency_ms=latency,
                    error="", raw_response=raw[:50000], recomputed=parsed.get("recomputed") or {},
                ),
            )
        except (llm_mod.LLMResponseError, LLMClientError) as e:
            had_error = True
            pair_errors.append(f"qualitative: {e}")
            log.warning("evaluate_pair qualitative failed snap=%s: %s", snapshot_id, e)
            EvalQualitative.objects.update_or_create(
                snapshot=snap,
                defaults=dict(
                    scores={}, comments={}, overall=None, suggested_partial_score=None, summary="",
                    model_used=model_used, llm_latency_ms=None, error=str(e)[:5000],
                    raw_response=(getattr(e, "last_raw", "") or "")[:50000], recomputed={},
                ),
            )

        # AI 사용 평가
        try:
            parsed_ai, raw_ai, latency_ai = llm_mod.call_with_retry(
                client,
                ai_usage_mod.build_messages(task),
                parser=ai_usage_mod.parse_response,
                model=None,
                temperature=0.2,
                max_tokens=1024,
                retries=1,
            )
            EvalAIUsage.objects.update_or_create(
                snapshot=snap,
                defaults=dict(
                    likelihood_score=parsed_ai["likelihood_score"],
                    confidence=parsed_ai["confidence"],
                    signals=[s.__dict__ for s in parsed_ai["signals"]],
                    counter_signals=parsed_ai["counter_signals"],
                    summary=parsed_ai["summary"], disclaimer=parsed_ai["disclaimer"],
                    model_used=model_used, llm_latency_ms=latency_ai,
                    error="", raw_response=raw_ai[:50000],
                ),
            )
        except (llm_mod.LLMResponseError, LLMClientError) as e:
            had_error = True
            pair_errors.append(f"ai_usage: {e}")
            log.warning("evaluate_pair ai_usage failed snap=%s: %s", snapshot_id, e)
            EvalAIUsage.objects.update_or_create(
                snapshot=snap,
                defaults=dict(
                    likelihood_score=None, confidence="low", signals=[], counter_signals=[],
                    summary="", disclaimer=ai_usage_mod.DISCLAIMER_TEXT, model_used=model_used,
                    llm_latency_ms=None, error=str(e)[:5000],
                    raw_response=(getattr(e, "last_raw", "") or "")[:50000],
                ),
            )

        success = not had_error
        if had_error:
            # 캐치된 LLM 에러 — UI 노출용 이벤트.
            error_data = {
                "snapshot_id": snapshot_id,
                "reason": "llm_error",
                "errors": pair_errors,
            }
    except Exception as e:
        # TimeLimitExceeded / 네트워크 / DB / 기타 — counter 누락 방지를 위해 반드시 catch.
        # dramatiq retry 와 무관하게 한 번에 failure 로 종결한다.
        success = False
        log.exception("evaluate_pair unhandled exception snap=%s job=%s", snapshot_id, job_id)
        error_data = {
            "snapshot_id": snapshot_id,
            "reason": "unhandled_exception",
            "exc_type": type(e).__name__,
            "exc_message": str(e)[:1000],
        }
    finally:
        _bump_job_counter(job_id, success=success, error_data=error_data)


@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(time_limit=3600_000, max_retries=0, max_age=86400_000))
def run_eval_job(job_id):
    """Job orchestration — snapshot 생성 + evaluate_pair 다발 발행.

    status=done 마킹은 evaluate_pair 들의 _bump_job_counter 가 모두 끝났음을 감지하면
    수행. 본 actor 는 발행 + watchdog 예약까지 책임.
    """
    try:
        job = EvalJob.objects.get(id=job_id)
    except EvalJob.DoesNotExist:
        log.error("run_eval_job: job %s not found", job_id)
        return

    if job.status not in EvalJobStatus.ACTIVE:
        log.warning("run_eval_job: job %s status=%s, skip", job_id, job.status)
        return

    EvalJob.objects.filter(id=job_id).update(
        status=EvalJobStatus.RUNNING, started_at=timezone.now()
    )
    _emit(job_id, EvalJobEventType.STARTED, {"contest_id": job.contest_id})

    try:
        _emit(job_id, EvalJobEventType.STAGE, {"name": "snapshot"})
        snap_ids = snapshot_submissions(job.contest_id, force=job.force)

        if not job.force:
            already = set(
                EvalQualitative.objects.filter(snapshot_id__in=snap_ids).values_list("snapshot_id", flat=True)
            ) & set(
                EvalAIUsage.objects.filter(snapshot_id__in=snap_ids).values_list("snapshot_id", flat=True)
            )
            pending = [sid for sid in snap_ids if sid not in already]
        else:
            pending = list(snap_ids)

        # n_total 먼저 셋팅 — evaluate_pair 가 counter 증가 시 비교 기준이 됨
        EvalJob.objects.filter(id=job_id).update(n_total=len(pending), n_done=0, n_failed=0)
        _emit(job_id, EvalJobEventType.STAGE, {"name": "evaluate", "n_total": len(pending)})

        if not pending:
            # 아무 것도 평가할 게 없으면 즉시 done
            EvalJob.objects.filter(id=job_id, status=EvalJobStatus.RUNNING).update(
                status=EvalJobStatus.DONE, finished_at=timezone.now()
            )
            _emit(job_id, EvalJobEventType.DONE, {"skipped": True, "n_total": 0})
            promote_next_queued()
            return

        for sid in pending:
            evaluate_pair.send(sid, job.force, job_id)

        # Watchdog 예약 — 메시지가 통째로 유실되어도 일정 시간 후 강제 종결.
        # 예상 완료시간 = ceil(n_total / max_concurrent) × time_limit, 거기에 ×2 safety + 10분 floor.
        max_concurrent = max(slots_service.get_max(), 1)
        expected_ms = math.ceil(len(pending) / max_concurrent) * PAIR_TIME_LIMIT_MS
        watchdog_delay_ms = max(expected_ms * 2, 600_000)
        try:
            finalize_stuck_job.send_with_options(args=(job_id,), delay=watchdog_delay_ms)
        except Exception as e:
            log.warning("run_eval_job: watchdog schedule failed job=%s: %s", job_id, e)

    except Exception as e:
        log.exception("run_eval_job failed job=%s", job_id)
        EvalJob.objects.filter(id=job_id).update(
            status=EvalJobStatus.FAILED, finished_at=timezone.now(), error=str(e)[:2000]
        )
        _emit(job_id, EvalJobEventType.ERROR, {"error": str(e)})
        promote_next_queued()


@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(time_limit=60_000, max_retries=0, max_age=86400_000 * 7))
def finalize_stuck_job(job_id):
    """Watchdog — run_eval_job 이 예상 완료시간 + 마진 후 발행.

    Job 이 아직 active 인데 counter 가 미달이면:
    - counter 가 채워졌는데 done 마킹 누락된 경우: DONE 으로 보정
    - counter 가 실제로 미달인 경우: 누락분을 n_failed 로 보정 후 FAILED 마킹

    이미 done/failed/cancelled 면 no-op.
    """
    job = EvalJob.objects.filter(id=job_id).first()
    if not job:
        return
    if job.status not in EvalJobStatus.ACTIVE:
        return

    missing = job.n_total - (job.n_done + job.n_failed)
    now = timezone.now()
    if missing <= 0:
        # counter 는 다 찼는데 done 마킹이 빠진 케이스 — DONE 으로 보정
        EvalJob.objects.filter(id=job_id, status__in=EvalJobStatus.ACTIVE).update(
            status=EvalJobStatus.DONE, finished_at=now,
        )
        _emit(job_id, EvalJobEventType.DONE, {
            "note": "watchdog finalized (counter complete)",
            "n_done": job.n_done, "n_failed": job.n_failed, "n_total": job.n_total,
        })
        promote_next_queued()
        return

    # 진짜 메시지 유실 — 누락분을 n_failed 에 가산하고 FAILED 마킹
    reason = (
        f"watchdog: {missing} pair(s) lost — worker exception or message dropped. "
        f"n_total={job.n_total} n_done={job.n_done} n_failed={job.n_failed}"
    )
    EvalJob.objects.filter(id=job_id, status__in=EvalJobStatus.ACTIVE).update(
        status=EvalJobStatus.FAILED, finished_at=now,
        n_failed=F("n_failed") + missing,
        error=reason[:2000],
    )
    _emit(job_id, EvalJobEventType.ERROR, {
        "reason": "watchdog_timeout",
        "missing": missing,
        "n_done": job.n_done, "n_failed": job.n_failed, "n_total": job.n_total,
    })
    promote_next_queued()
