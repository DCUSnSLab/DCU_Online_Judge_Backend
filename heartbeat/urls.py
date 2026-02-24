from django.urls import re_path
from .views import HeartBeatView, StaticHeartbeatView

urlpatterns = [
    re_path(r'^heartbeat/$', HeartBeatView.as_view(), name='django_heartbeat'),
    re_path(r'^staticheartbeat/$', StaticHeartbeatView.as_view(), name='django_static_heartbeat'),
]