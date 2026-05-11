"""
/api/eval/ read endpoints.

응답 shape 는 사이드카(eval-dashboard FastAPI) 와 byte-equal 을 목표 — Frontend 가
baseURL `/eval-api` → `/api/eval` 만 바꾸면 작동.

권한:
- 메타 endpoint (/years, /semesters, /lectures, /queue, /jobs) → has_any_score_permission
- contest 단위 endpoint (scoreboard, cell, eval-status) → has_lecture_score_permission
"""
from django.db import connection
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from contest.models import Contest

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
