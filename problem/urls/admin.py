from django.urls import re_path

from ..views.admin import (ContestProblemAPI, ProblemAPI, TestCaseAPI, TestCaseDataAPI, MakeContestProblemPublicAPIView,
                           CompileSPJAPI, AddContestProblemAPI, ExportProblemAPI, ImportProblemAPI, TestCaseRenameAPI,
                           FPSProblemImport, CopyKiller, CopyKillerAPIView)

urlpatterns = [
    re_path(r"^test_case/?$", TestCaseAPI.as_view(), name="test_case_api"),
    re_path(r"^test_case_data/?$", TestCaseDataAPI.as_view(), name="test_case_data_api"),
    re_path(r"^test_case/rename$", TestCaseRenameAPI.as_view(), name="test_case_rename_api"),
    re_path(r"^compile_spj/?$", CompileSPJAPI.as_view(), name="compile_spj"),
    re_path(r"^problem/?$", ProblemAPI.as_view(), name="problem_admin_api"),
    re_path(r"^contest/problem/?$", ContestProblemAPI.as_view(), name="contest_problem_admin_api"),
    re_path(r"^contest_problem/make_public/?$", MakeContestProblemPublicAPIView.as_view(), name="make_public_api"),
    re_path(r"^contest/add_problem_from_public/?$", AddContestProblemAPI.as_view(), name="add_contest_problem_from_public_api"),
    re_path(r"^export_problem/?$", ExportProblemAPI.as_view(), name="export_problem_api"),
    re_path(r"^import_problem/?$", ImportProblemAPI.as_view(), name="import_problem_api"),
    re_path(r"^import_fps/?$", FPSProblemImport.as_view(), name="fps_problem_api"),
    re_path(r"^problem/copy_killer/?$", CopyKiller.as_view(), name="copy_killer"),
    re_path(r"^problem/copykiller/?$", CopyKillerAPIView.as_view(), name="copy_killer_api"),
]
