from django.urls import re_path

from ..views import JudgeServerHeartbeatAPI, LanguagesAPI, WebsiteConfigAPI

urlpatterns = [
    re_path(r"^website/?$", WebsiteConfigAPI.as_view(), name="website_info_api"),
    re_path(r"^judge_server_heartbeat/?$", JudgeServerHeartbeatAPI.as_view(), name="judge_server_heartbeat_api"),
    re_path(r"^languages/?$", LanguagesAPI.as_view(), name="language_list_api")
]
