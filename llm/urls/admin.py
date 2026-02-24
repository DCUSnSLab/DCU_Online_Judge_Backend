from django.urls import re_path

from ..views.admin import LLMKeyAdminAPI, LLMKeyRevokeAPI, LLMRouteAdminAPI

urlpatterns = [
    re_path(r"^llm/keys/?$", LLMKeyAdminAPI.as_view(), name="llm_key_admin_api"),
    re_path(r"^llm/keys/revoke/?$", LLMKeyRevokeAPI.as_view(), name="llm_key_revoke_api"),
    re_path(r"^llm/routes/?$", LLMRouteAdminAPI.as_view(), name="llm_route_admin_api"),
]
