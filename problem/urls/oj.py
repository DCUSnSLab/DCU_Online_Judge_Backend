from django.conf.urls import url

from ..views.oj import ProblemTagAPI, ProblemAPI, ContestExitInfoAPI, ContestProblemAPI, PickOneAPI, ProblemResponsibility

urlpatterns = [
    url(r"^problem/tags/?$", ProblemTagAPI.as_view(), name="problem_tag_list_api"),
    url(r"^problem/?$", ProblemAPI.as_view(), name="problem_api"),
    url(r"^problem/contest_exit_info/?$", ContestExitInfoAPI.as_view(), name="problem_contest_exit_access_api"), # working by soojung
    url(r"^problemResponsible/?$", ProblemResponsibility.as_view(), name="problem_api"),
    url(r"^pickone/?$", PickOneAPI.as_view(), name="pick_one_api"),
    url(r"^contest/problem/?$", ContestProblemAPI.as_view(), name="contest_problem_api"),
]