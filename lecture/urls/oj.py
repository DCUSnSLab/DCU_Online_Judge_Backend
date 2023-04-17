from django.conf.urls import url

from ..views.oj import LectureAPI, CheckingAIhelperFlagAPI, LectureListAPI, TakingLectureListAPI, LectureApplyAPI, ContestExitInfoListAPI

urlpatterns = [
    url(r"^lecture/?$", LectureAPI.as_view(), name="lecture_api"),
    url(r"^lecture/aihelperflag/?$", CheckingAIhelperFlagAPI.as_view(), name="lecture_aihelper_api"),
    url(r"^lectures/?$", LectureListAPI.as_view(), name="lectures_api"),
    url(r"^takinglec/?$", TakingLectureListAPI.as_view(), name="takinglectures_api"),
    url(r"^lectureapply/?$", LectureApplyAPI.as_view(), name="lectureapply_api"),
    url(r"^lecture/contest_exit_manage/?$", ContestExitInfoListAPI.as_view(), name="lecture_contest_exit_manage_api"),    # working by soojung

]
