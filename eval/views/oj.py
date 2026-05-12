"""
/api/eval/ read + write endpoints.

권한:
- 메타 endpoint (/years, /semesters, /lectures, /queue, /jobs) → has_any_score_permission
- contest 단위 endpoint (scoreboard, cell, eval-status, trigger) → has_lecture_score_permission
"""
import json
from urllib.parse import quote

from django.db import IntegrityError, connection, transaction
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from contest.models import Contest

from ..models import (
    EvalJob,
    EvalJobEvent,
    EvalJobEventType,
    EvalJobRequester,
    EvalJobStatus,
)
from ..services import export as export_service
from ..services import scoreboard as sb_service
from ..services.permissions import has_any_score_permission, has_lecture_score_permission


def _err(msg, status):
    return JsonResponse({"detail": msg}, status=status)


def _ok(payload):
    return JsonResponse(payload, safe=False)


def _require_login(request):
    if not request.user.is_authenticated:
        return _err("Login required", 401)
    return None


def _require_any_score_perm(request):
    err = _require_login(request)
    if err:
        return err
    if not has_any_score_permission(request.user):
        return _err("Forbidden", 403)
    return None


def _require_lecture_perm(request, lecture_id):
    err = _require_login(request)
    if err:
        return err
    if not has_lecture_score_permission(request.user, lecture_id):
        return _err("Forbidden", 403)
    return None


# ─────────────────────────────────────────────────────────────────────
# Navigation
# ─────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class YearsView(View):
    def get(self, request):
        err = _require_any_score_perm(request)
        if err:
            return err
        with connection.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT year FROM lecture WHERE status = true ORDER BY year DESC"
            )
            years = [row[0] for row in cur.fetchall()]
        return _ok(years)


@method_decorator(csrf_exempt, name="dispatch")
class SemestersView(View):
    def get(self, request, year):
        err = _require_any_score_perm(request)
        if err:
            return err
        with connection.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT semester FROM lecture WHERE year = %s AND status = true ORDER BY semester",
                (year,),
            )
            semesters = [row[0] for row in cur.fetchall()]
        return _ok(semesters)


@method_decorator(csrf_exempt, name="dispatch")
class LecturesView(View):
    def get(self, request, year, semester):
        err = _require_any_score_perm(request)
        if err:
            return err
        from lecture.models import Lecture
        rows = [
            {"id": l.id, "title": l.title, "year": l.year, "semester": l.semester}
            for l in Lecture.objects.filter(year=year, semester=semester, status=True).order_by("title")
        ]
        return _ok(rows)


@method_decorator(csrf_exempt, name="dispatch")
class LectureDetailView(View):
    def get(self, request, lecture_id):
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        data = sb_service.get_lecture_dict(lecture_id)
        if data is None:
            return _err("lecture not found", 404)
        return _ok(data)


@method_decorator(csrf_exempt, name="dispatch")
class LectureContestsView(View):
    def get(self, request, lecture_id):
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        return _ok(sb_service.list_lecture_contests(lecture_id))


# ─────────────────────────────────────────────────────────────────────
# Scoreboard / Detail / Eval status
# ─────────────────────────────────────────────────────────────────────

def _resolve_lecture_for_contest(contest_id):
    try:
        return Contest.objects.values_list("lecture_id", flat=True).get(id=contest_id)
    except Contest.DoesNotExist:
        return None


@method_decorator(csrf_exempt, name="dispatch")
class ContestScoreboardView(View):
    def get(self, request, contest_id):
        lecture_id = _resolve_lecture_for_contest(contest_id)
        if lecture_id is None:
            return _err("contest not found", 404)
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        data, error = sb_service.build_scoreboard(contest_id)
        if error:
            return _err(error, 404)
        return _ok(data)


@method_decorator(csrf_exempt, name="dispatch")
class CellDetailView(View):
    def get(self, request, contest_id, user_id, problem_id):
        lecture_id = _resolve_lecture_for_contest(contest_id)
        if lecture_id is None:
            return _err("contest not found", 404)
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        data, error = sb_service.get_cell_detail(contest_id, user_id, problem_id)
        if error:
            return _err(error, 404)
        return _ok(data)


