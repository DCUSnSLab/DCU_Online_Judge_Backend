from django.urls import re_path

from ..views.oj import LLMChatCompletionsAPI

urlpatterns = [
    re_path(r"^llm/chat/completions/?$", LLMChatCompletionsAPI.as_view(), name="llm_chat_completions_api"),
]
