from django.urls import re_path

from ..views.admin import SubmissionRejudgeAPI, SubmissionUpdater, SubmissionDataAPI, TopSubmittersAPI

urlpatterns = [
    re_path(r"^submission/rejudge?$", SubmissionRejudgeAPI.as_view(), name="submission_rejudge_api"),
    re_path(r"^submission/SubmissionUpdater/?$", SubmissionUpdater.as_view(), name="submission_updater_api"),
    re_path(r"^sub_date_counts", SubmissionDataAPI.as_view(), name="submission_date_counts_api"),
    re_path(r"^topsubmitters", TopSubmittersAPI.as_view(), name="topsubmitters_counts_api"),
]
