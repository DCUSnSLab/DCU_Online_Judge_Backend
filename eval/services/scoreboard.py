"""
Scoreboard 생성 service.

eval-dashboard 사이드카(`api/scoreboard.py`, `queries.py`) 의 응답 구조를 1:1 으로
유지하면서 데이터 소스만 변경:
- final submission: raw SQL ROW_NUMBER OVER → Django ORM DISTINCT ON (Postgres)
- testcase 결과: submission.result + statistic_info (동일)
- qualitative: 디스크 JSON → EvalQualitative DB 테이블 (PR 3 이전엔 비어있음)

Response shape 는 사이드카와 byte-equal — Frontend 는 URL baseURL 만 바꾸면 됨.
"""
from collections import defaultdict

from account.models import User
from contest.models import Contest
from lecture.models import Lecture, signup_class
from problem.models import Problem
from submission.models import Submission

from ..models import EvalAIUsage, EvalConfidence, EvalQualitative


# eval-dashboard 와 sync — JudgeStatus 변경 시 동기화 필요
RESULT_LABELS = {
    -2: "CE",
    -1: "WA",
    0: "AC",
    1: "TLE",
    2: "RTLE",
    3: "MLE",
    4: "RE",
    5: "SE",
    6: "PENDING",
    7: "JUDGING",
    8: "PA",
}


def result_label(code):
    if code is None:
        return None
    return RESULT_LABELS.get(code, f"R{code}")


def list_final_submissions(lecture_id, contest_id, include_pending=False):
    """학생-문제별 최신 submission 1건 (raw SQL 의 ROW_NUMBER OVER 대체).

    Postgres DISTINCT ON 으로 ORM 표현. 결과는 list of dict 로 사이드카와 일치하게.
    """
    qs = Submission.objects.filter(lecture_id=lecture_id, contest_id=contest_id)
    if not include_pending:
        qs = qs.exclude(result__in=(6, 7))  # PENDING, JUDGING
    # Postgres DISTINCT ON (user_id, problem_id) — 정렬 첫 컬럼이 distinct 필드와 일치해야 함
    qs = qs.order_by("user_id", "problem_id", "-create_time", "-id").distinct(
        "user_id", "problem_id"
    )
    rows = []
    # select_related 로 problem.label 조회 1회만
    for s in qs.select_related("problem"):
        rows.append({
            "id": s.id,
            "user_id": s.user_id,
            "username": s.username,
            "problem_id": s.problem_id,
            "problem_label": s.problem._id,
            "total_score": s.problem.total_score,
            "language": s.language,
            "result": s.result,
            "statistic_info": s.statistic_info or {},
            "create_time": s.create_time,
        })
    # 사이드카는 username, problem_label 순 정렬
    rows.sort(key=lambda r: ((r["username"] or "").lower(), r["problem_label"] or ""))
    return rows


def list_students(lecture_id):
    """signup_class JOIN user. enrolled 는 isallow."""
    rows = []
    for s in signup_class.objects.filter(lecture_id=lecture_id).select_related("user").order_by("user__username"):
        if s.user is None:
            continue
        rows.append({
            "user_id": s.user_id,
            "username": s.user.username,
            "realname": s.user.realname,
            "schoolssn": getattr(s.user, "schoolssn", None),
            "enrolled": bool(s.isallow),
        })
    return rows


def list_contest_problems(contest_id):
    rows = []
    for p in Problem.objects.filter(contest_id=contest_id).order_by("_id"):
        rows.append({
            "id": p.id,
            "label": p._id,
            "title": p.title,
            "total_score": p.total_score,
            "difficulty": p.difficulty,
        })
    return rows


def _iso_z(dt):
    """사이드카는 UTC 'Z' suffix 를 사용. Django datetime 도 같은 형식으로 정규화."""
    if dt is None:
        return None
    s = dt.isoformat()
    return s.replace("+00:00", "Z")


def list_lecture_contests(lecture_id):
    rows = []
    for c in Contest.objects.filter(lecture_id=lecture_id).order_by("-start_time", "-id"):
        rows.append({
            "id": c.id,
            "title": c.title,
            "lecture_id": c.lecture_id,
            "lecture_contest_type": c.lecture_contest_type,
            "start_time": _iso_z(c.start_time),
            "end_time": _iso_z(c.end_time),
        })
    return rows


