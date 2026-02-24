from django.urls import re_path

from ..views.admin import SubmissionRejudgeAPI, SubmissionUpdater

urlpatterns = [
    re_path(r"^submission/rejudge?$", SubmissionRejudgeAPI.as_view(), name="submission_rejudge_api"),
    re_path(r"^submission/SubmissionUpdater/?$", SubmissionUpdater.as_view(), name="submission_updater_api"),
]
