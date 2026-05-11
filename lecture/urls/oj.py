from django.urls import re_path

from ..views.oj import LectureAPI, CheckingAIhelperFlagAPI, LectureListAPI, TakingLectureListAPI, LectureApplyAPI, ContestExitInfoListAPI, TAlistLectureAPI, LectureScorePermissionAPI
from ..views.score_export import LectureScoreExportAPI, ContestScoreExportAPI

urlpatterns = [
    re_path(r"^lecture/?$", LectureAPI.as_view(), name="lecture_api"),
    re_path(r"^lecture/aihelperflag/?$", CheckingAIhelperFlagAPI.as_view(), name="lecture_aihelper_api"),
    re_path(r"^lectures/?$", LectureListAPI.as_view(), name="lectures_api"),
    re_path(r"^takinglec/?$", TakingLectureListAPI.as_view(), name="takinglectures_api"),
    re_path(r"^lectureapply/?$", LectureApplyAPI.as_view(), name="lectureapply_api"),
    re_path(r"^lecture/contest_exit_manage/?$", ContestExitInfoListAPI.as_view(), name="lecture_contest_exit_manage_api"),    # working by soojung
    re_path(r"^lecture/talist/?$", TAlistLectureAPI.as_view(), name="ta_list_api"),
    re_path(r"^lecture/score_permission/?$", LectureScorePermissionAPI.as_view(), name="lecture_score_permission_api"),
    re_path(r"^lecture/(?P<lecture_id>\d+)/score_export/?$", LectureScoreExportAPI.as_view(), name="lecture_score_export_api"),
    re_path(r"^contest/(?P<contest_id>\d+)/score_export/?$", ContestScoreExportAPI.as_view(), name="contest_score_export_api"),
]
