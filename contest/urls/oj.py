from django.conf.urls import url

from ..views.oj import ContestAnnouncementListAPI
from ..views.oj import ContestPasswordVerifyAPI, ContestAccessAPI
from ..views.oj import ContestListAPI, ContestAPI
from ..views.oj import ContestRankAPI
from ..views.oj import ContestExitAPI
from ..views.oj import ContestTimeOverExitAPI
from ..views.oj import ContestScoreInfoAPI
from ..views.oj import ContestLectureUserAPI
from ..views.oj import ContestUserAPI
from ..views.oj import ContestExitStudentAPI
from ..views.oj import ContestCheckInAPI

urlpatterns = [
    url(r"^contests/?$", ContestListAPI.as_view(), name="contest_list_api"),
    url(r"^contest/?$", ContestAPI.as_view(), name="contest_api"),
    url(r"^contest/password/?$", ContestPasswordVerifyAPI.as_view(), name="contest_password_api"),
    url(r"^contest/announcement/?$", ContestAnnouncementListAPI.as_view(), name="contest_announcement_api"),
    url(r"^contest/access/?$", ContestAccessAPI.as_view(), name="contest_access_api"),
    url(r"^contest_rank/?$", ContestRankAPI.as_view(), name="contest_rank_api"),
    url(r"^contest/exit/?$", ContestExitAPI.as_view(), name="contest_exit_api"),     # working by soojung
    url(r"^contest/time_over_exit/?$", ContestTimeOverExitAPI.as_view(), name="contest_time_over_exit_api"),     # working by soojung
    url(r"^contest/score_info/?$", ContestScoreInfoAPI.as_view(), name="contest_score_info_api"),    # working by soojung
    url(r"^contest/lecture_user/?$", ContestLectureUserAPI.as_view(), name="contest_lecture_user_api"),  # working by soojung
    url(r"^contest/user/?$", ContestUserAPI.as_view(), name="contest_user_api"),  # working by soojung
    url(r"^contest/exit_student/?$", ContestExitStudentAPI.as_view(), name="contest_exit_student_api"),  # working by soojung
    url(r"^contest/check_in/?$", ContestCheckInAPI.as_view(), name="contest_check_in_api")
]
