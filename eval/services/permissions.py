"""
정성평가/점수 권한 검사.

기존 lecture/views/eval_proxy.py 의 _has_lecture_score_permission 로직을
eval 앱 내부로 이관. PR 6 의 cleanup 단계에서 eval_proxy.py 자체는 삭제됨.
"""
from account.models import AdminType
from lecture.models import ta_admin_class


def has_lecture_score_permission(user, lecture_id):
    if not user or not user.is_authenticated:
        return False
    if user.admin_type in (AdminType.SUPER_ADMIN, AdminType.ADMIN):
        return True
    if lecture_id is None:
        return False
    return ta_admin_class.objects.filter(
        lecture_id=lecture_id, user=user, score_isallow=True
    ).exists()


def has_any_score_permission(user):
    """globally-scoped 메타 endpoint (/years, /queue, /jobs) 허용 여부."""
    if not user or not user.is_authenticated:
        return False
    if user.admin_type in (AdminType.SUPER_ADMIN, AdminType.ADMIN):
        return True
    return ta_admin_class.objects.filter(user=user, score_isallow=True).exists()
