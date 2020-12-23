from django.conf.urls import include, url

from django.urls import path

urlpatterns = [
    url(r"^api/", include("account.urls.oj")),
    url(r"^api/admin/", include("account.urls.admin")),
    url(r"^api/", include("announcement.urls.oj")),
    url(r"^api/admin/", include("announcement.urls.admin")),
    url(r"^api/", include("conf.urls.oj")),
    url(r"^api/admin/", include("conf.urls.admin")),
    url(r"^api/", include("problem.urls.oj")),
    url(r"^api/admin/", include("problem.urls.admin")),
    url(r"^api/", include("contest.urls.oj")),
    url(r"^api/admin/", include("contest.urls.admin")),
    #path("api/admin", include("contest.urls.admin")),
    url(r"^api/", include("submission.urls.oj")),
    url(r"^api/admin/", include("submission.urls.admin")),

    #강의 페이지 추가를 위해 임의로 추가한 부분
    url(r"^api/", include("lecture.urls.oj")),
    url(r"^api/admin/", include("lecture.urls.admin")),
    ###########################################

    url(r"^api/admin/", include("utils.urls")),
	url(r"^api/", include("heartbeat.urls")),
    url(r"^api/", include("qna.urls.oj")),
]
