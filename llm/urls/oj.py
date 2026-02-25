from django.urls import re_path

from ..views.oj import LLMChatCompletionsAPI, LLMChatMessageAPI, LLMChatSessionAPI

urlpatterns = [
    re_path(r"^llm/chat/sessions/?$", LLMChatSessionAPI.as_view(), name="llm_chat_sessions_api"),
    re_path(r"^llm/chat/messages/?$", LLMChatMessageAPI.as_view(), name="llm_chat_messages_api"),
    re_path(r"^llm/chat/completions/?$", LLMChatCompletionsAPI.as_view(), name="llm_chat_completions_api"),
]
