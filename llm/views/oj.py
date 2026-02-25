import json
import logging

import requests
from django.http import HttpResponse, StreamingHttpResponse

from account.decorators import login_required
from utils.api import APIView, validate_serializer
from utils.shortcuts import get_env

from ..models import LLMChatMessage, LLMChatMessageRole, LLMChatSession
from ..serializers import (
    LLMChatCompletionsSerializer,
    LLMChatMessageSerializer,
    LLMChatMessagesQuerySerializer,
    LLMChatSessionCreateSerializer,
    LLMChatSessionDeleteSerializer,
    LLMChatSessionSerializer,
    LLMChatSessionUpdateSerializer,
)

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "You are a helpful programming assistant. Answer briefly, clearly, and in Korean unless user asks otherwise."


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


def _read_system_prompt():
    return get_env("LLM_CHAT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT


def _json_resp(payload, status=200):
    return HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
    )


def _serializer_error(serializer):
    if not serializer.errors:
        return "Invalid request"
    first_key = list(serializer.errors.keys())[0]
    first_err = serializer.errors[first_key]
    if isinstance(first_err, list) and first_err:
        first_err = first_err[0]
    return f"{first_key}: {first_err}"


def _extract_assistant_content(response_json):
    choices = response_json.get("choices") or []
    if not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    text = first.get("text")
    return text if isinstance(text, str) else ""


def _extract_usage(response_json):
    usage = response_json.get("usage") or {}
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def _touch_session(session, extra_fields=None):
    update_fields = ["updated_at"]
    if extra_fields:
        for field in extra_fields:
            if field not in update_fields:
                update_fields.append(field)
    session.save(update_fields=update_fields)


def _recent_messages_for_prompt(session, recent_count=10):
    rows = list(
        LLMChatMessage.objects.filter(session=session)
        .order_by("-id")[:recent_count]
    )
    rows.reverse()
    return [
        {"role": row.role, "content": row.content}
        for row in rows
        if row.role in (LLMChatMessageRole.USER, LLMChatMessageRole.ASSISTANT, LLMChatMessageRole.SYSTEM)
    ]


def _build_gateway_payload(session, data):
    model_name = data.get("model") or session.model_name or _read_default_model()
    messages = [{"role": "system", "content": _read_system_prompt()}]
    messages.extend(_recent_messages_for_prompt(session))
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 1024),
        "stream": bool(data.get("stream", True)),
    }
    return payload


class LLMChatSessionAPI(APIView):
    @login_required
    def get(self, request):
        session_id = request.GET.get("id")
        queryset = LLMChatSession.objects.filter(user=request.user).order_by("-updated_at")

        if session_id:
            session = queryset.filter(id=session_id).first()
            if not session:
                return self.error("Chat session does not exist")
            return self.success(LLMChatSessionSerializer(session).data)

        if request.GET.get("paging") == "true":
            data = self.paginate_data(request, queryset, LLMChatSessionSerializer)
            return self.success(data)
        return self.success(LLMChatSessionSerializer(queryset, many=True).data)

    @login_required
    @validate_serializer(LLMChatSessionCreateSerializer)
    def post(self, request):
        model_name = (request.data.get("model_name") or _read_default_model()).strip()
        if not model_name:
            return self.error("model_name is required")

        session = LLMChatSession.objects.create(
            user=request.user,
            title=(request.data.get("title") or "").strip(),
            model_name=model_name,
        )
        return self.success(LLMChatSessionSerializer(session).data)

    @login_required
    @validate_serializer(LLMChatSessionUpdateSerializer)
    def put(self, request):
        session = LLMChatSession.objects.filter(id=request.data["id"], user=request.user).first()
        if not session:
            return self.error("Chat session does not exist")

        update_fields = []
        if "title" in request.data:
            session.title = (request.data.get("title") or "").strip()
            update_fields.append("title")
        if "model_name" in request.data:
            model_name = (request.data.get("model_name") or "").strip()
            if not model_name:
                return self.error("model_name cannot be blank")
            session.model_name = model_name
            update_fields.append("model_name")

        if update_fields:
            _touch_session(session, update_fields)

        return self.success(LLMChatSessionSerializer(session).data)

    @login_required
    @validate_serializer(LLMChatSessionDeleteSerializer)
    def delete(self, request):
        session = LLMChatSession.objects.filter(id=request.data["id"], user=request.user).first()
        if not session:
            return self.error("Chat session does not exist")
        session.delete()
        return self.success()


class LLMChatMessageAPI(APIView):
    @login_required
    @validate_serializer(LLMChatMessagesQuerySerializer)
    def get(self, request):
        session = LLMChatSession.objects.filter(id=request.data["session_id"], user=request.user).first()
        if not session:
            return self.error("Chat session does not exist")

        offset = int(request.data.get("offset", 0))
        limit = int(request.data.get("limit", 100))
        queryset = LLMChatMessage.objects.filter(session=session).order_by("created_at", "id")
        total = queryset.count()
        rows = queryset[offset:offset + limit]
        return self.success({
            "results": LLMChatMessageSerializer(rows, many=True).data,
            "total": total,
        })


