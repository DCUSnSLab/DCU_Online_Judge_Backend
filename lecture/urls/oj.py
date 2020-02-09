from django.conf.urls import url

from ..views.oj import LectureAPI, LectureListAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_api"),
    url(r"^lectures/?$", LectureListAPI.as_view(), name="lectures_api"),
]
