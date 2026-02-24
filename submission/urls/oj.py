from django.urls import re_path

from ..views.oj import SubmissionAPI, SubmissionListAPI, ContestSubmissionListAPI, SubmissionExistsAPI, SubmissionLogAPI, GithubPushAPI

urlpatterns = [
    re_path(r"^submission/?$", SubmissionAPI.as_view(), name="submission_api"),
    re_path(r"^submissions/?$", SubmissionListAPI.as_view(), name="submission_list_api"),
    re_path(r"^submissionslog/?$", SubmissionLogAPI.as_view(), name="submission_log_api"),
    re_path(r"^submission_exists/?$", SubmissionExistsAPI.as_view(), name="submission_exists"),
    re_path(r"^contest_submissions/?$", ContestSubmissionListAPI.as_view(), name="contest_submission_list_api"),
    re_path(r"^githubpush/?$", GithubPushAPI.as_view(), name="github_push_api"),
]
