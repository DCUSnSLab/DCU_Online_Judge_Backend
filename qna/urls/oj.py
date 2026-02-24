from django.urls import re_path

from ..views.oj import QnAPostAPI, QnAPostDetailAPI, CommentAPI, AIhelperAPI

urlpatterns = [
    re_path(r"^comment/?$", CommentAPI.as_view(), name="Comment_API"),
    re_path(r"^qapost/?$", QnAPostAPI.as_view(), name="QnAPost_API"),
    re_path(r"^qapostdetail/?$", QnAPostDetailAPI.as_view(), name="QnAPostDetail_API"),
    re_path(r"^aihelper/$",AIhelperAPI.as_view(), name="AIhelper_API"),
]