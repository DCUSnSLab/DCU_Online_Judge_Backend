from django.urls import re_path

from ..views.oj import ProblemTagAPI, ProblemAPI, ContestExitInfoAPI, ContestProblemAPI, PickOneAPI, ProblemResponsibility

urlpatterns = [
    re_path(r"^problem/tags/?$", ProblemTagAPI.as_view(), name="problem_tag_list_api"),
    re_path(r"^problem/?$", ProblemAPI.as_view(), name="problem_api"),
    re_path(r"^problem/contest_exit_info/?$", ContestExitInfoAPI.as_view(), name="problem_contest_exit_access_api"), # working by soojung
    re_path(r"^problemResponsible/?$", ProblemResponsibility.as_view(), name="problem_api"),
    re_path(r"^pickone/?$", PickOneAPI.as_view(), name="pick_one_api"),
    re_path(r"^contest/problem/?$", ContestProblemAPI.as_view(), name="contest_problem_api"),
]