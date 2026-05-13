"""
/api/eval/ 사용자 측 endpoint.

path converter `<int:...>` 사용 — re_path 의 named group 은 str 로 들어와 ORM
자동 coerce 에 의존하게 됨. path converter 는 int 타입 보장.
"""
from django.urls import path

from ..views.oj import (
    CellDetailView,
    ContestExportView,
    ContestScoreboardView,
    EvalStatusView,
    JobDetailView,
    LectureContestsView,
    LectureDetailView,
    LectureExportView,
    LecturesView,
    QualitativeEvalTriggerView,
    QueueView,
    SemestersView,
    YearsView,
)

urlpatterns = [
    # Navigation
    path("years", YearsView.as_view(), name="eval_years"),
    path("years/<int:year>/semesters", SemestersView.as_view(), name="eval_semesters"),
    path("years/<int:year>/semesters/<int:semester>/lectures", LecturesView.as_view(), name="eval_lectures"),
    path("lectures/<int:lecture_id>", LectureDetailView.as_view(), name="eval_lecture_detail"),
    path("lectures/<int:lecture_id>/contests", LectureContestsView.as_view(), name="eval_lecture_contests"),

    # Scoreboard / Detail / Status
    path("contests/<int:contest_id>/scoreboard", ContestScoreboardView.as_view(), name="eval_contest_scoreboard"),
    path(
        "contests/<int:contest_id>/students/<int:user_id>/problems/<int:problem_id>",
        CellDetailView.as_view(),
        name="eval_contest_cell",
    ),
    path("contests/<int:contest_id>/eval-status", EvalStatusView.as_view(), name="eval_contest_status"),

    # Trigger / Queue / Job detail
    path("contests/<int:contest_id>/qualitative-eval", QualitativeEvalTriggerView.as_view(), name="eval_qualitative_trigger"),
    path("queue", QueueView.as_view(), name="eval_queue"),
    path("jobs/<int:job_id>", JobDetailView.as_view(), name="eval_job_detail"),

    # Score export
    path("contests/<int:contest_id>/score_export", ContestExportView.as_view(), name="eval_contest_export"),
    path("lectures/<int:lecture_id>/score_export", LectureExportView.as_view(), name="eval_lecture_export"),
]
