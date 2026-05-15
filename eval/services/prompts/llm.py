"""LLM 응답 파싱 + retry. SideProject llm_code_review.llm 에서 LLMClient 만 교체.

LLMClient: dcu_llm 의 onprem Qwen client → DCUCODE LLM Gateway HTTP wrapper.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

from ..llm_client import LLMClient, LLMClientError
from .rubric import AXES, overall_score, partial_score

log = logging.getLogger(__name__)


def _read_retries_default():
    """env override 가능. 잘못된 값이면 기본 3 사용."""
    raw = os.environ.get("EVAL_LLM_RETRIES", "3")
    try:
        return max(0, int(raw))
    except ValueError:
        return 3


# 정성평가/AI 사용 평가 두 호출 모두에서 사용하는 retries 기본값.
# 초회 + N 회 재시도 = 총 (N+1) 회 호출. 기본 3 → 총 4 회.
# LLM 의 일시적 JSON 형식 오류(컴마 누락 등) 흡수율을 높이는 게 목적.
RETRIES_DEFAULT = _read_retries_default()


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMResponseError(Exception):
    pass


# Qwen3 chat template option to disable reasoning content (the "thinking" mode).
QWEN_NO_THINK_EXTRA = {"chat_template_kwargs": {"enable_thinking": False}}


def _strip_fence(s):
    m = _FENCE.search(s)
    return m.group(1) if m else s


def _largest_json_object(s):
    best = None
    depth = 0
    start = -1
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    span = (start, i + 1)
                    if best is None or (span[1] - span[0]) > (best[1] - best[0]):
                        best = span
    return s[best[0] : best[1]] if best else None


def extract_json_object(text):
    raw = _strip_fence(text).strip()
    candidate = raw if raw.startswith("{") else _largest_json_object(text)
    if not candidate:
        raise LLMResponseError("no JSON object in response")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LLMResponseError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise LLMResponseError("response is not a JSON object")
    return data


def _check_nonempty_str(value, where):
    if not isinstance(value, str) or not value.strip():
        raise LLMResponseError(f"{where} must be a non-empty string")
    return value.strip()


def parse_response(text, *, total_score):
    """정성평가 응답 파싱 + 산식 강제 재계산."""
    data = extract_json_object(text)
    scores = data.get("scores")
    comments = data.get("comments")
    if not isinstance(scores, dict) or not isinstance(comments, dict):
        raise LLMResponseError("missing 'scores' or 'comments' object")

    norm_scores = {}
    norm_comments = {}
    for axis in AXES:
        v = scores.get(axis)
        try:
            iv = int(v)
        except (TypeError, ValueError):
            raise LLMResponseError(f"score for '{axis}' is not an int: {v!r}")
        norm_scores[axis] = max(0, min(10, iv))

        cobj = comments.get(axis)
        if not isinstance(cobj, dict):
            raise LLMResponseError(f"comments['{axis}'] must be an object with 'assessment' and 'suggestion'")
        norm_comments[axis] = {
            "assessment": _check_nonempty_str(cobj.get("assessment"), f"comments['{axis}'].assessment"),
            "suggestion": _check_nonempty_str(cobj.get("suggestion"), f"comments['{axis}'].suggestion"),
        }

    canonical_overall = overall_score(norm_scores)
    canonical_sps = partial_score(total_score, norm_scores)

    model_overall = data.get("overall")
    model_sps = data.get("suggested_partial_score")
    try:
        model_overall_int = int(model_overall) if model_overall is not None else None
    except (TypeError, ValueError):
        model_overall_int = None
    try:
        model_sps_int = int(model_sps) if model_sps is not None else None
    except (TypeError, ValueError):
        model_sps_int = None

    recomputed = {}
    if model_overall_int is None or model_overall_int != canonical_overall:
        recomputed["overall"] = {
            "model": model_overall_int,
            "formula": canonical_overall,
            "diff": (canonical_overall - model_overall_int) if model_overall_int is not None else None,
        }
    if model_sps_int is None or model_sps_int != canonical_sps:
        recomputed["suggested_partial_score"] = {
            "model": model_sps_int,
            "formula": canonical_sps,
            "diff": (canonical_sps - model_sps_int) if model_sps_int is not None else None,
        }

    return {
        "scores": norm_scores,
        "comments": norm_comments,
        "overall": canonical_overall,
        "summary": _check_nonempty_str(data.get("summary"), "summary"),
        "suggested_partial_score": canonical_sps,
        "recomputed": recomputed,
    }


def _backoff(attempt):
    return min(8.0, 1.5 ** attempt)


def call_with_retry(
    client,
    messages,
    *,
    parser,
    model,
    temperature,
    max_tokens,
    retries,
):
    """LLM 호출 + retry. (parsed, raw_text, latency_ms) 반환."""
    last_err = None
    last_raw = ""
    for attempt in range(retries + 1):
        try:
            t0 = time.monotonic()
            text = client.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=QWEN_NO_THINK_EXTRA,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            last_raw = text
            parsed = parser(text)
            return parsed, text, latency_ms
        except LLMResponseError as e:
            last_err = e
            log.warning("attempt %d/%d: parse error: %s", attempt + 1, retries + 1, e)
        except LLMClientError as e:
            last_err = e
            log.warning("attempt %d/%d: client error: %s", attempt + 1, retries + 1, e)
        if attempt < retries:
            time.sleep(_backoff(attempt))
    err = last_err if last_err else LLMResponseError("unknown failure")
    setattr(err, "last_raw", last_raw)
    raise err