class LLMChatCompletionsAPI(APIView):
    @login_required
    def post(self, request):
        raw_payload = request.data
        if not isinstance(raw_payload, dict):
            return _json_resp({"error": "invalid-request", "data": "Invalid request body"}, status=400)

        if "session_id" in raw_payload and "content" in raw_payload:
            return self._post_with_db_session(request, raw_payload)
        return self._post_legacy_proxy(raw_payload)

    def _post_with_db_session(self, request, raw_payload):
        serializer = LLMChatCompletionsSerializer(data=raw_payload)
        if not serializer.is_valid():
            return _json_resp({"error": "invalid-request", "data": _serializer_error(serializer)}, status=400)
        data = serializer.validated_data

        session = LLMChatSession.objects.filter(id=data["session_id"], user=request.user).first()
        if not session:
            return _json_resp({"error": "not-found", "data": "Chat session does not exist"}, status=404)

        user_content = data["content"].strip()
        if not user_content:
            return _json_resp({"error": "invalid-request", "data": "content cannot be blank"}, status=400)

        if not (data.get("model") or session.model_name or _read_default_model()):
            return _json_resp({"error": "invalid-request", "data": "model is required"}, status=400)

        LLMChatMessage.objects.create(
            session=session,
            role=LLMChatMessageRole.USER,
            content=user_content,
        )

        update_fields = []
        if not session.title:
            session.title = user_content[:36]
            update_fields.append("title")
        requested_model = (data.get("model") or "").strip()
        if requested_model and requested_model != session.model_name:
            session.model_name = requested_model
            update_fields.append("model_name")
        _touch_session(session, update_fields)

        payload = _build_gateway_payload(session, data)
        return self._proxy_with_optional_persist(payload, session)

    def _post_legacy_proxy(self, raw_payload):
        payload = dict(raw_payload)
        if not isinstance(payload.get("messages"), list) or not payload.get("messages"):
            return _json_resp({"error": "invalid-request", "data": "messages is required"}, status=400)

        default_model = _read_default_model()
        if default_model:
            payload["model"] = default_model
        elif not payload.get("model"):
            return _json_resp({"error": "invalid-request", "data": "model is required"}, status=400)
        return self._proxy_with_optional_persist(payload, session=None)

    def _proxy_with_optional_persist(self, payload, session):
        gateway_key = _read_gateway_api_key()
        if not gateway_key:
            return _json_resp(
                {"error": "gateway-misconfigured", "data": "LLM gateway api key is not configured"},
                status=500,
            )

        stream = bool(payload.get("stream", False))
        timeout_sec = float(get_env("LLM_GATEWAY_TIMEOUT_SEC", "300"))
        headers = {
            "Authorization": f"Bearer {gateway_key}",
            "Content-Type": "application/json",
        }

        try:
            upstream = requests.post(
                _build_gateway_url(),
                headers=headers,
                data=json.dumps(payload),
                stream=stream,
                timeout=timeout_sec,
            )
        except requests.RequestException as e:
            logger.exception("Failed to call gateway: %s", e)
            return _json_resp({"error": "gateway-unavailable", "data": "Failed to connect to llm gateway"}, status=502)

        if not stream:
            return self._handle_non_stream_response(upstream, session)
        return self._handle_stream_response(upstream, session)

    def _handle_non_stream_response(self, upstream, session):
        content_type = upstream.headers.get("Content-Type", "application/json")
        status_code = upstream.status_code
        body = upstream.content

        if session and status_code < 400:
            try:
                response_json = upstream.json()
                assistant_content = _extract_assistant_content(response_json)
                prompt_tokens, completion_tokens = _extract_usage(response_json)
                if assistant_content:
                    LLMChatMessage.objects.create(
                        session=session,
                        role=LLMChatMessageRole.ASSISTANT,
                        content=assistant_content,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                    _touch_session(session)
            except Exception:
                logger.exception("Failed to persist non-stream assistant response")
            finally:
                upstream.close()
        else:
            upstream.close()

        return HttpResponse(body, status=status_code, content_type=content_type)

    def _handle_stream_response(self, upstream, session):
        if upstream.status_code >= 400:
            body = upstream.content
            content_type = upstream.headers.get("Content-Type", "application/json")
            upstream.close()
            return HttpResponse(body, status=upstream.status_code, content_type=content_type)

        full_content = {"text": ""}
        usage_state = {"prompt_tokens": 0, "completion_tokens": 0}

        def stream_iter():
            line_buffer = ""
            try:
                for chunk in upstream.iter_content(chunk_size=1024):
                    if not chunk:
                        continue

                    text = chunk.decode("utf-8", errors="ignore")
                    line_buffer += text
                    lines = line_buffer.split("\n")
                    line_buffer = lines.pop() or ""

                    for raw_line in lines:
                        line = raw_line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload_line = line[5:].strip()
                        if not payload_line or payload_line == "[DONE]":
                            continue
                        try:
                            event = json.loads(payload_line)
                            choices = event.get("choices") or []
                            if choices:
                                delta = choices[0].get("delta") or {}
                                delta_content = delta.get("content")
                                if isinstance(delta_content, str):
                                    full_content["text"] += delta_content
                            usage = event.get("usage") or {}
                            if isinstance(usage, dict):
                                usage_state["prompt_tokens"] = int(usage.get("prompt_tokens") or usage_state["prompt_tokens"])
                                usage_state["completion_tokens"] = int(usage.get("completion_tokens") or usage_state["completion_tokens"])
                        except Exception:
                            continue

                    yield chunk
            finally:
                upstream.close()
                if session and full_content["text"]:
                    try:
                        LLMChatMessage.objects.create(
                            session=session,
                            role=LLMChatMessageRole.ASSISTANT,
                            content=full_content["text"],
                            prompt_tokens=usage_state["prompt_tokens"],
                            completion_tokens=usage_state["completion_tokens"],
                        )
                        _touch_session(session)
                    except Exception:
                        logger.exception("Failed to persist stream assistant response")

        response = StreamingHttpResponse(
            streaming_content=stream_iter(),
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "text/event-stream"),
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
