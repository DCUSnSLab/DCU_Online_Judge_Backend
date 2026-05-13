"""DCUCODE LLM Gateway HTTP wrapper.

정성평가 전용 LLM 설정은 /data/config/eval_llm_* 파일에서 읽음 — 기존
llm_gateway_api_key/llm_gateway_model 패턴과 동일.

읽는 우선순위 (각 항목 모두 동일):
  1) /data/config/eval_llm_api_key | eval_llm_model | eval_llm_url  (파일)
  2) LLM_GATEWAY_API_KEY_FILE / LLM_GATEWAY_API_KEY env
     EVAL_LLM_DEFAULT_MODEL / LLM_DEFAULT_MODEL env
     LLM_GATEWAY_CHAT_COMPLETIONS_URL / LLM_GATEWAY_BASE_URL env
  3) 기존 llm 앱 fallback (/data/config/llm_gateway_api_key, dcucode-llm-gateway:18000)

운영에서는 PVC `/data` 안의 파일이 SoT — git/manifest 노출 없음. dev 도 동일 패턴.
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


def _read_text_file(path):
    """텍스트 파일 한 줄 읽기. 없거나 비어있으면 None."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        val = p.read_text(encoding="utf-8").strip()
        return val or None
    except OSError:
        return None


def _eval_config_path(name):
    return os.path.join(_data_dir(), "config", f"eval_llm_{name}")


def _load_api_key():
    # 1) eval 전용 파일
    v = _read_text_file(_eval_config_path("api_key"))
    if v:
        return v
    # 2) env (LLM_GATEWAY_API_KEY_FILE > LLM_GATEWAY_API_KEY)
    env_key_file = os.environ.get("LLM_GATEWAY_API_KEY_FILE")
    if env_key_file:
        v = _read_text_file(env_key_file)
        if v:
            return v
    env_key = os.environ.get("LLM_GATEWAY_API_KEY")
    if env_key:
        return env_key
    # 3) 기존 llm 앱 파일 fallback
    v = _read_text_file(os.path.join(_data_dir(), "config", "llm_gateway_api_key"))
    return v or ""


def _default_model():
    # 1) eval 전용 파일
    v = _read_text_file(_eval_config_path("model"))
    if v:
        return v
    # 2) env
    env_model = os.environ.get("EVAL_LLM_DEFAULT_MODEL") or os.environ.get("LLM_DEFAULT_MODEL")
    if env_model:
        return env_model
    # 3) 기존 채팅용 llm 모델 파일 fallback (다른 모델일 수 있음)
    v = _read_text_file(os.path.join(_data_dir(), "config", "llm_gateway_model"))
    return v or "default"


def _default_base():
    # DCUCODE 운영 gateway 는 자체 FastAPI proxy 라 base 가 service hostname:port.
    # K8s 운영의 hostname 은 NS 포함 (vllm-workspace 등) — 그건 manifest env 로 override.
    return (os.environ.get("LLM_GATEWAY_BASE_URL") or "http://dcucode-llm-gateway:18000").rstrip("/")


def _completions_url():
    # 1) eval 전용 파일 — 완전한 URL 한 줄 (path 까지)
    v = _read_text_file(_eval_config_path("url"))
    if v:
        return v
    # 2) env (전체 URL 직접 지정)
    explicit = os.environ.get("LLM_GATEWAY_CHAT_COMPLETIONS_URL")
    if explicit:
        return explicit
    # 3) base url + 운영 gateway 의 path prefix ("/llm/v1/chat/completions").
    # DCUCODE LLM Gateway FastAPI proxy 가 /llm 아래에 모든 OpenAI 호환 endpoint 를 노출.
    # 1, 2 가 비었을 때만 사용되는 안전망 — 파일 한 줄로 override 권장.
    return f"{_default_base()}/llm/v1/chat/completions"


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
