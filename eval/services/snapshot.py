"""Final submission → EvalSubmissionSnapshot 동결 service.

평가 작업 시작 시 호출. 같은 (contest, user, problem) 에 이미 스냅샷이 있으면:
- force=False: skip (기존 스냅샷에 묶인 평가 재사용)
- force=True: code/code_hash 변경 시 새 스냅샷으로 교체 (기존 평가 cascade 삭제)
"""
from __future__ import annotations

import hashlib

from django.db import transaction

from ..models import EvalSubmissionSnapshot
from . import scoreboard as sb_service


def _code_hash(code):
    return hashlib.sha256((code or "").encode("utf-8")).hexdigest()


def snapshot_submissions(contest_id, force=False):
    """contest 의 final submission 들을 EvalSubmissionSnapshot 으로 동결.

    반환: 새로 만들거나 force 로 갱신된 스냅샷의 id 리스트 (= 평가 필요 대상).
    """
    contest = sb_service.get_contest_dict(contest_id)
    if not contest:
        return []
    lecture_id = contest["lecture_id"]

    finals = sb_service.list_final_submissions(lecture_id, contest_id)
    if not finals:
        return []

    # 한 번에 select 한 뒤 in-memory 매칭 — N+1 회피
    existing = {
        (s.user_id, s.problem_id): s
        for s in EvalSubmissionSnapshot.objects.filter(contest_id=contest_id)
    }

    to_evaluate = []
    with transaction.atomic():
        for f in finals:
            from submission.models import Submission
            try:
                sub = Submission.objects.only("code", "language").get(id=f["id"])
            except Submission.DoesNotExist:
                continue
            new_hash = _code_hash(sub.code)
            key = (f["user_id"], f["problem_id"])
            snap = existing.get(key)
            if snap is None:
                snap = EvalSubmissionSnapshot.objects.create(
                    submission_id=f["id"],
                    user_id=f["user_id"],
                    problem_id=f["problem_id"],
                    contest_id=contest_id,
                    lecture_id=lecture_id,
                    code=sub.code,
                    code_hash=new_hash,
                    language=sub.language,
                )
                to_evaluate.append(snap.id)
            elif force or snap.code_hash != new_hash:
                # 코드 바뀜 → 기존 평가 삭제 후 스냅샷 갱신
                snap.qualitative.all().delete() if hasattr(snap, "qualitative_set") else None
                # OneToOne 은 직접 접근으로 cascade
                from ..models import EvalAIUsage, EvalQualitative
                EvalQualitative.objects.filter(snapshot=snap).delete()
                EvalAIUsage.objects.filter(snapshot=snap).delete()
                snap.submission_id = f["id"]
                snap.code = sub.code
                snap.code_hash = new_hash
                snap.language = sub.language
                snap.save(update_fields=["submission_id", "code", "code_hash", "language"])
                to_evaluate.append(snap.id)
            elif force:
                to_evaluate.append(snap.id)
    return to_evaluate
