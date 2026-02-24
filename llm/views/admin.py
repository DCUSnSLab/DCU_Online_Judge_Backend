import hashlib
import os

from account.decorators import super_admin_required
from utils.api import APIView, validate_serializer
from utils.shortcuts import get_env, rand_str

from ..models import LLMAuditLog, LLMApiKey, LLMKeyStatus, LLMRouteMap
from ..serializers import (
    LLMApiKeySerializer,
    LLMGatewayConfigUpdateSerializer,
    LLMKeyCreateSerializer,
    LLMKeyRevokeSerializer,
    LLMRouteCreateSerializer,
    LLMRouteDeleteSerializer,
    LLMRouteSerializer,
    LLMRouteUpdateSerializer,
)


def make_llm_key():
    return "dcu_llm_" + rand_str(48, type="lower_str")


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _gateway_api_key_file_path():
    return get_env("LLM_GATEWAY_API_KEY_FILE", "/data/config/llm_gateway_api_key")


def _gateway_default_model_file_path():
    return get_env("LLM_DEFAULT_MODEL_FILE", "/data/config/llm_gateway_model")


def _read_config_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


def _write_config_file(path, value):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        f.write(value.strip())


def _mask_key(value):
    if not value:
        return ""
    if len(value) <= 12:
        return "*" * len(value)
    return "{}...{}".format(value[:8], value[-4:])


def _build_gateway_config_payload():
    key = _read_config_file(_gateway_api_key_file_path())
    default_model = _read_config_file(_gateway_default_model_file_path())
    return {
        "api_key_configured": bool(key),
        "api_key_preview": _mask_key(key),
        "default_model": default_model,
    }


class LLMGatewayConfigAdminAPI(APIView):
    @super_admin_required
    def get(self, request):
        return self.success(_build_gateway_config_payload())

    @super_admin_required
    @validate_serializer(LLMGatewayConfigUpdateSerializer)
    def post(self, request):
        api_key = request.data.get("api_key")
        default_model = request.data.get("default_model")

        if api_key is None and default_model is None:
            return self.error("api_key or default_model is required")

        if api_key is not None:
            api_key = api_key.strip()
            if not api_key:
                return self.error("api_key cannot be blank")
            _write_config_file(_gateway_api_key_file_path(), api_key)

        if default_model is not None:
            default_model = default_model.strip()
            if not default_model:
                return self.error("default_model cannot be blank")
            _write_config_file(_gateway_default_model_file_path(), default_model)

        return self.success(_build_gateway_config_payload())


class LLMKeyAdminAPI(APIView):
    @super_admin_required
    def get(self, request):
        key_id = request.GET.get("id")
        if key_id:
            key = LLMApiKey.objects.filter(id=key_id).first()
            if not key:
                return self.error("Key does not exist")
            return self.success(LLMApiKeySerializer(key).data)

        queryset = LLMApiKey.objects.all().select_related("created_by")
        if request.GET.get("paging") == "true":
            data = self.paginate_data(request, queryset, LLMApiKeySerializer)
            return self.success(data)
        return self.success(LLMApiKeySerializer(queryset, many=True).data)

    @super_admin_required
    @validate_serializer(LLMKeyCreateSerializer)
    def post(self, request):
        data = request.data
        raw_key = make_llm_key()
        key = LLMApiKey.objects.create(
            name=data["name"],
            key_prefix=raw_key[:16],
            key_hash=hash_key(raw_key),
            scope=data.get("scope") or {"models": ["*"]},
            expires_at=data.get("expires_at"),
            created_by=request.user,
        )

        LLMAuditLog.objects.create(
            actor=request.user,
            action="create",
            target_key=key,
            metadata={"name": key.name, "scope": key.scope},
        )
        return self.success({"key": raw_key, "meta": LLMApiKeySerializer(key).data})


class LLMKeyRevokeAPI(APIView):
    @super_admin_required
    @validate_serializer(LLMKeyRevokeSerializer)
    def post(self, request):
        key = LLMApiKey.objects.filter(id=request.data["id"]).first()
        if not key:
            return self.error("Key does not exist")
        if key.status == LLMKeyStatus.REVOKED:
            return self.success()

        key.status = LLMKeyStatus.REVOKED
        key.save(update_fields=["status", "updated_at"])

        LLMAuditLog.objects.create(
            actor=request.user,
            action="revoke",
            target_key=key,
            metadata={"id": str(key.id)},
        )
        return self.success()


class LLMRouteAdminAPI(APIView):
    @super_admin_required
    def get(self, request):
        route_id = request.GET.get("id")
        if route_id:
            route = LLMRouteMap.objects.filter(id=route_id).select_related("updated_by").first()
            if not route:
                return self.error("Route does not exist")
            return self.success(LLMRouteSerializer(route).data)

        queryset = LLMRouteMap.objects.all().select_related("updated_by")
        model_name = request.GET.get("model_name")
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        if request.GET.get("paging") == "true":
            data = self.paginate_data(request, queryset, LLMRouteSerializer)
            return self.success(data)
        return self.success(LLMRouteSerializer(queryset, many=True).data)

    @super_admin_required
    @validate_serializer(LLMRouteCreateSerializer)
    def post(self, request):
        data = request.data
        route = LLMRouteMap.objects.create(
            model_name=data["model_name"],
            upstream_url=data["upstream_url"],
            priority=data.get("priority", 100),
            weight=data.get("weight", 100),
            enabled=data.get("enabled", True),
            updated_by=request.user,
        )
        return self.success(LLMRouteSerializer(route).data)

    @super_admin_required
    @validate_serializer(LLMRouteUpdateSerializer)
    def put(self, request):
        route = LLMRouteMap.objects.filter(id=request.data["id"]).first()
        if not route:
            return self.error("Route does not exist")

        for field in ["model_name", "upstream_url", "priority", "weight", "enabled"]:
            if field in request.data:
                setattr(route, field, request.data[field])

        route.updated_by = request.user
        route.save()
        return self.success(LLMRouteSerializer(route).data)

    @super_admin_required
    @validate_serializer(LLMRouteDeleteSerializer)
    def delete(self, request):
        route = LLMRouteMap.objects.filter(id=request.data["id"]).first()
        if not route:
            return self.error("Route does not exist")
        route.delete()
        return self.success()
