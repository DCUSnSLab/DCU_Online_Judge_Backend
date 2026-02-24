from django.urls import re_path

from django.contrib import admin

from ..views.admin import LectureAPI, AdminLectureApplyAPI, WaitStudentAddAPI, TAAdminLectureAPI

urlpatterns = [
    re_path(r"^lecture/?$", LectureAPI.as_view(), name="lecture_admin_api"),
    re_path(r"^signupstudent/?$", AdminLectureApplyAPI.as_view(), name="lectureapply_admin_api"),
    re_path(r"^tauser/?$", TAAdminLectureAPI.as_view(), name="ta_admin_api"),
    re_path(r"migratelecture/?$", AdminLectureApplyAPI.as_view(), name="migratelecture_admin_api"),
    re_path(r"^waitstudent/?$", WaitStudentAddAPI.as_view(), name="waitstudent_admin_api"),
    #re_path(r"^test/", admin.site.urls),
]
