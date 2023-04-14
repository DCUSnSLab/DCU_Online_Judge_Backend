from django.conf.urls import url

from ..views.oj import QnAPostAPI, QnAPostDetailAPI, CommentAPI, AIhelperAPI

urlpatterns = [
    url(r"^comment/?$", CommentAPI.as_view(), name="Comment_API"),
    url(r"^qapost/?$", QnAPostAPI.as_view(), name="QnAPost_API"),
    url(r"^qapostdetail/?$", QnAPostDetailAPI.as_view(), name="QnAPostDetail_API"),
    url(r"^aihelper/$",AIhelperAPI.as_view(), name="AIhelper_API"),
]