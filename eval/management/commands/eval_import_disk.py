"""
디스크의 llm-code-review/out/ 평가 결과를 DB 로 이관.

원본 경로 패턴:
  <LLM_CR_DIR>/out/lecture-<L>_contest-<C>/evaluations/<username>/<problem_label>.json

각 JSON 의 evaluation/ai_usage_assessment 를 EvalQualitative/EvalAIUsage 로 bulk insert.
EvalSubmissionSnapshot 은 submission_id 매칭으로 자동 생성.

사용 예:
  python manage.py eval_import_disk --dry-run
  python manage.py eval_import_disk --lecture 388 --contest 6177
  python manage.py eval_import_disk --overwrite

기본 LLM_CR_DIR: env LLM_CR_DIR > /home/soobin/development/dcucode/DCU_Online_Judge_SideProjects/llm-code-review
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from account.models import User
from contest.models import Contest
from eval.models import EvalAIUsage, EvalQualitative, EvalSubmissionSnapshot
from lecture.models import Lecture
from problem.models import Problem
from submission.models import Submission


DEFAULT_LLM_CR_DIR = "/home/soobin/development/dcucode/DCU_Online_Judge_SideProjects/llm-code-review"
DIR_RE = re.compile(r"^lecture-(\d+)_contest-(\d+)$")


def _llm_cr_dir():
    return os.environ.get("LLM_CR_DIR") or DEFAULT_LLM_CR_DIR


def _code_hash(code):
    return hashlib.sha256((code or "").encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Import disk evaluations JSON files into eval_* DB tables."

    def add_arguments(self, parser):
        parser.add_argument("--lecture", type=int, default=None, help="특정 lecture id 만")
        parser.add_argument("--contest", type=int, default=None, help="특정 contest id 만 (--lecture 와 함께)")
        parser.add_argument("--dry-run", action="store_true", help="실제 insert 없이 count 만")
        parser.add_argument("--overwrite", action="store_true", help="기존 row 있어도 덮어쓰기")
        parser.add_argument("--llm-cr-dir", default=None, help="원본 디렉토리 (env LLM_CR_DIR 우선)")

    def handle(self, *args, **opts):
        base = Path(opts.get("llm_cr_dir") or _llm_cr_dir()) / "out"
        if not base.is_dir():
            self.stderr.write(f"out 디렉토리 없음: {base}")
            return

        wanted_lecture = opts.get("lecture")
        wanted_contest = opts.get("contest")
        dry = opts["dry_run"]
        overwrite = opts["overwrite"]

        total_files = 0
        imported_q = 0
        imported_a = 0
        skipped = 0
        failed = 0

        for run_dir in sorted(base.iterdir()):
            if not run_dir.is_dir():
                continue
            m = DIR_RE.match(run_dir.name)
            if not m:
                continue
            lid, cid = int(m.group(1)), int(m.group(2))
            if wanted_lecture and lid != wanted_lecture:
                continue
            if wanted_contest and cid != wanted_contest:
                continue
            ev_dir = run_dir / "evaluations"
            if not ev_dir.is_dir():
                continue

            self.stdout.write(f"== {run_dir.name} ==")
            try:
                stats = self._import_run(lid, cid, ev_dir, dry=dry, overwrite=overwrite)
            except Exception as e:
                self.stderr.write(f"  실패: {e}")
                failed += 1
                continue
            total_files += stats["files"]
            imported_q += stats["imported_q"]
            imported_a += stats["imported_a"]
            skipped += stats["skipped"]
            self.stdout.write(
                f"  files={stats['files']} q={stats['imported_q']} ai={stats['imported_a']} "
                f"skipped={stats['skipped']}"
            )

        self.stdout.write("")
        prefix = "(DRY-RUN) " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}총 {total_files} 파일 — qual {imported_q}, ai_usage {imported_a}, skip {skipped}, fail {failed}"
        ))

    def _import_run(self, lecture_id, contest_id, ev_dir, *, dry, overwrite):
        # 사전 조회 (FK 검증)
        try:
            lecture = Lecture.objects.get(id=lecture_id)
            contest = Contest.objects.get(id=contest_id)
        except (Lecture.DoesNotExist, Contest.DoesNotExist):
            raise RuntimeError(f"lecture {lecture_id} or contest {contest_id} not in DB")

        problems_by_label = {p._id: p for p in Problem.objects.filter(contest_id=contest_id)}
        # 사용자 ID 사전 캐시 (디렉토리 user 이름 → User 객체)
        user_dirs = [d for d in ev_dir.iterdir() if d.is_dir()]
        usernames = [d.name for d in user_dirs]
        users_by_name = {u.username: u for u in User.objects.filter(username__in=usernames)}

        stats = {"files": 0, "imported_q": 0, "imported_a": 0, "skipped": 0}
        for user_dir in user_dirs:
            user = users_by_name.get(user_dir.name)
            if not user:
                continue
            for jf in user_dir.glob("*.json"):
                stats["files"] += 1
                try:
                    doc = json.loads(jf.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue

                plabel = (doc.get("problem") or {}).get("label") or jf.stem
                problem = problems_by_label.get(plabel)
                if not problem:
                    continue

                sub_id = doc.get("submission_id")
                if not sub_id:
                    continue
                # Submission 존재 확인 (없으면 snapshot 만들 수 없음)
                sub = Submission.objects.filter(id=sub_id).only("code", "language").first()
                if not sub:
                    stats["skipped"] += 1
                    continue

                evaluation = doc.get("evaluation") or {}
                ai_usage = doc.get("ai_usage_assessment") or {}

                if dry:
                    stats["imported_q"] += 1 if evaluation else 0
                    stats["imported_a"] += 1 if ai_usage else 0
                    continue

                with transaction.atomic():
                    snap, _ = EvalSubmissionSnapshot.objects.get_or_create(
                        contest_id=contest_id, user=user, problem=problem,
                        defaults=dict(
                            submission_id=sub_id,
                            lecture_id=lecture_id,
                            code=sub.code or "",
                            code_hash=_code_hash(sub.code or ""),
                            language=sub.language or "",
                        ),
                    )

                    if evaluation:
                        existing = EvalQualitative.objects.filter(snapshot=snap).first()
                        if existing and not overwrite:
                            stats["skipped"] += 1
                        else:
                            EvalQualitative.objects.update_or_create(
                                snapshot=snap,
                                defaults=dict(
                                    scores=evaluation.get("scores") or {},
                                    comments=evaluation.get("comments") or {},
                                    overall=evaluation.get("overall"),
                                    suggested_partial_score=evaluation.get("suggested_partial_score"),
                                    summary=evaluation.get("summary") or "",
                                    model_used=evaluation.get("model_used") or "",
                                    llm_latency_ms=evaluation.get("llm_latency_ms"),
                                    error=evaluation.get("error") or "",
                                    raw_response=(doc.get("raw_response") or "")[:50000],
                                    recomputed=evaluation.get("recomputed") or {},
                                ),
                            )
                            stats["imported_q"] += 1

                    if ai_usage:
                        existing_a = EvalAIUsage.objects.filter(snapshot=snap).first()
                        if existing_a and not overwrite:
                            stats["skipped"] += 1
                        else:
                            EvalAIUsage.objects.update_or_create(
                                snapshot=snap,
                                defaults=dict(
                                    likelihood_score=ai_usage.get("likelihood_score"),
                                    confidence=(ai_usage.get("confidence") or "low"),
                                    signals=ai_usage.get("signals") or [],
                                    counter_signals=ai_usage.get("counter_signals") or [],
                                    summary=ai_usage.get("summary") or "",
                                    disclaimer=ai_usage.get("disclaimer") or "",
                                    model_used=ai_usage.get("model_used") or "",
                                    llm_latency_ms=ai_usage.get("llm_latency_ms"),
                                    error=ai_usage.get("error") or "",
                                    raw_response=(doc.get("ai_usage_raw_response") or "")[:50000],
                                ),
                            )
                            stats["imported_a"] += 1
        return stats
