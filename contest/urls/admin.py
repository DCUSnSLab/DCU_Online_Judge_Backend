from django.urls import re_path

from ..views.admin import ContestAnnouncementAPI, ContestAPI, ACMContestHelper, DownloadContestSubmissions, AddLectureContestAPI, LectureContestAPI, ContProblemAPI, AddLectureAPI

urlpatterns = [
    re_path(r"^contest/?$", ContestAPI.as_view(), name="contest_admin_api"),
    re_path(r"^lecture/contest/?$", LectureContestAPI.as_view(), name="contest_problem_admin_api"),
    re_path(r"^contest/contproblem/?$", ContProblemAPI.as_view(), name="cont_problem_api"),
    re_path(r"^contest/announcement/?$", ContestAnnouncementAPI.as_view(), name="contest_announcement_admin_api"),
    re_path(r"^lecture/add_contest_from_public/?$", AddLectureContestAPI.as_view(), name="add_lecture_contest_from_public_api"),
    re_path(r"^lecture/add_lecture_copy/?$", AddLectureAPI.as_view(), name="add_lecture_api"),
    re_path(r"^contest/acm_helper/?$", ACMContestHelper.as_view(), name="acm_contest_helper"),
    re_path(r"^download_submissions/?$", DownloadContestSubmissions.as_view(), name="acm_contest_helper"),
]
