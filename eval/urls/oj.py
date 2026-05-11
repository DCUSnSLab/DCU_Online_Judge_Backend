"""
/api/eval/ 하위 사용자 측 endpoint.

PR1 은 스켈레톤만. 실제 view 는 PR2(read) / PR3(write) / PR4(export) 에서 채움.
"""
from django.urls import re_path

urlpatterns = [
    # PR 2: /years, /years/<y>/semesters, /years/<y>/semesters/<s>/lectures
    # PR 2: /lectures/<id>, /lectures/<id>/contests, /contests/<id>/scoreboard,
    #       /contests/<id>/students/<uid>/problems/<pid>, /contests/<id>/eval-status
    # PR 3: POST /contests/<id>/qualitative-eval, /queue, /jobs/<id>
    # PR 4: /contests/<id>/score_export, /lectures/<id>/score_export
]
