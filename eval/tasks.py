"""Dramatiq actors — LLM 호출.

운영 supervisord 의 dramatiq worker 는 default 큐만 처리하므로 actor 도 default 큐 사용
(별도 queue_name 지정 안 함). 동시성 한도는 worker process 수(MAX_WORKER_NUM)로 자연
스럽게 통제.

evaluate_pair: 1 (학생, 문제) 단위 정성평가 + AI 사용 평가 + EvalJob counter 증가
run_eval_job: contest 단위 orchestration — snapshot → evaluate_pair 다발 발행
"""
from __future__ import annotations

import logging

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
from .services.llm_client import LLMClient, LLMClientError
from .services.prompts import ai_usage as ai_usage_mod
from .services.prompts import llm as llm_mod
from .services.prompts import prompt as prompt_mod
from .services.prompts.models import EvalTask, FinalSubmissionRow, ProblemMeta
from .services.snapshot import snapshot_submissions

log = logging.getLogger(__name__)


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


def _bump_job_counter(job_id, *, success):
    """evaluate_pair 한 건이 끝날 때마다 부모 job 의 counter 증가.

    F() expression 으로 race-condition 회피. 모두 끝났으면 status=done 으로 마킹.
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

@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(time_limit=180_000, max_retries=1, max_age=86400_000))
def evaluate_pair(snapshot_id, force=False, job_id=None):
    """1 (학생, 문제) 평가. 정성 + AI 사용 두 호출.

    호출 실패도 row 는 생성 — error 필드에 사유 기록.
    완료 후 부모 job 의 n_done/n_failed counter 증가 + 모두 끝났으면 status=done.
    """
    snap = EvalSubmissionSnapshot.objects.select_related("submission").filter(id=snapshot_id).first()
    if not snap:
        log.error("evaluate_pair: snapshot %s not found", snapshot_id)
        _bump_job_counter(job_id, success=False)
        return

    has_qual = EvalQualitative.objects.filter(snapshot_id=snapshot_id).exists()
    has_ai = EvalAIUsage.objects.filter(snapshot_id=snapshot_id).exists()
    if has_qual and has_ai and not force:
        log.info("evaluate_pair: snapshot %s already evaluated, skip", snapshot_id)
        _bump_job_counter(job_id, success=True)
        return

    task = _build_task(snap)
    client = LLMClient()
    model_used = client.default_model
    had_error = False

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

    _bump_job_counter(job_id, success=not had_error)


@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(time_limit=3600_000, max_retries=0, max_age=86400_000))
def run_eval_job(job_id):
    """Job orchestration — snapshot 생성 + evaluate_pair 다발 발행.

    status=done 마킹은 evaluate_pair 들의 _bump_job_counter 가 모두 끝났음을 감지하면
    수행. 본 actor 는 발행까지만 책임.
    """
    try:
        job = EvalJob.objects.get(id=job_id)
    except EvalJob.DoesNotExist:
        log.error("run_eval_job: job %s not found", job_id)
        return

    if job.status not in (EvalJobStatus.QUEUED, EvalJobStatus.RUNNING):
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
            return

        for sid in pending:
            evaluate_pair.send(sid, job.force, job_id)

    except Exception as e:
        log.exception("run_eval_job failed job=%s", job_id)
        EvalJob.objects.filter(id=job_id).update(
            status=EvalJobStatus.FAILED, finished_at=timezone.now(), error=str(e)[:2000]
        )
        _emit(job_id, EvalJobEventType.ERROR, {"error": str(e)})
