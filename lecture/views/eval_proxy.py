"""
eval-dashboard FastAPI(:8001)로 가는 reverse proxy.
- 외부에는 /eval-api/<subpath> 만 노출
- FastAPI는 127.0.0.1 로만 listen → 같은 머신의 Django 프로세스만 도달 가능
- 인증은 DCUCODE Django 세션을 그대로 사용
- 권한은 lecture 단위로 검사 (admin / score_isallow=True 인 TA)
- 클라가 보낸 X-Requester 헤더는 무조건 strip → request.user.id 로 다시 박음
"""
import json

import requests
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from account.models import AdminType
from contest.models import Contest

from ..models import ta_admin_class

EVAL_BASE = "http://127.0.0.1:8001/api"


def _has_lecture_score_permission(user, lecture_id):
    if not user.is_authenticated:
        return False
    if user.admin_type in (AdminType.SUPER_ADMIN, AdminType.ADMIN):
        return True
    if lecture_id is None:
        return False
    return ta_admin_class.objects.filter(
        lecture_id=lecture_id, user=user, score_isallow=True
    ).exists()


def _user_has_any_score_permission(user):
    """globally-scoped 메타 엔드포인트 (years/queue/health/jobs) 허용 여부."""
    if not user.is_authenticated:
        return False
    if user.admin_type in (AdminType.SUPER_ADMIN, AdminType.ADMIN):
        return True
    return ta_admin_class.objects.filter(user=user, score_isallow=True).exists()


def _resolve_lecture_id(subpath):
    """subpath 의 첫 segment 패턴을 보고 lecture_id 결정."""
    parts = [p for p in subpath.split("/") if p]
    if not parts:
        return None, "global"
    head = parts[0]
    if head in ("years", "queue", "health", "jobs"):
        return None, "global"
    if head == "lectures" and len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1]), "lecture"
    if head == "contests" and len(parts) >= 2 and parts[1].isdigit():
        try:
            lec = Contest.objects.values_list("lecture_id", flat=True).get(id=int(parts[1]))
            return lec, "contest"
        except Contest.DoesNotExist:
            return None, "contest-missing"
    return None, "unknown"


def _err(msg, status):
    return JsonResponse({"error": "forbidden" if status == 403 else "error", "data": msg}, status=status)


@method_decorator(csrf_exempt, name="dispatch")
class EvalProxyAPI(View):
    """
    /eval-api/<subpath> 모든 method 처리.
    csrf_exempt: 프론트는 동일 origin(localhost:8080 → :8000)에서 호출하지만
    Vue 의 axios 가 자동으로 X-CSRFToken 을 붙이지 않는 경로일 수 있어 우회.
    Cross-origin 호출은 SameSite=Lax 쿠키 + 127.0.0.1 bind 로 차단됨.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _err("Login required", 401)

        subpath = kwargs.get("subpath", "") or ""
        lecture_id, scope = _resolve_lecture_id(subpath)

        if scope == "global":
            if not _user_has_any_score_permission(request.user):
                return _err("Score permission required", 403)
        elif scope in ("lecture", "contest"):
            if not _has_lecture_score_permission(request.user, lecture_id):
                return _err("Forbidden for this lecture", 403)
        elif scope == "contest-missing":
            return _err("Contest not found", 404)
        else:
            return _err("Unknown eval-api path", 400)

        url = f"{EVAL_BASE}/{subpath}"
        qs = request.META.get("QUERY_STRING", "")
        if qs:
            url = f"{url}?{qs}"

        forward_headers = {
            "X-Requester": str(request.user.id),
            "Accept": request.META.get("HTTP_ACCEPT", "*/*"),
        }
        ctype = request.META.get("CONTENT_TYPE")
        if ctype and request.method in ("POST", "PUT", "PATCH"):
            forward_headers["Content-Type"] = ctype

        body = request.body if request.method in ("POST", "PUT", "PATCH") else None

        is_stream = subpath.endswith("/stream")
        try:
            if is_stream:
                upstream = requests.request(
                    request.method, url, headers=forward_headers, data=body,
                    stream=True, timeout=None,
                )
                resp = StreamingHttpResponse(
                    upstream.iter_content(chunk_size=None),
                    content_type=upstream.headers.get("Content-Type", "text/event-stream"),
                    status=upstream.status_code,
                )
                resp["Cache-Control"] = "no-cache"
                resp["X-Accel-Buffering"] = "no"
                return resp

            upstream = requests.request(
                request.method, url, headers=forward_headers, data=body, timeout=120,
            )
            resp = HttpResponse(
                upstream.content,
                status=upstream.status_code,
                content_type=upstream.headers.get("Content-Type", "application/json"),
            )
            return resp
        except requests.RequestException as e:
            return _err(f"Eval backend unreachable: {e}", 502)