@method_decorator(csrf_exempt, name="dispatch")
class EvalStatusView(View):
    def get(self, request, contest_id):
        lecture_id = _resolve_lecture_for_contest(contest_id)
        if lecture_id is None:
            return _err("contest not found", 404)
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        return _ok(sb_service.get_eval_status(contest_id))


# ─────────────────────────────────────────────────────────────────────
# Write: trigger / queue / job detail
# ─────────────────────────────────────────────────────────────────────

def _job_to_dict(job):
    # select_related("lecture", "contest") 가정 — N+1 회피
    return {
        "job_id": str(job.id),
        "lecture_id": job.lecture_id,
        "lecture_title": job.lecture.title if job.lecture_id else None,
        "contest_id": job.contest_id,
        "contest_title": job.contest.title if job.contest_id else None,
        "contest_type": job.contest.lecture_contest_type if job.contest_id else None,
        "status": job.status,
        "force": job.force,
        "n_total": job.n_total,
        "n_done": job.n_done,
        "n_failed": job.n_failed,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        "error": job.error or None,
        "requester_ids": list(job.requesters.values_list("user_id", flat=True)),
    }


@method_decorator(csrf_exempt, name="dispatch")
class QualitativeEvalTriggerView(View):
    """POST /api/eval/contests/<cid>/qualitative-eval

    body: {"force": bool}
    response: {job_id, n_total, n_to_run, joined_existing, queue_position, slots_in_use, slots_total}
    """

    def post(self, request, contest_id):
        lecture_id = _resolve_lecture_for_contest(contest_id)
        if lecture_id is None:
            return _err("contest not found", 404)
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return _err("invalid JSON body", 400)
        force = bool(body.get("force"))

        # 같은 contest 에 active job 이 있는지 확인 → 합류 vs 신규 생성
        joined = False
        try:
            with transaction.atomic():
                job = EvalJob.objects.create(
                    lecture_id=lecture_id,
                    contest_id=contest_id,
                    status=EvalJobStatus.QUEUED,
                    force=force,
                )
                EvalJobRequester.objects.create(job=job, user=request.user)
        except IntegrityError:
            # partial unique constraint 충돌 → 기존 active job 에 합류
            job = EvalJob.objects.filter(
                contest_id=contest_id, status__in=EvalJobStatus.ACTIVE
            ).first()
            if job is None:
                return _err("conflict but no active job (race?)", 500)
            EvalJobRequester.objects.get_or_create(job=job, user=request.user)
            joined = True

        # 신규 job 만 actor 발행 (합류는 이미 발행됨)
        if not joined:
            # 지연 import — Django 앱 로드 순서 의존
            from ..tasks import run_eval_job
            try:
                run_eval_job.send(job.id)
            except Exception as e:
                # Dramatiq broker 미가동 시에도 row 는 보존 — 운영팀이 워커 띄우면 재시도
                EvalJobEvent.objects.create(
                    job=job, event_type=EvalJobEventType.WARN,
                    data={"message": f"dramatiq dispatch failed: {e}"},
                )

        # 대기열 위치는 단순화: queued job 의 enqueued_at 순위
        queue_position = None
        if job.status == EvalJobStatus.QUEUED:
            queue_position = EvalJob.objects.filter(
                status=EvalJobStatus.QUEUED, enqueued_at__lte=job.enqueued_at,
            ).count()
        from ..services import slots as slots_service
        slots_in_use = slots_service.get_in_flight()
        slots_total = slots_service.get_max()

        return _ok({
            "job_id": str(job.id),
            "n_total": job.n_total,
            "n_already_evaluated": 0,  # 정확한 값은 actor 실행 후 갱신
            "n_to_run": job.n_total,
            "joined_existing": joined,
            "queue_position": queue_position,
            "slots_in_use": slots_in_use,
            "slots_total": slots_total,
        })


