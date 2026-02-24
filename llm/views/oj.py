import json
import logging

import requests
from django.http import HttpResponse, StreamingHttpResponse

from account.decorators import login_required
from utils.api import APIView
from utils.shortcuts import get_env

logger = logging.getLogger(__name__)


def _read_gateway_api_key():
    key_file = get_env("LLM_GATEWAY_API_KEY_FILE", "/data/config/llm_gateway_api_key")
    try:
        with open(key_file, "r") as f:
            key_from_file = f.read().strip()
            if key_from_file:
                return key_from_file
    except OSError:
        logger.warning("LLM gateway key file not found: %s", key_file)
    return get_env("LLM_GATEWAY_API_KEY", "").strip()


def _build_gateway_url():
    explicit_url = get_env("LLM_GATEWAY_CHAT_COMPLETIONS_URL", "").strip()
    if explicit_url:
        return explicit_url
    base_url = get_env("LLM_GATEWAY_BASE_URL", "http://dcucode-llm-gateway:18000").rstrip("/")
    return f"{base_url}/llm/v1/chat/completions"


def _read_default_model():
    model_file = get_env("LLM_DEFAULT_MODEL_FILE", "/data/config/llm_gateway_model")
    try:
        with open(model_file, "r") as f:
            model_from_file = f.read().strip()
            if model_from_file:
                return model_from_file
    except OSError:
        pass
    return get_env("LLM_DEFAULT_MODEL", "").strip()


def _json_resp(payload, status=200):
    return HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
    )


class LLMChatCompletionsAPI(APIView):
    @login_required
    def post(self, request):
        raw_payload = request.data
        if not isinstance(raw_payload, dict):
            return _json_resp({"error": "invalid-request", "data": "Invalid request body"}, status=400)
        payload = dict(raw_payload)
        if not isinstance(payload.get("messages"), list) or not payload.get("messages"):
            return _json_resp({"error": "invalid-request", "data": "messages is required"}, status=400)

        default_model = _read_default_model()
        if default_model:
            payload["model"] = default_model
        elif not payload.get("model"):
            return _json_resp({"error": "invalid-request", "data": "model is required"}, status=400)

        gateway_key = _read_gateway_api_key()
        if not gateway_key:
            return _json_resp(
                {"error": "gateway-misconfigured", "data": "LLM gateway api key is not configured"},
                status=500,
            )

        gateway_url = _build_gateway_url()
        stream = bool(payload.get("stream", False))
        timeout_sec = float(get_env("LLM_GATEWAY_TIMEOUT_SEC", "300"))
        headers = {
            "Authorization": f"Bearer {gateway_key}",
            "Content-Type": "application/json",
        }

        try:
            upstream = requests.post(
                gateway_url,
                headers=headers,
                data=json.dumps(payload),
                stream=stream,
                timeout=timeout_sec,
            )
        except requests.RequestException as e:
            logger.exception("Failed to call gateway: %s", e)
            return _json_resp({"error": "gateway-unavailable", "data": "Failed to connect to llm gateway"}, status=502)

        if not stream:
            content_type = upstream.headers.get("Content-Type", "application/json")
            return HttpResponse(
                upstream.content,
                status=upstream.status_code,
                content_type=content_type,
            )

        if upstream.status_code >= 400:
            body = upstream.content
            content_type = upstream.headers.get("Content-Type", "application/json")
            upstream.close()
            return HttpResponse(body, status=upstream.status_code, content_type=content_type)

        def stream_iter():
            try:
                for chunk in upstream.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        resp = StreamingHttpResponse(
            streaming_content=stream_iter(),
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "text/event-stream"),
        )
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp
