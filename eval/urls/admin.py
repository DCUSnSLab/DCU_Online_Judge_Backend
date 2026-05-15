"""/api/admin/eval/ — Super Admin 운영 옵션."""
from django.urls import path

from ..views.admin import EvalQueueConfigAPI, EvalSlotsResetAPI

urlpatterns = [
    path("queue-config", EvalQueueConfigAPI.as_view(), name="eval_admin_queue_config"),
    path("slots/reset", EvalSlotsResetAPI.as_view(), name="eval_admin_slots_reset"),
]