@method_decorator(csrf_exempt, name="dispatch")
class QueueView(View):
    """GET /api/eval/queue — 활성 job 스냅샷."""

    def get(self, request):
        err = _require_any_score_perm(request)
        if err:
            return err
        # select_related: 응답마다 lecture/contest title 포함 — N+1 회피
        running_qs = (
            EvalJob.objects.filter(status=EvalJobStatus.RUNNING)
            .select_related("lecture", "contest")
            .prefetch_related("requesters")
        )
        pending_qs = (
            EvalJob.objects.filter(status=EvalJobStatus.QUEUED)
            .select_related("lecture", "contest")
            .prefetch_related("requesters")
            .order_by("enqueued_at")
        )
        running = [_job_to_dict(j) for j in running_qs]
        pending = []
        for i, j in enumerate(pending_qs, 1):
            d = _job_to_dict(j)
            d["queue_position"] = i
            pending.append(d)
        # slots_total 은 admin 설정값
        from ..services import slots as slots_service
        return _ok({
            "slots_total": slots_service.get_max(),
            "slots_in_use": slots_service.get_in_flight(),
            "queue_size": len(pending),
            "running": running,
            "pending": pending,
        })


@method_decorator(csrf_exempt, name="dispatch")
class JobDetailView(View):
    """GET /api/eval/jobs/<jid> — Job 메타 + 최근 이벤트."""

    def get(self, request, job_id):
        err = _require_any_score_perm(request)
        if err:
            return err
        try:
            job = (
                EvalJob.objects
                .select_related("lecture", "contest")
                .prefetch_related("requesters")
                .get(id=job_id)
            )
        except (EvalJob.DoesNotExist, ValueError):
            return _err("job not found", 404)
        events = list(
            EvalJobEvent.objects.filter(job=job).order_by("-ts").values("event_type", "data", "ts")[:50]
        )
        for e in events:
            e["ts"] = e["ts"].isoformat()
        data = _job_to_dict(job)
        data["events"] = events
        return _ok(data)


# ─────────────────────────────────────────────────────────────────────
# Score Export (CSV / XLSX)
# ─────────────────────────────────────────────────────────────────────

def _safe_filename(name):
    return quote((name or "export").encode("utf-8"), safe="")


def _export_response(stem, content, content_type, ext):
    resp = HttpResponse(content, content_type=content_type)
    resp["Content-Disposition"] = f"attachment; filename*=UTF-8''{_safe_filename(stem)}.{ext}"
    return resp


def _parse_json_param(request, name):
    """query 의 JSON 인코딩된 값 파싱. 비어있거나 잘못된 JSON 이면 None."""
    raw = request.GET.get(name)
    if not raw:
        return None
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else None
    except (ValueError, TypeError):
        return None


@method_decorator(csrf_exempt, name="dispatch")
class ContestExportView(View):
    def get(self, request, contest_id):
        lecture_id = _resolve_lecture_for_contest(contest_id)
        if lecture_id is None:
            return _err("contest not found", 404)
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        fmt = (request.GET.get("format") or "xlsx").lower()
        if fmt not in ("csv", "xlsx"):
            return _err("unsupported format", 400)
        weights = _parse_json_param(request, "weights")
        scales = _parse_json_param(request, "scales")
        stem, content, content_type = export_service.build_contest_export(
            contest_id, fmt, weights=weights, scales=scales
        )
        if stem is None:
            return _err(content, 404 if "not found" in (content or "").lower() else 400)
        return _export_response(stem, content, content_type, fmt)


@method_decorator(csrf_exempt, name="dispatch")
class LectureExportView(View):
    def get(self, request, lecture_id):
        err = _require_lecture_perm(request, lecture_id)
        if err:
            return err
        fmt = (request.GET.get("format") or "xlsx").lower()
        if fmt not in ("csv", "xlsx"):
            return _err("unsupported format", 400)
        weights = _parse_json_param(request, "weights")
        scales = _parse_json_param(request, "scales")
        stem, content, content_type = export_service.build_lecture_export(
            lecture_id, fmt, weights=weights, scales=scales
        )
        if stem is None:
            return _err(content, 404 if "not found" in (content or "").lower() else 400)
        return _export_response(stem, content, content_type, fmt)
