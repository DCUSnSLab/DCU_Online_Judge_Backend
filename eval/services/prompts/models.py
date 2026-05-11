"""평가용 데이터 클래스. SideProject 의 llm_code_review.models 와 동일."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProblemMeta:
    label: str
    title: str
    description: str
    input_description: str
    output_description: str
    samples: list
    hint: str | None
    languages: list
    time_limit: int
    memory_limit: int
    difficulty: str
    total_score: int


@dataclass(frozen=True)
class FinalSubmissionRow:
    submission_id: str
    user_id: int
    username: str
    problem_label: str
    problem_id: int
    language: str
    result: int
    result_label: str
    score: int | None
    time_cost_ms: int | None
    memory_cost_kb: int | None
    create_time: str | None
    final_code_path: str = ""


@dataclass(frozen=True)
class EvalTask:
    problem: ProblemMeta
    submission: FinalSubmissionRow
    code: str


@dataclass
class Evaluation:
    scores: dict
    comments: dict
    overall: int
    summary: str
    suggested_partial_score: int
    raw_response: str = ""
    llm_latency_ms: int = 0
    model_used: str = ""
    error: str | None = None
    recomputed: dict = field(default_factory=dict)


@dataclass
class AIUsageSignal:
    category: str
    observation: str
    weight: str  # low | medium | high


@dataclass
class AIUsageAssessment:
    likelihood_score: int
    confidence: str
    signals: list
    counter_signals: list
    summary: str
    disclaimer: str
    raw_response: str = ""
    llm_latency_ms: int = 0
    model_used: str = ""
    error: str | None = None
