from django.urls import re_path

from ..views.oj import LectureAPI, CheckingAIhelperFlagAPI, LectureListAPI, TakingLectureListAPI, LectureApplyAPI, ContestExitInfoListAPI, TAlistLectureAPI

urlpatterns = [
    re_path(r"^lecture/?$", LectureAPI.as_view(), name="lecture_api"),
    re_path(r"^lecture/aihelperflag/?$", CheckingAIhelperFlagAPI.as_view(), name="lecture_aihelper_api"),
    re_path(r"^lectures/?$", LectureListAPI.as_view(), name="lectures_api"),
    re_path(r"^takinglec/?$", TakingLectureListAPI.as_view(), name="takinglectures_api"),
    re_path(r"^lectureapply/?$", LectureApplyAPI.as_view(), name="lectureapply_api"),
    re_path(r"^lecture/contest_exit_manage/?$", ContestExitInfoListAPI.as_view(), name="lecture_contest_exit_manage_api"),    # working by soojung
    re_path(r"^lecture/talist/?$", TAlistLectureAPI.as_view(), name="ta_list_api"),
]
