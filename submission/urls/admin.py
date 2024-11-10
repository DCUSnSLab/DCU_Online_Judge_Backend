from django.conf.urls import url

from ..views.admin import SubmissionRejudgeAPI, SubmissionUpdater, SubmissionDateAPI

urlpatterns = [
    url(r"^submission/rejudge?$", SubmissionRejudgeAPI.as_view(), name="submission_rejudge_api"),
    url(r"^submission/SubmissionUpdater/?$", SubmissionUpdater.as_view(), name="submission_updater_api"),
    url(r"^submission/date_counts?$", SubmissionDateAPI.as_view(), name="submission_date_counts_api"),
]