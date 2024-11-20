from django.conf.urls import url

from ..views.admin import SubmissionRejudgeAPI, SubmissionUpdater, SubmissionDataAPI, TopSubmittersAPI

urlpatterns = [
    url(r"^submission/rejudge?$", SubmissionRejudgeAPI.as_view(), name="submission_rejudge_api"),
    url(r"^submission/SubmissionUpdater/?$", SubmissionUpdater.as_view(), name="submission_updater_api"),
    url(r"^sub_date_counts", SubmissionDataAPI.as_view(), name="submission_date_counts_api"),
    url(r"^topsubmitters", TopSubmittersAPI.as_view(), name="submission_date_counts_api"),
]