def get_lecture_dict(lecture_id):
    try:
        lec = Lecture.objects.get(id=lecture_id)
    except Lecture.DoesNotExist:
        return None
    # 사이드카 응답 키 (id, title, year, semester) 와 동일
    return {
        "id": lec.id,
        "title": lec.title,
        "year": lec.year,
        "semester": lec.semester,
    }


def get_contest_dict(contest_id):
    try:
        c = Contest.objects.get(id=contest_id)
    except Contest.DoesNotExist:
        return None
    # 사이드카 응답 키 (id, title, lecture_id, lecture_contest_type, start_time, end_time) 와 동일
    return {
        "id": c.id,
        "title": c.title,
        "lecture_id": c.lecture_id,
        "lecture_contest_type": c.lecture_contest_type,
        "start_time": _iso_z(c.start_time),
        "end_time": _iso_z(c.end_time),
    }


def _qualitative_short(snapshot_id):
    """EvalQualitative + EvalAIUsage 의 매트릭스용 컴팩트 표현.

    사이드카 응답의 QualitativeShort 와 동일 키 (overall, suggested_partial_score,
    ai_likelihood_score, ai_confidence, has_error).
    """
    qual = EvalQualitative.objects.filter(snapshot_id=snapshot_id).first()
    aiu = EvalAIUsage.objects.filter(snapshot_id=snapshot_id).first()
    if not qual and not aiu:
        return None
    return {
        "overall": qual.overall if qual else None,
        "suggested_partial_score": qual.suggested_partial_score if qual else None,
        "ai_likelihood_score": aiu.likelihood_score if aiu else None,
        "ai_confidence": aiu.confidence if aiu else EvalConfidence.LOW,
        "has_error": bool((qual and qual.error) or (aiu and aiu.error)),
    }


def _evaluated_snapshots_by_pair(contest_id):
    """(user_id, problem_label) -> snapshot_id 매핑 — qualitative/ai 가 1개라도 있는 것만."""
    from ..models import EvalSubmissionSnapshot
    qs = EvalSubmissionSnapshot.objects.filter(contest_id=contest_id).select_related("problem")
    out = {}
    qual_ids = set(
        EvalQualitative.objects.filter(snapshot__contest_id=contest_id).values_list("snapshot_id", flat=True)
    )
    ai_ids = set(
        EvalAIUsage.objects.filter(snapshot__contest_id=contest_id).values_list("snapshot_id", flat=True)
    )
    eval_ids = qual_ids | ai_ids
    for snap in qs:
        if snap.id in eval_ids:
            out[(snap.user_id, snap.problem._id)] = snap.id
    return out


def build_scoreboard(contest_id):
    """사이드카 GET /api/contests/{id}/scoreboard 응답 1:1 재현."""
    contest = get_contest_dict(contest_id)
    if not contest:
        return None, "contest not found"
    lecture_id = contest["lecture_id"]
    if lecture_id is None:
        return None, "contest has no lecture_id"
    lecture = get_lecture_dict(lecture_id)
    if not lecture:
        return None, "lecture not found"

    problems = list_contest_problems(contest_id)
    if not problems:
        return None, "no problems in contest"

    roster = list_students(lecture_id)
    submissions = list_final_submissions(lecture_id, contest_id)

    # roster + 외부 제출자 (signup 안 한 사용자) 모두 포함
    by_uid = {r["user_id"]: r for r in roster}
    for s in submissions:
        if s["user_id"] not in by_uid:
            by_uid[s["user_id"]] = {
                "user_id": s["user_id"],
                "username": s["username"],
                "realname": None,
                "schoolssn": None,
                "enrolled": False,
            }

    subs_by_user = defaultdict(list)
    for s in submissions:
        subs_by_user[s["user_id"]].append(s)

    eval_pairs = _evaluated_snapshots_by_pair(contest_id)

    students = []
    for uid in sorted(by_uid.keys(), key=lambda i: ((by_uid[i].get("username") or "").lower())):
        user = by_uid[uid]
        by_problem = {}
        for p in problems:
            by_problem[p["label"]] = {"testcase": None, "qualitative": None}
        for s in subs_by_user.get(uid, []):
            stat = s.get("statistic_info") or {}
            by_problem[s["problem_label"]]["testcase"] = {
                "submission_id": s["id"],
                "result": s["result"],
                "result_label": result_label(s["result"]),
                "score": stat.get("score"),
                "time_cost_ms": stat.get("time_cost"),
                "memory_cost_kb": stat.get("memory_cost"),
                "language": s.get("language"),
            }
        for p in problems:
            key = (uid, p["label"])
            if key in eval_pairs:
                short = _qualitative_short(eval_pairs[key])
                if short:
                    by_problem[p["label"]]["qualitative"] = short
        students.append({
            "user_id": uid,
            "username": user["username"],
            "realname": user.get("realname"),
            "schoolssn": user.get("schoolssn"),
            "by_problem": by_problem,
        })

    n_total_pairs = len(students) * len(problems)
    return {
        "contest": contest,
        "lecture": lecture,
        "problems": problems,
        "students": students,
        "n_evaluated_pairs": len(eval_pairs),
        "n_total_pairs": n_total_pairs,
    }, None


