"""
LLM 기반 정성평가 시스템의 Django 모델.

사이드 프로젝트(SideProjects/llm-code-review, eval-dashboard) 가 디스크 JSON 으로
보존하던 평가 결과를 Postgres 로 일원화한다.

- EvalSubmissionSnapshot: 평가 시점의 final submission 동결 스냅샷
- EvalQualitative: 정성평가 결과 (4축 점수 + 코멘트 + overall)
- EvalAIUsage: AI 사용 가능성 평가 (별도 LLM 호출 결과, 점수 계산과 분리)
- EvalJob: 평가 작업 단위 (contest 1건당 active 1개)
- EvalJobRequester: 같은 job 에 합류한 사용자 (멀티 트리거 dedup)
- EvalJobEvent: Job 진행 이벤트 (폴링 응답 + 감사 로그)

기존 lecture/llm 앱과 동일한 컨벤션:
- db_table 명시 (eval_*)
- on_delete=models.CASCADE
- JSONField 는 utils.models.JSONField (Postgres JSONB)
"""
from django.db import models

from account.models import User
from contest.models import Contest
from lecture.models import Lecture
from problem.models import Problem
from submission.models import Submission
from utils.models import JSONField


class EvalJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    CHOICES = (
        (QUEUED, "Queued"),
        (RUNNING, "Running"),
        (DONE, "Done"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
    )
    ACTIVE = (QUEUED, RUNNING)


class EvalJobEventType:
    QUEUED = "queued"
    STARTED = "started"
    STAGE = "stage"
    PROGRESS = "progress"
    WARN = "warn"
    LOG = "log"
    DONE = "done"
    ERROR = "error"

    CHOICES = (
        (QUEUED, "Queued"),
        (STARTED, "Started"),
        (STAGE, "Stage"),
        (PROGRESS, "Progress"),
        (WARN, "Warn"),
        (LOG, "Log"),
        (DONE, "Done"),
        (ERROR, "Error"),
    )


class EvalConfidence:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    CHOICES = (
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
    )


class EvalSubmissionSnapshot(models.Model):
    """평가 시점의 final submission 동결.

    학생이 contest 종료 후 코드를 재제출해도 평가는 이 스냅샷에 묶임.
    같은 (contest, user, problem) 에 대해 한 번에 하나의 스냅샷만 존재.
    """
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="eval_snapshots")
    lecture = models.ForeignKey(Lecture, null=True, on_delete=models.SET_NULL, related_name="+")
    code = models.TextField()
    code_hash = models.CharField(max_length=64, db_index=True)
    language = models.TextField()
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "eval_submission_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["contest", "user", "problem"],
                name="eval_snapshot_unique_per_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["contest", "user"]),
            models.Index(fields=["contest", "problem"]),
        ]


class EvalQualitative(models.Model):
    """정성평가 결과. LLM 1차 호출 결과.

    한 스냅샷당 1건. force 재평가 시 같은 row 를 update_or_create.
    """
    snapshot = models.OneToOneField(
        EvalSubmissionSnapshot,
        on_delete=models.CASCADE,
        related_name="qualitative",
    )
    # 4축 점수 (0-10): correctness, algorithm, readability, problem_understanding
    scores = JSONField(default=dict)
    # 4축 코멘트 (각 축마다 {assessment, suggestion})
    comments = JSONField(default=dict)
    # 산식으로 재계산된 합산 점수 (0-100)
    overall = models.IntegerField(null=True)
    # 산식으로 계산된 제안 부분점수 (problem.total_score 기준)
    suggested_partial_score = models.IntegerField(null=True)
    summary = models.TextField(blank=True, default="")

    model_used = models.TextField(blank=True, default="")
    llm_latency_ms = models.IntegerField(null=True)
    error = models.TextField(blank=True, default="")
    raw_response = models.TextField(blank=True, default="")
    # 모델이 응답한 overall/sps 와 산식 결과 차이 기록 (감사용)
    recomputed = JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "eval_qualitative"
        indexes = [
            models.Index(fields=["updated_at"]),
        ]


class EvalAIUsage(models.Model):
    """AI 사용 가능성 평가. LLM 2차 호출 결과.

    점수 계산과 분리 — counter_signals 까지 함께 보관해 한쪽 관점으로 추론 안 하도록.
    """
    snapshot = models.OneToOneField(
        EvalSubmissionSnapshot,
        on_delete=models.CASCADE,
        related_name="ai_usage",
    )
    likelihood_score = models.IntegerField(null=True)  # 0-100
    confidence = models.CharField(
        max_length=8, choices=EvalConfidence.CHOICES, default=EvalConfidence.LOW
    )
    signals = JSONField(default=list)  # [{category, observation, weight}]
    counter_signals = JSONField(default=list)  # ["..."]
    summary = models.TextField(blank=True, default="")
    disclaimer = models.TextField(blank=True, default="")

    model_used = models.TextField(blank=True, default="")
    llm_latency_ms = models.IntegerField(null=True)
    error = models.TextField(blank=True, default="")
    raw_response = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "eval_ai_usage"


class EvalJob(models.Model):
    """평가 작업 단위.

    1 contest 당 active(queued/running) 인 job 은 partial unique constraint 로 1개로 강제.
    여러 사용자가 같은 contest 를 force=False 트리거 → 두 번째는 IntegrityError →
    catch 후 기존 job 에 EvalJobRequester 합류 (사이드카의 _active_by_contest 와 동등).
    """
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name="eval_jobs")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="eval_jobs")

    status = models.CharField(
        max_length=16, choices=EvalJobStatus.CHOICES, default=EvalJobStatus.QUEUED, db_index=True
    )
    force = models.BooleanField(default=False)

    n_total = models.IntegerField(default=0)
    n_done = models.IntegerField(default=0)
    n_failed = models.IntegerField(default=0)

    enqueued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "eval_job"
        constraints = [
            # active(queued/running) 인 job 은 contest 당 1개로 제한.
            # partial unique index — Postgres 의 condition 지원 활용
            models.UniqueConstraint(
                fields=["contest"],
                condition=models.Q(status__in=("queued", "running")),
                name="eval_job_unique_active_per_contest",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "enqueued_at"]),
            models.Index(fields=["lecture", "status"]),
        ]


class EvalJobRequester(models.Model):
    """같은 job 에 합류한 사용자들.

    프론트에서 '내 작업' 표시 / MyJobsBanner 식별에 사용.
    """
    job = models.ForeignKey(EvalJob, on_delete=models.CASCADE, related_name="requesters")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "eval_job_requester"
        unique_together = (("job", "user"),)


class EvalJobEvent(models.Model):
    """Job 진행 이벤트.

    폴링 응답으로 최근 N개를 노출. SSE 영속화 대용.
    Job 종료 후에도 감사 목적으로 보존 (자동 삭제는 별도 retention 정책).
    """
    job = models.ForeignKey(EvalJob, on_delete=models.CASCADE, related_name="events")
    ts = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=16, choices=EvalJobEventType.CHOICES)
    data = JSONField(default=dict)

    class Meta:
        db_table = "eval_job_event"
        indexes = [
            models.Index(fields=["job", "ts"]),
        ]


class EvalConfig(models.Model):
    """LLM 정성평가 운영 옵션. 단일 row(id=1)만 사용 (singleton pattern).

    런타임에 admin 이 GUI 로 변경 → Redis key 즉시 갱신 → actor 가 다음 acquire 시 반영.
    """
    max_concurrent_eval_jobs = models.IntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "eval_config"

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
