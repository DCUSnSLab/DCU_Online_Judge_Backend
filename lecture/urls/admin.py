from django.conf.urls import url

from django.contrib import admin

from ..views.admin import LectureAPI, AdminLectureApplyAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_admin_api"),
    url(r"^acceptstudent/?$", AdminLectureApplyAPI.as_view(), name="lectureapply_admin_api"),
    #url(r"^test/", admin.site.urls),
]
