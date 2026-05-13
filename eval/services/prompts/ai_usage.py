"""AI 사용 가능성 평가. SideProject 그대로 (import path 만 변경)."""
from __future__ import annotations

import json
import logging

from .llm import LLMResponseError, extract_json_object
from .models import AIUsageAssessment, AIUsageSignal
from .prompt import _LANG_MD, html_to_text

log = logging.getLogger(__name__)


DISCLAIMER_TEXT = (
    "이 평가는 참고 신호일 뿐이며 부정행위 판단의 단독 근거가 아닙니다."
)


_SIGNAL_CATEGORIES = (
    "comment_style", "naming", "structure", "idiom", "consistency",
    "irrelevant_feature", "absence_of_learner_traces", "other",
)

_PERSPECTIVE_HINTS = (
    "주석 스타일·밀도 패턴이 학습 단계에 자연스러운가",
    "난이도 대비 네이밍·추상화 수준이 적절한가 (지나치게 정제되어 있는가)",
    "해당 학습 단계에서 흔히 보이는 관용구의 부재 여부",
    "문제에서 요구하지 않은 방어적 코딩·견고성·일반화가 과도한가",
    "스타일·포맷팅 일관성이 비현실적으로 균일한가",
    "학습자 흔적(시행착오, 일관성 없는 스타일, 주석 처리된 이전 시도)의 존재 여부",
)


SYSTEM_PROMPT = f"""당신은 프로그래밍 과목의 조교(TA)입니다. 학생 제출 코드가 LLM 도움을 받아 작성되었을 가능성을 **참고용으로** 평가합니다.

[중요한 원칙]
- 이 평가는 채점자가 참고하는 보조 신호이며, 부정행위 판단의 단독 근거가 될 수 없습니다.
- LLM 생성 코드를 LLM이 판독하는 작업은 false positive·false negative 가 필연적입니다. 확신할 수 없는 경우 confidence 를 낮추고, counter_signals 도 적극적으로 찾으세요.
- 학생이 LLM 도움 없이 깔끔하게 작성하는 경우도 흔합니다. **잘 정돈된 코드** 자체는 LLM 사용의 결정적 근거가 아닙니다.
- 출력은 단일 JSON 객체로만, 한국어로 작성합니다. 다른 텍스트 일체 금지.

[참고 관점 — 어느 하나도 단독으로는 결정적이지 않음. 종합적으로 고려]
{chr(10).join("- " + h for h in _PERSPECTIVE_HINTS)}

[필수 출력 규칙]
- `signals`: 위 카테고리({", ".join(_SIGNAL_CATEGORIES)}) 중 하나로 분류한 관찰. 각 항목은 `category`, `observation`(관찰한 구체적 사실 1문장), `weight`(low|medium|high).
- `counter_signals`: 가능성을 **낮추는** 관찰들. 0개 이상이지만 키 자체는 반드시 존재. 한쪽 관점에 치우치지 않도록 적극 탐색하세요.
- `confidence`: low|medium|high.
- `likelihood_score`: 0~100 정수. 신호와 반대 신호를 종합한 추정.
- `summary`: 한국어 2~3문장.
- `disclaimer`: 위 문구를 그대로 포함합니다 — "{DISCLAIMER_TEXT}"
"""


def _build_user_prompt(task):
    p = task.problem
    s = task.submission
    lang_md = _LANG_MD.get(s.language, "")
    schema = {
        "likelihood_score": "int [0,100]",
        "confidence": "low | medium | high",
        "signals": [{"category": " | ".join(_SIGNAL_CATEGORIES), "observation": "string (한국어 1문장)", "weight": "low | medium | high"}],
        "counter_signals": ["string (한국어, 0개 이상)"],
        "summary": "string (한국어 2~3문장)",
        "disclaimer": DISCLAIMER_TEXT,
    }
    return f"""[문제 컨텍스트 — 학습 단계 판단용]
{p.label} (난이도 {p.difficulty}, 배점 {p.total_score})
제목: {p.title}
설명 요약: {html_to_text(p.description)[:300]}

[학생 코드]
사용자: {s.username}   언어: {s.language}
```{lang_md}
{task.code}
```

[지시]
- 위 코드가 LLM 도움을 받아 작성되었을 가능성을 0~100 정수로 추정하세요.
- 신호(`signals`)와 반대 신호(`counter_signals`)를 균형 있게 모두 적습니다.
- counter_signals 는 빈 배열이라도 키는 반드시 포함하고, 가급적 1개 이상 채우려 노력하세요.
- 응답은 다음 JSON 스키마를 따르는 단일 JSON 객체로만 출력하세요. 다른 어떤 텍스트도 출력하지 마세요.

{json.dumps(schema, ensure_ascii=False, indent=2)}
"""


def build_messages(task):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(task)},
    ]


def _check_str(v, where, *, allow_empty=False):
    if not isinstance(v, str):
        raise LLMResponseError(f"{where} must be a string")
    if not allow_empty and not v.strip():
        raise LLMResponseError(f"{where} must be non-empty")
    return v.strip()


def parse_response(text):
    data = extract_json_object(text)
    try:
        likelihood = max(0, min(100, int(data.get("likelihood_score"))))
    except (TypeError, ValueError):
        raise LLMResponseError(f"likelihood_score not int: {data.get('likelihood_score')!r}")

    confidence = _check_str(data.get("confidence"), "confidence").lower()
    if confidence not in ("low", "medium", "high"):
        raise LLMResponseError(f"confidence must be low|medium|high, got {confidence!r}")

    signals_raw = data.get("signals")
    if not isinstance(signals_raw, list):
        raise LLMResponseError("signals must be a list")
    signals = []
    for i, s in enumerate(signals_raw):
        if not isinstance(s, dict):
            raise LLMResponseError(f"signals[{i}] must be object")
        cat = _check_str(s.get("category"), f"signals[{i}].category").lower()
        if cat not in _SIGNAL_CATEGORIES:
            cat = "other"
        weight = _check_str(s.get("weight"), f"signals[{i}].weight").lower()
        if weight not in ("low", "medium", "high"):
            weight = "low"
        signals.append(AIUsageSignal(
            category=cat,
            observation=_check_str(s.get("observation"), f"signals[{i}].observation"),
            weight=weight,
        ))

    counter_signals_raw = data.get("counter_signals")
    if counter_signals_raw is None or not isinstance(counter_signals_raw, list):
        raise LLMResponseError("counter_signals must be a list (key required, even if empty)")
    counter_signals = [_check_str(c, f"counter_signals[{i}]") for i, c in enumerate(counter_signals_raw)]

    return {
        "likelihood_score": likelihood,
        "confidence": confidence,
        "signals": signals,
        "counter_signals": counter_signals,
        "summary": _check_str(data.get("summary"), "summary"),
        "disclaimer": DISCLAIMER_TEXT,
    }


def make_assessment(parsed, *, raw, latency_ms, model):
    return AIUsageAssessment(
        likelihood_score=parsed["likelihood_score"],
        confidence=parsed["confidence"],
        signals=parsed["signals"],
        counter_signals=parsed["counter_signals"],
        summary=parsed["summary"],
        disclaimer=parsed["disclaimer"],
        raw_response=raw,
        llm_latency_ms=latency_ms,
        model_used=model,
    )


def make_failed_assessment(error, *, model):
    return AIUsageAssessment(
        likelihood_score=0,
        confidence="low",
        signals=[],
        counter_signals=[],
        summary="",
        disclaimer=DISCLAIMER_TEXT,
        raw_response="",
        llm_latency_ms=0,
        model_used=model,
        error=error,
    )
