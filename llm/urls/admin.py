from django.conf.urls import url

from ..views.admin import LLMKeyAdminAPI, LLMKeyRevokeAPI, LLMRouteAdminAPI

urlpatterns = [
    url(r"^llm/keys/?$", LLMKeyAdminAPI.as_view(), name="llm_key_admin_api"),
    url(r"^llm/keys/revoke/?$", LLMKeyRevokeAPI.as_view(), name="llm_key_revoke_api"),
    url(r"^llm/routes/?$", LLMRouteAdminAPI.as_view(), name="llm_route_admin_api"),
]
