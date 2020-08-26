from django.conf.urls import url

from django.contrib import admin

from ..views.admin import LectureAPI, AdminLectureApplyAPI, WaitStudentAddAPI, TAAdminLectureAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_admin_api"),
    url(r"^signupstudent/?$", AdminLectureApplyAPI.as_view(), name="lectureapply_admin_api"),
    url(r"^tauser/?$", TAAdminLectureAPI.as_view(), name="ta_admin_api"),
    url(r"^waitstudent/?$", WaitStudentAddAPI.as_view(), name="waitstudent_admin_api"),
    #url(r"^test/", admin.site.urls),
]
