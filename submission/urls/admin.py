from django.conf.urls import url

from ..views.admin import SubmissionRejudgeAPI, SubmissionUpdater

urlpatterns = [
    url(r"^submission/rejudge?$", SubmissionRejudgeAPI.as_view(), name="submission_rejudge_api"),
    url(r"^submission/SubmissionUpdater/?$", SubmissionUpdater.as_view(), name="submission_updater_api"),
]
