from django.urls import re_path

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
    re_path(r"^contests/?$", ContestListAPI.as_view(), name="contest_list_api"),
    re_path(r"^contest/?$", ContestAPI.as_view(), name="contest_api"),
    re_path(r"^contest/password/?$", ContestPasswordVerifyAPI.as_view(), name="contest_password_api"),
    re_path(r"^contest/announcement/?$", ContestAnnouncementListAPI.as_view(), name="contest_announcement_api"),
    re_path(r"^contest/access/?$", ContestAccessAPI.as_view(), name="contest_access_api"),
    re_path(r"^contest_rank/?$", ContestRankAPI.as_view(), name="contest_rank_api"),
    re_path(r"^contest/exit/?$", ContestExitAPI.as_view(), name="contest_exit_api"),     # working by soojung
    re_path(r"^contest/time_over_exit/?$", ContestTimeOverExitAPI.as_view(), name="contest_time_over_exit_api"),     # working by soojung
    re_path(r"^contest/score_info/?$", ContestScoreInfoAPI.as_view(), name="contest_score_info_api"),    # working by soojung
    re_path(r"^contest/lecture_user/?$", ContestLectureUserAPI.as_view(), name="contest_lecture_user_api"),  # working by soojung
    re_path(r"^contest/user/?$", ContestUserAPI.as_view(), name="contest_user_api"),  # working by soojung
    re_path(r"^contest/exit_student/?$", ContestExitStudentAPI.as_view(), name="contest_exit_student_api"),  # working by soojung
    re_path(r"^contest/check_in/?$", ContestCheckInAPI.as_view(), name="contest_check_in_api")
]
