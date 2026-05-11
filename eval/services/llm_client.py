"""DCUCODE LLM Gateway HTTP wrapper.

SideProject 의 dcu_llm.LLMClient (onprem Qwen 직접) 를 DCUCODE 운영 패턴 (LLM Gateway)
으로 교체. 기존 llm/views/oj.py 의 환경변수 패턴과 동일:
- LLM_GATEWAY_BASE_URL (기본 http://dcucode-llm-gateway:18000)
- LLM_GATEWAY_API_KEY_FILE (파일 우선)
- LLM_GATEWAY_API_KEY (env fallback)
- LLM_GATEWAY_CHAT_COMPLETIONS_URL (직접 override)

LLM Gateway 는 OpenAI 호환 /v1/chat/completions 를 노출.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from django.conf import settings


class LLMClientError(Exception):
    pass


def _data_dir():
    return getattr(settings, "DATA_DIR", "/data")


def _load_api_key():
    key_file = os.environ.get("LLM_GATEWAY_API_KEY_FILE") or os.path.join(_data_dir(), "config", "llm_gateway_api_key")
    p = Path(key_file)
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return os.environ.get("LLM_GATEWAY_API_KEY", "")


def _default_base():
    return (os.environ.get("LLM_GATEWAY_BASE_URL") or "http://dcucode-llm-gateway:18000").rstrip("/")


def _completions_url():
    explicit = os.environ.get("LLM_GATEWAY_CHAT_COMPLETIONS_URL")
    if explicit:
        return explicit
    return f"{_default_base()}/v1/chat/completions"


def _default_model():
    return os.environ.get("EVAL_LLM_DEFAULT_MODEL") or os.environ.get("LLM_DEFAULT_MODEL") or "default"


class LLMClient:
    """SideProject dcu_llm.LLMClient 호환 인터페이스 (complete only)."""

    def __init__(self, base_url=None, api_key=None, default_model=None, timeout=60):
        self.base_url = base_url or _default_base()
        self.api_key = api_key if api_key is not None else _load_api_key()
        self.default_model = default_model or _default_model()
        self.completions_url = _completions_url()
        self.timeout = timeout

    def complete(self, messages, *, model=None, temperature=0.2, max_tokens=2048, extra_body=None):
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra_body:
            # OpenAI 호환 client 가 다 받아주는 건 아니지만, vLLM/내부 게이트웨이는 통과
            payload.update(extra_body)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = requests.post(self.completions_url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMClientError(f"LLM gateway unreachable: {e}") from e
        if r.status_code != 200:
            raise LLMClientError(f"LLM gateway returned {r.status_code}: {r.text[:300]}")
        try:
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise LLMClientError(f"Bad LLM response: {e}") from e
