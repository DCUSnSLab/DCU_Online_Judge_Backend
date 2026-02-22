from django.conf.urls import url

from ..views.internal import LLMRoutesAPI, LLMUsageReportAPI, LLMValidateKeyAPI

urlpatterns = [
    url(r"^llm/validate-key/?$", LLMValidateKeyAPI.as_view(), name="llm_validate_key_api"),
    url(r"^llm/report-usage/?$", LLMUsageReportAPI.as_view(), name="llm_report_usage_api"),
    url(r"^llm/routes/?$", LLMRoutesAPI.as_view(), name="llm_routes_api"),
]
