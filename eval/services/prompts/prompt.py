"""정성평가 prompt builders. SideProject 그대로 (import path 만 변경)."""
from __future__ import annotations

import json
import re
from html import unescape

from .models import EvalTask
from .rubric import (
    AXES,
    AXIS_CHECKLISTS,
    AXIS_DESCRIPTIONS,
    AXIS_RANGE,
    OVERALL_FORMULA_TEXT,
    PARTIAL_FORMULA_TEXT,
)


_HTML_TAG = re.compile(r"<[^>]+>")
_LANG_MD = {
    "C": "c", "C++": "cpp", "Java": "java", "Python3": "python", "Python2": "python",
    "Go": "go", "Rust": "rust", "JavaScript": "javascript", "Kotlin": "kotlin", "C#": "csharp",
}


def html_to_text(s):
    if not s:
        return ""
    s = unescape(s)
    s = _HTML_TAG.sub(" ", s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


SYSTEM_PRINCIPLES = f"""당신은 프로그래밍 과목의 조교(TA)입니다. 학생이 제출한 코드를 정성적으로 평가합니다.

[출력 형식 — 절대 규칙]
- 응답은 단일 JSON 객체로만 출력합니다.
- JSON 외 다른 텍스트(설명, 마크다운, ``` 펜스 포함)를 절대 포함하지 마세요.
- 코멘트와 summary는 한국어 자연스러운 문체로, 학생이 이해할 수 있는 용어로 작성합니다.

[평가 일반 원칙]
- testcase 통과 여부는 자동 채점 결과로 별도 제공됩니다. 정성 평가는 testcase 통과 여부와 **독립적**으로, 코드 자체의 품질을 봅니다.
- 평가 강도는 문제의 `difficulty` 와 학습 단계에 비례합니다. 입문 난이도 문제에서 함수 분리 부재·고급 기법 미사용 등을 큰 감점 요인으로 삼지 마세요.
- 추상적 평가("좋다", "나쁘다", "가독성이 떨어진다")만으로 끝내지 말고, 항상 학생이 실제로 무엇을 고치면 되는지 또는 무엇이 왜 좋은지 구체적으로 적습니다.

[점수 산출 — 자의적 계산 금지]
- 각 축은 0~10의 정수.
- {OVERALL_FORMULA_TEXT}
- {PARTIAL_FORMULA_TEXT}
- 위 산식은 후처리에서 다시 검증·재계산되어 응답 값이 산식과 다르면 산식 값으로 강제로 대체됩니다.

[코멘트 형식]
- 각 축의 코멘트는 두 키를 모두 채웁니다:
  - `assessment`: 현재 상태 평가 (잘된 점 또는 문제점, 1~2문장)
  - `suggestion`: 만점이 아니면 "어떻게 고치면 되는지" 구체적 개선 방향. 만점이면 "왜 좋은지" 짧게.
- 두 키 중 하나라도 비어 있거나 추상적이면 응답을 다시 생성합니다.
"""


def build_axis_checklists():
    parts = ["[축별 평가 체크리스트 — 일반 원칙. 모든 항목은 testcase 결과와 독립적]"]
    for axis in AXES:
        parts.append(f"\n■ {axis} — {AXIS_DESCRIPTIONS[axis]}")
        for item in AXIS_CHECKLISTS[axis]:
            parts.append(f"  · {item}")
    return "\n".join(parts)


_AXIS_CHECKLISTS_BLOCK = build_axis_checklists()


def _samples_block(samples):
    if not samples:
        return "(예제 없음)"
    parts = []
    for i, s in enumerate(samples, 1):
        inp = (s.get("input") or "").rstrip()
        outp = (s.get("output") or "").rstrip()
        parts.append(f"예제 {i}:\n  입력: {inp}\n  출력: {outp}")
    return "\n".join(parts)


def build_problem_block(task):
    p = task.problem
    return f"""[문제]
{p.label} (난이도 {p.difficulty}, 배점 {p.total_score})
제목: {p.title}

설명:
{html_to_text(p.description)}

입력 형식:
{html_to_text(p.input_description)}

출력 형식:
{html_to_text(p.output_description)}

{_samples_block(p.samples)}

[자동 채점 결과 — 정성 평가는 이 결과와 독립적]
결과: {task.submission.result_label}   testcase 점수: {task.submission.score if task.submission.score is not None else "-"}/{p.total_score}
시간: {task.submission.time_cost_ms if task.submission.time_cost_ms is not None else "-"} ms   메모리: {task.submission.memory_cost_kb if task.submission.memory_cost_kb is not None else "-"} KB
"""


def build_code_block(task):
    s = task.submission
    lang_md = _LANG_MD.get(s.language, "")
    return f"""[학생 코드]
사용자: {s.username}   언어: {s.language}
```{lang_md}
{task.code}
```
"""


def build_evaluation_instructions(task):
    return f"""[평가 지시]
- 위 [축별 평가 체크리스트]를 기준으로 각 축에 0~10 정수 점수를 매기고, 두 키(`assessment`, `suggestion`)를 모두 한국어로 채웁니다.
- `overall` 과 `suggested_partial_score` 는 시스템 프롬프트의 산식대로 계산하여 채워주세요.
  ({OVERALL_FORMULA_TEXT})
  (suggested_partial_score = round(total_score * (correctness + problem_understanding) / 20), 본 문제는 total_score = {task.problem.total_score})
- 응답은 다음 JSON 스키마를 따르는 단일 JSON 객체로만 출력합니다. 다른 어떤 텍스트도 출력하지 마세요.
"""


def build_response_schema(task):
    schema_doc = {
        "scores": {a: f"int in [{AXIS_RANGE[0]},{AXIS_RANGE[1]}]" for a in AXES},
        "comments": {
            a: {"assessment": "string (한국어 1~2문장, 비공백 필수)", "suggestion": "string (한국어 1~2문장, 비공백 필수)"}
            for a in AXES
        },
        "overall": "int in [0,100] — 산식 적용 결과",
        "summary": "string (한국어 2~3문장 종합 평)",
        "suggested_partial_score": f"int in [0,{task.problem.total_score}] — 산식 적용 결과",
    }
    example = {
        "scores": {a: 7 for a in AXES},
        "comments": {a: {"assessment": "예시: 현재 상태에 대한 한국어 평가 한두 문장.", "suggestion": "예시: 구체적 개선 방향 한두 문장."} for a in AXES},
        "overall": 70,
        "summary": "예시: 종합 평 두세 문장.",
        "suggested_partial_score": min(task.problem.total_score, max(0, round(task.problem.total_score * 0.7))),
    }
    return (
        "스키마(타입·범위만):\n"
        + json.dumps(schema_doc, ensure_ascii=False, indent=2)
        + "\n\n중요: `comments` 의 각 축은 반드시 두 개의 서브키 `assessment`, `suggestion` 을 가지는 객체입니다.\n"
        "절대 평탄(flat) 문자열로 만들지 말고, 절대 `assessment`/`suggestion` 을 `comments` 바로 아래에 두지 마세요.\n"
        "즉, 올바른 형태는 `comments.correctness.assessment`, `comments.correctness.suggestion` 처럼 두 단계 깊이입니다.\n\n"
        "정확한 형태의 예시(채울 값은 학생 코드에 맞게 작성):\n"
        + json.dumps(example, ensure_ascii=False, indent=2)
    )


def build_user_prompt(task):
    return (
        build_problem_block(task)
        + "\n"
        + build_code_block(task)
        + "\n"
        + _AXIS_CHECKLISTS_BLOCK
        + "\n\n"
        + build_evaluation_instructions(task)
        + "\n"
        + build_response_schema(task)
    )


def build_messages(task):
    return [
        {"role": "system", "content": SYSTEM_PRINCIPLES},
        {"role": "user", "content": build_user_prompt(task)},
    ]
