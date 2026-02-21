from django.conf.urls import url

from ..views.internal import LLMValidateKeyAPI

urlpatterns = [
    url(r"^llm/validate-key/?$", LLMValidateKeyAPI.as_view(), name="llm_validate_key_api"),
]
