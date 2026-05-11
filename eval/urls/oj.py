"""
/api/eval/ 하위 사용자 측 endpoint.

PR2 — read endpoints (navigation + scoreboard + cell detail + eval-status).
PR3 — POST trigger, /queue, /jobs/<id>
PR4 — /score_export
"""
from django.urls import re_path

from ..views.oj import (
    CellDetailView,
    ContestScoreboardView,
    EvalStatusView,
    LectureContestsView,
    LectureDetailView,
    LecturesView,
    SemestersView,
    YearsView,
)

urlpatterns = [
    # Navigation
    re_path(r"^years/?$", YearsView.as_view(), name="eval_years"),
    re_path(r"^years/(?P<year>\d+)/semesters/?$", SemestersView.as_view(), name="eval_semesters"),
    re_path(
        r"^years/(?P<year>\d+)/semesters/(?P<semester>\d+)/lectures/?$",
        LecturesView.as_view(),
        name="eval_lectures",
    ),
    re_path(r"^lectures/(?P<lecture_id>\d+)/?$", LectureDetailView.as_view(), name="eval_lecture_detail"),
    re_path(
        r"^lectures/(?P<lecture_id>\d+)/contests/?$",
        LectureContestsView.as_view(),
        name="eval_lecture_contests",
    ),

    # Scoreboard / Detail / Status
    re_path(
        r"^contests/(?P<contest_id>\d+)/scoreboard/?$",
        ContestScoreboardView.as_view(),
        name="eval_contest_scoreboard",
    ),
    re_path(
        r"^contests/(?P<contest_id>\d+)/students/(?P<user_id>\d+)/problems/(?P<problem_id>\d+)/?$",
        CellDetailView.as_view(),
        name="eval_contest_cell",
    ),
    re_path(
        r"^contests/(?P<contest_id>\d+)/eval-status/?$",
        EvalStatusView.as_view(),
        name="eval_contest_status",
    ),

    # PR 3: POST /contests/<id>/qualitative-eval, /queue, /jobs/<id>
    # PR 4: /contests/<id>/score_export, /lectures/<id>/score_export
]
