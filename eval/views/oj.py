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
from django.utils import timezone
from django.utils.dateparse import parse_datetime
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

_VALID_TRIGGER_MODES = ("pending", "all", "failed")


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
        "mode": job.mode,
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

    body:
      {"mode": "pending"|"all"|"failed"}  (권장)
      {"force": bool}                      (legacy 호환 — mode 미지정 시 사용)
        force=True → mode=all, force=False → mode=pending
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

        raw_mode = body.get("mode")
        if raw_mode is not None:
            mode = str(raw_mode).strip().lower()
            if mode not in _VALID_TRIGGER_MODES:
                return _err(f"invalid mode (allowed: {', '.join(_VALID_TRIGGER_MODES)})", 400)
        else:
            mode = "all" if bool(body.get("force")) else "pending"
        force = (mode != "pending")  # legacy 필드는 mode 와 동기화해 채움

        # 같은 contest 에 active job 이 있는지 확인 → 합류 vs 신규 생성
        joined = False
        try:
            with transaction.atomic():
                job = EvalJob.objects.create(
                    lecture_id=lecture_id,
                    contest_id=contest_id,
                    status=EvalJobStatus.QUEUED,
                    force=force,
                    mode=mode,
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

        # 신규 job 은 dispatcher 가 슬롯 가용 시 promote (RUNNING 전이 + run_eval_job.send).
        # 한도 초과 상태면 QUEUED 그대로 유지되고 다른 job 종료 시 자동 promote 됨.
        # (합류는 기존 RUNNING/QUEUED job 의 흐름을 그대로 따른다.)
        if not joined:
            from ..tasks import promote_next_queued
            try:
                promote_next_queued()
            except Exception as e:
                EvalJobEvent.objects.create(
                    job=job, event_type=EvalJobEventType.WARN,
                    data={"message": f"promote failed: {e}"},
                )

        # promote 결과 job 이 RUNNING 으로 전이됐을 수 있으므로 status 재조회
        job.refresh_from_db()
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
            "mode": job.mode,
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


_VALID_EVENT_TYPES = {v for v, _ in EvalJobEventType.CHOICES}


def _parse_event_query(request):
    """JobDetailView 쿼리스트링 파싱. 잘못된 값은 조용히 무시."""
    try:
        limit = int(request.GET.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    since_raw = (request.GET.get("since") or "").strip()
    since_dt = parse_datetime(since_raw) if since_raw else None

    types_raw = (request.GET.get("types") or "").strip()
    types = None
    if types_raw:
        wanted = {t.strip().lower() for t in types_raw.split(",") if t.strip()}
        valid = wanted & _VALID_EVENT_TYPES
        types = list(valid) if valid else None
    return limit, since_dt, types


@method_decorator(csrf_exempt, name="dispatch")
class JobDetailView(View):
    """GET /api/eval/jobs/<jid> — Job 메타 + 이벤트.

    쿼리 파라미터:
      limit=<1..500> (default 50)
      since=<ISO8601> — 이 시각 이후(>) 이벤트만 (incremental 폴링용)
      types=<csv> — event_type 화이트리스트 필터 (warn,error 등)
    """

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

        limit, since_dt, types = _parse_event_query(request)
        qs = EvalJobEvent.objects.filter(job=job)
        if since_dt is not None:
            qs = qs.filter(ts__gt=since_dt)
        if types:
            qs = qs.filter(event_type__in=types)
        # 한 개 더 끌어와서 truncation 여부 판단
        rows = list(qs.order_by("-ts").values("event_type", "data", "ts")[: limit + 1])
        truncated = len(rows) > limit
        events = rows[:limit]
        for e in events:
            e["ts"] = e["ts"].isoformat()

        # 다음 polling 의 since 로 쓰일 max(ts). 응답은 -ts 정렬이라 events[0] 이 가장 최근.
        last_ts = events[0]["ts"] if events else (since_dt.isoformat() if since_dt else None)

        data = _job_to_dict(job)
        data["events"] = events
        data["events_truncated"] = truncated
        data["last_ts"] = last_ts
        return _ok(data)


@method_decorator(csrf_exempt, name="dispatch")
class JobCancelView(View):
    """POST /api/eval/jobs/<jid>/cancel — 진행 중 job 취소.

    권한: 해당 lecture 의 점수 권한 보유자 (즉 trigger 권한과 동일).
    효과:
    - QUEUED/RUNNING → CANCELLED 전이
    - In-flight evaluate_pair 메시지는 다음 진입 시 _is_job_active 체크에서 자동 skip
    - watchdog finalize_stuck_job 도 CANCELLED 면 no-op
    이미 종결된 job(done/failed/cancelled) 은 409 로 응답.
    """

    def post(self, request, job_id):
        err = _require_login(request)
        if err:
            return err
        try:
            job = EvalJob.objects.select_related("lecture").get(id=job_id)
        except (EvalJob.DoesNotExist, ValueError):
            return _err("job not found", 404)
        perm_err = _require_lecture_perm(request, job.lecture_id)
        if perm_err:
            return perm_err
        if job.status not in EvalJobStatus.ACTIVE:
            return _err(f"job already {job.status}", 409)

        now = timezone.now()
        reason = f"cancelled by user {request.user.username}"
        updated = EvalJob.objects.filter(
            id=job_id, status__in=EvalJobStatus.ACTIVE,
        ).update(
            status=EvalJobStatus.CANCELLED,
            finished_at=now,
            error=reason[:2000],
        )
        if not updated:
            # 동시 전이 — 다시 조회
            job.refresh_from_db()
            return _err(f"job already {job.status}", 409)

        EvalJobEvent.objects.create(
            job_id=job_id,
            event_type=EvalJobEventType.ERROR,
            data={"reason": "cancelled", "by_user_id": request.user.id, "by_username": request.user.username},
        )
        # 슬롯 해제 → 대기 중 QUEUED job 자동 promote
        from ..tasks import promote_next_queued
        try:
            promote_next_queued()
        except Exception:
            pass
        return _ok({"job_id": str(job_id), "status": EvalJobStatus.CANCELLED})


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
        use_qual = _parse_json_param(request, "use_qual")
        stem, content, content_type = export_service.build_contest_export(
            contest_id, fmt, weights=weights, scales=scales, use_qual=use_qual
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
        use_qual = _parse_json_param(request, "use_qual")
        stem, content, content_type = export_service.build_lecture_export(
            lecture_id, fmt, weights=weights, scales=scales, use_qual=use_qual
        )
        if stem is None:
            return _err(content, 404 if "not found" in (content or "").lower() else 400)
        return _export_response(stem, content, content_type, fmt)
