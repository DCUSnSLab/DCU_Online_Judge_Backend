from django.conf.urls import url

from ..views.oj import QnAPostAPI, QnAPostDetailAPI

urlpatterns = [
    url(r"^qapost/?$", QnAPostAPI.as_view(), name="QnAPost_API"),
    url(r"^qapostdetail/?$", QnAPostDetailAPI.as_view(), name="QnAPostDetail_API"),
]