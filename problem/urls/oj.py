from django.conf.urls import url

from ..views.oj import ProblemTagAPI, ProblemAPI, ContestExitAccessAPI, ContestProblemAPI, PickOneAPI, ProblemResponsibility, Random_By_LevelAPI

urlpatterns = [
    url(r"^problem/tags/?$", ProblemTagAPI.as_view(), name="problem_tag_list_api"),
    url(r"^problem/?$", ProblemAPI.as_view(), name="problem_api"),
    url(r"^problem/contest_exit_access/?$", ContestExitAccessAPI.as_view(), name="problem_contest_exit_access_api"), # working by soojung
    url(r"^problemResponsible/?$", ProblemResponsibility.as_view(), name="problem_api"),
    url(r"^pickone/?$", PickOneAPI.as_view(), name="pick_one_api"),
    url(r"^random_by_level/?$", Random_By_LevelAPI.as_view(), name="random_by_level_api"),
    url(r"^contest/problem/?$", ContestProblemAPI.as_view(), name="contest_problem_api"),
]