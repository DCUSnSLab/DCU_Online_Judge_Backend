from django.conf.urls import url

from django.contrib import admin

from .views import LectureAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_admin_api"),
    #url(r"^test/", admin.site.urls),
]
