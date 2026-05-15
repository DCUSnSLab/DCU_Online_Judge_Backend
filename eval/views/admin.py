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
    pair_workers = slots_service.get_pair_workers()
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
        "pair_workers_per_job": pair_workers,
        "queue_size": len(pending),
        "running": _flatten(running, "started_at"),
        "pending": _flatten(pending, "enqueued_at"),
    }


class EvalQueueConfigAPI(APIView):
    """GET 현재 상태 + POST 슬롯 변경. Super Admin 전용.

    한도 증가 시 대기 중인 QUEUED job 이 있다면 즉시 promote.
    """

    @super_admin_required
    def get(self, request):
        return self.success(_snapshot())

    @super_admin_required
    def post(self, request):
        """두 한도를 부분/전체 갱신 가능 — 보낸 키만 적용.

        body 예시:
          {"value": 4}                       # slots 만 변경 (구버전 호환)
          {"max_concurrent_jobs": 4}         # 동일 (명시적 키)
          {"pair_workers_per_job": 3}        # pair_workers 만 변경
          {"max_concurrent_jobs": 4, "pair_workers_per_job": 3}  # 동시 변경
        """
        data = request.data or {}
        applied = {}

        # 구버전 호환: 'value' 단독 → max_concurrent_jobs
        slots_value = data.get("max_concurrent_jobs", data.get("value"))
        if slots_value is not None:
            try:
                v = int(slots_value)
            except (TypeError, ValueError):
                return self.error("max_concurrent_jobs 는 정수여야 합니다")
            if v < 1 or v > 64:
                return self.error("max_concurrent_jobs 는 1~64 사이여야 합니다")
            applied["max_concurrent_jobs"] = slots_service.set_max(v)

        pair_value = data.get("pair_workers_per_job")
        if pair_value is not None:
            try:
                v = int(pair_value)
            except (TypeError, ValueError):
                return self.error("pair_workers_per_job 는 정수여야 합니다")
            if v < 1 or v > 16:
                return self.error("pair_workers_per_job 는 1~16 사이여야 합니다")
            applied["pair_workers_per_job"] = slots_service.set_pair_workers(v)

        if not applied:
            return self.error("변경할 필드가 없습니다 (max_concurrent_jobs / pair_workers_per_job)")

        # 한도가 늘었으면 대기 중인 job 즉시 promote
        from ..tasks import promote_next_queued
        try:
            promote_next_queued()
        except Exception:
            pass
        return self.success({"applied": applied, **_snapshot()})
