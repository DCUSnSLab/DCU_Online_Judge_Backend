from django.conf.urls import *
from .views import HeartBeatView, StaticHeartbeatView

urlpatterns = [
    url(r'^heartbeat/$', HeartBeatView.as_view(), name='django_heartbeat'),
    url(r'^staticheartbeat/$', StaticHeartbeatView.as_view(), name='django_static_heartbeat'),
]