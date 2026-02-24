from django.urls import re_path

from ..views.internal import LLMRoutesAPI, LLMUsageReportAPI, LLMValidateKeyAPI

urlpatterns = [
    re_path(r"^llm/validate-key/?$", LLMValidateKeyAPI.as_view(), name="llm_validate_key_api"),
    re_path(r"^llm/report-usage/?$", LLMUsageReportAPI.as_view(), name="llm_report_usage_api"),
    re_path(r"^llm/routes/?$", LLMRoutesAPI.as_view(), name="llm_routes_api"),
]
