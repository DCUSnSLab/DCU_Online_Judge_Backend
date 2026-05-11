"""
/api/admin/eval/ — 운영 옵션 관리.

Super Admin 전용. 현재는 큐 동시성(max_concurrent_eval_jobs) 만 조정.
"""
import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from account.decorators import super_admin_required
from utils.api import APIView

from ..models import EvalJob, EvalJobStatus
from ..services import slots as slots_service


def _err(msg, status):
    return JsonResponse({"detail": msg}, status=status)


def _snapshot():
    """현재 큐 상태 스냅샷 — admin 페이지 표시용."""
    max_n = slots_service.get_max()
    in_flight = slots_service.get_in_flight()
    running = list(
        EvalJob.objects.filter(status=EvalJobStatus.RUNNING)
        .order_by("started_at")
        .values("id", "lecture_id", "contest_id", "n_done", "n_failed", "n_total", "started_at")
    )
    pending = list(
        EvalJob.objects.filter(status=EvalJobStatus.QUEUED)
        .order_by("enqueued_at")
        .values("id", "lecture_id", "contest_id", "n_total", "enqueued_at")
    )
    for r in running:
        r["started_at"] = r["started_at"].isoformat() if r["started_at"] else None
    for p in pending:
        p["enqueued_at"] = p["enqueued_at"].isoformat() if p["enqueued_at"] else None
    return {
        "slots_total": max_n,
        "slots_in_use": in_flight,
        "queue_size": len(pending),
        "running": running,
        "pending": pending,
    }


class EvalQueueConfigAPI(APIView):
    """GET 현재 상태 + POST 슬롯 변경. Super Admin 전용."""

    @super_admin_required
    def get(self, request):
        return self.success(_snapshot())

    @super_admin_required
    def post(self, request):
        try:
            value = int((request.data or {}).get("value"))
        except (TypeError, ValueError):
            return self.error("value(정수) 필드가 필요합니다")
        if value < 1 or value > 64:
            return self.error("value 는 1~64 사이여야 합니다")
        applied = slots_service.set_max(value)
        return self.success({"applied": applied, **_snapshot()})