def get_cell_detail(contest_id, user_id, problem_id):
    """사이드카 GET /api/contests/{cid}/students/{uid}/problems/{pid} 응답 재현."""
    contest = get_contest_dict(contest_id)
    if not contest:
        return None, "contest not found"
    lecture_id = contest["lecture_id"]
    try:
        problem = Problem.objects.get(id=problem_id)
    except Problem.DoesNotExist:
        return None, "problem not found"
    if problem.contest_id != contest_id:
        return None, "problem not in contest"

    sub = (
        Submission.objects.filter(
            lecture_id=lecture_id,
            contest_id=contest_id,
            user_id=user_id,
            problem_id=problem_id,
        )
        .exclude(result__in=(6, 7))
        .order_by("-create_time", "-id")
        .first()
    )

    qual_data = None
    aiu_data = None
    if sub:
        from ..models import EvalSubmissionSnapshot
        snap = EvalSubmissionSnapshot.objects.filter(
            contest_id=contest_id, user_id=user_id, problem_id=problem_id
        ).first()
        if snap:
            q = EvalQualitative.objects.filter(snapshot=snap).first()
            if q:
                qual_data = {
                    "scores": q.scores,
                    "comments": q.comments,
                    "overall": q.overall,
                    "suggested_partial_score": q.suggested_partial_score,
                    "summary": q.summary,
                    "model_used": q.model_used,
                    "llm_latency_ms": q.llm_latency_ms,
                    "error": q.error or None,
                    "recomputed": q.recomputed or None,
                }
            a = EvalAIUsage.objects.filter(snapshot=snap).first()
            if a:
                aiu_data = {
                    "likelihood_score": a.likelihood_score,
                    "confidence": a.confidence,
                    "signals": a.signals,
                    "counter_signals": a.counter_signals,
                    "summary": a.summary,
                    "disclaimer": a.disclaimer,
                    "model_used": a.model_used,
                    "llm_latency_ms": a.llm_latency_ms,
                    "error": a.error or None,
                }

    return {
        "lecture_id": lecture_id,
        "contest_id": contest_id,
        "problem": {
            "id": problem.id,
            "label": problem._id,
            "title": problem.title,
            "description": problem.description,
            "input_description": problem.input_description,
            "output_description": problem.output_description,
            "samples": problem.samples,
            "total_score": problem.total_score,
            "difficulty": problem.difficulty,
            "time_limit": problem.time_limit,
            "memory_limit": problem.memory_limit,
        },
        "submission": (
            {
                "id": sub.id,
                "code": sub.code,
                "language": sub.language,
                "result": sub.result,
                "result_label": result_label(sub.result),
                "statistic_info": sub.statistic_info,
                "create_time": sub.create_time.isoformat() if sub.create_time else None,
            }
            if sub
            else None
        ),
        "qualitative": qual_data,
        "ai_usage_assessment": aiu_data,
    }, None


def get_eval_status(contest_id):
    """사이드카 GET /api/contests/{id}/eval-status 응답."""
    from ..models import EvalJob, EvalJobStatus
    n_eval = EvalQualitative.objects.filter(snapshot__contest_id=contest_id).count()
    running = (
        EvalJob.objects.filter(contest_id=contest_id, status__in=EvalJobStatus.ACTIVE)
        .values("id", "started_at")
        .first()
    )
    n_pairs = 0  # 사이드카 응답 호환 — 실제 정확한 값은 build_scoreboard 의 n_total_pairs 와 동일하므로 0 으로 둠
    return {
        "has_lecture_export": True,  # DB 기반이라 항상 True
        "n_evaluated": n_eval,
        "n_pairs": n_pairs,
        "last_run_at": None,
        "running_job_id": str(running["id"]) if running else None,
    }
