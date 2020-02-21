from django.conf.urls import url

from ..views.oj import LectureAPI, LectureListAPI, LectureApplyAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_api"),
    url(r"^lectures/?$", LectureListAPI.as_view(), name="lectures_api"),
    url(r"^lectureapply/?$", LectureApplyAPI.as_view(), name="lectureapply_api"),
]
