"""4축 산식. SideProject llm_code_review.rubric 그대로."""
from __future__ import annotations

from dataclasses import dataclass


AXES = ("correctness", "algorithm", "readability", "problem_understanding")

AXIS_DESCRIPTIONS = {
    "correctness": "정상 입출력 + 코너케이스 처리. testcase 통과 여부와 별개의 코드 단위 정합성.",
    "algorithm": "접근 방식이 문제 의도에 맞는지, 시간/공간 적합성.",
    "readability": "네이밍·들여쓰기·함수 분리·주석 등 코드 가독성.",
    "problem_understanding": "요구사항·제약조건 반영도 (입출력 형식, 단위, 정밀도 등).",
}

AXIS_CHECKLISTS = {
    "correctness": (
        "변수·배열의 초기화 완전성 (사용 전 값 보장)",
        "리턴값·종료 조건 처리",
        "입출력 형식 정확성 — 공백·개행·정밀도(소수점 자릿수 등)",
        "입력 처리 정합성 — scanf 포맷 문자열·포인터·인덱스 범위",
        "미정의 동작 가능성 — 배열 경계 초과, 미초기화 변수, 0 나눗셈, 정수 오버플로우",
        "코너·경계 케이스 — 입력 최솟/최댓값, 빈 입력, 동일값 반복",
        "**testcase 통과 여부와 독립적으로 평가**",
    ),
    "algorithm": (
        "접근 방식이 문제가 요구하는 로직과 일치하는가",
        "시간 복잡도가 입력 규모·시간 제한에 적합한가",
        "공간 복잡도가 메모리 제한 안에서 안전한가",
        "불필요한 연산·중복 계산이 있는가",
        "사용한 자료구조 선택이 합리적인가",
    ),
    "readability": (
        "변수·함수 이름이 의도를 드러내는가",
        "들여쓰기·중괄호·공백이 일관되어 있는가",
        "함수·루프 분리가 가독성에 도움이 되는가 (난이도가 낮으면 분리 부재를 큰 감점으로 삼지 말 것)",
        "주석이 의도 전달에 적절한가 (없어도 자명하면 무방)",
        "중복된 코드 블록을 잘 묶었는가",
    ),
    "problem_understanding": (
        "입력 형식·개수·타입을 정확히 반영했는가",
        "출력 형식·단위·정밀도를 정확히 반영했는가",
        "문제의 특수 조건(예: '홀수 번째만', '소수점 둘째 자리') 누락 여부",
        "예제 입출력과 일치하는가",
        "제약조건(범위·시간·메모리)이 코드에 반영되었는가",
    ),
}

AXIS_RANGE = (0, 10)
AXIS_MAX = AXIS_RANGE[1]
AXIS_TOTAL_MAX = AXIS_MAX * len(AXES)

OVERALL_FORMULA_TEXT = (
    "overall = round( (correctness + algorithm + readability + problem_understanding) / 40 * 100 )"
)
PARTIAL_FORMULA_TEXT = (
    "suggested_partial_score = round( total_score * (correctness + problem_understanding) / 20 )\n"
    "  (algorithm, readability 는 부분점수 계산에 영향을 주지 않습니다 — 스타일·접근 적절성은 부분점수의 결정 변수가 아님)"
)


def overall_score(scores):
    total = sum(int(scores.get(a, 0)) for a in AXES)
    return round(total / AXIS_TOTAL_MAX * 100)


def partial_score(total_score, scores):
    if total_score <= 0:
        return 0
    c = int(scores.get("correctness", 0))
    p = int(scores.get("problem_understanding", 0))
    raw = total_score * (c + p) / (2 * AXIS_MAX)
    return max(0, min(int(total_score), round(raw)))


@dataclass(frozen=True)
class Rubric:
    axes: tuple = AXES
    range_min: int = AXIS_RANGE[0]
    range_max: int = AXIS_RANGE[1]
    descriptions: dict = None  # type: ignore[assignment]


DEFAULT_RUBRIC = Rubric(descriptions=AXIS_DESCRIPTIONS)
