from django.conf.urls import url

from ..views.admin import ContestAnnouncementAPI, ContestAPI, ACMContestHelper, DownloadContestSubmissions, AddLectureContestAPI, LectureContestAPI, ContProblemAPI, AddLectureAPI

urlpatterns = [
    url(r"^contest/?$", ContestAPI.as_view(), name="contest_admin_api"),
    url(r"^lecture/contest/?$", LectureContestAPI.as_view(), name="contest_problem_admin_api"),
    url(r"^contest/contproblem/?$", ContProblemAPI.as_view(), name="cont_problem_api"),
    url(r"^contest/announcement/?$", ContestAnnouncementAPI.as_view(), name="contest_announcement_admin_api"),
    url(r"^lecture/add_contest_from_public/?$", AddLectureContestAPI.as_view(), name="add_lecture_contest_from_public_api"),
    url(r"^lecture/add_lecture_copy/?$", AddLectureAPI.as_view(), name="add_lecture_api"),
    url(r"^contest/acm_helper/?$", ACMContestHelper.as_view(), name="acm_contest_helper"),
    url(r"^download_submissions/?$", DownloadContestSubmissions.as_view(), name="acm_contest_helper"),
]
