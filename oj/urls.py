from django.urls import include, re_path

from django.urls import path

urlpatterns = [
    re_path(r"^api/", include("account.urls.oj")),
    re_path(r"^api/admin/", include("account.urls.admin")),
    re_path(r"^api/", include("announcement.urls.oj")),
    re_path(r"^api/admin/", include("announcement.urls.admin")),
    re_path(r"^api/", include("conf.urls.oj")),
    re_path(r"^api/admin/", include("conf.urls.admin")),
    re_path(r"^api/", include("problem.urls.oj")),
    re_path(r"^api/admin/", include("problem.urls.admin")),
    re_path(r"^api/", include("contest.urls.oj")),
    re_path(r"^api/admin/", include("contest.urls.admin")),
    #path("api/admin", include("contest.urls.admin")),
    re_path(r"^api/", include("submission.urls.oj")),
    re_path(r"^api/admin/", include("submission.urls.admin")),

    #강의 페이지 추가를 위해 임의로 추가한 부분
    re_path(r"^api/", include("lecture.urls.oj")),
    re_path(r"^api/admin/", include("lecture.urls.admin")),
    ###########################################

    re_path(r"^api/admin/", include("utils.urls")),
	re_path(r"^api/", include("heartbeat.urls")),
    re_path(r"^api/", include("qna.urls.oj")),
    re_path(r"^api/", include("llm.urls.oj")),
    re_path(r"^api/admin/", include("llm.urls.admin")),
    re_path(r"^api/internal/", include("llm.urls.internal")),
]
