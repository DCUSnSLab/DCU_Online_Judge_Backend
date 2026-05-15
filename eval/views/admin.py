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
        .select_related("lecture", "contest")
        .order_by("started_at")
        .values(
            "id", "lecture_id", "contest_id",
            "lecture__title", "contest__title", "contest__lecture_contest_type",
            "n_done", "n_failed", "n_total", "started_at",
        )
    )
    pending = list(
        EvalJob.objects.filter(status=EvalJobStatus.QUEUED)
        .select_related("lecture", "contest")
        .order_by("enqueued_at")
        .values(
            "id", "lecture_id", "contest_id",
            "lecture__title", "contest__title", "contest__lecture_contest_type",
            "n_total", "enqueued_at",
        )
    )
    # values() 컬럼명 정리 + datetime iso
    def _flatten(rows, ts_field):
        out = []
        for r in rows:
            d = {
                "id": r["id"],
                "lecture_id": r["lecture_id"],
                "lecture_title": r.get("lecture__title"),
                "contest_id": r["contest_id"],
                "contest_title": r.get("contest__title"),
                "contest_type": r.get("contest__lecture_contest_type"),
                "n_total": r["n_total"],
            }
            if "n_done" in r:
                d["n_done"] = r["n_done"]
                d["n_failed"] = r["n_failed"]
            t = r.get(ts_field)
            d[ts_field] = t.isoformat() if t else None
            out.append(d)
        return out
    return {
        "slots_total": max_n,
        "slots_in_use": in_flight,
        "queue_size": len(pending),
        "running": _flatten(running, "started_at"),
        "pending": _flatten(pending, "enqueued_at"),
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


class EvalSlotsResetAPI(APIView):
    """POST in-flight 카운터 강제 0 리셋. 워커 SIGKILL/OOM 으로 release 못 한 leak 복구용.

    주의: 진행 중 evaluate_pair 의 release 가 호출되면 일시적으로 음수가 될 수 있으나
    slots.release() 의 음수 가드가 이를 0 으로 복구함.
    """

    @super_admin_required
    def post(self, request):
        before = slots_service.get_in_flight()
        slots_service.reset_in_flight()
        return self.success({"before": before, "after": 0, **_snapshot()})
