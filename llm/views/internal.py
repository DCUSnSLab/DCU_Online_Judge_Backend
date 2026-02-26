import hashlib
import hmac

from django.db.models import F, Max
from django.utils import timezone

from utils.api import CSRFExemptAPIView, validate_serializer
from utils.shortcuts import get_env

from ..models import LLMAuditLog, LLMApiKey, LLMKeyStatus, LLMRouteMap
from ..serializers import LLMUsageReportSerializer, LLMValidateKeySerializer


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _has_scope(scope, model):
    if not model:
        return True
    if not isinstance(scope, dict):
        return False
    models = scope.get("models", ["*"])
    if not isinstance(models, list):
        return False
    return "*" in models or model in models


def _check_internal_secret(request):
    # Prefer dedicated LLM secret; fallback to judge token for unified env usage.
    expected_secret = get_env("LLM_INTERNAL_SHARED_SECRET", "") or get_env("JUDGE_SERVER_TOKEN", "")
    if not expected_secret:
        return True
    client_secret = request.META.get("HTTP_X_INTERNAL_SECRET", "")
    return hmac.compare_digest(client_secret, expected_secret)


class LLMValidateKeyAPI(CSRFExemptAPIView):
    @validate_serializer(LLMValidateKeySerializer)
    def post(self, request):
        if not _check_internal_secret(request):
            return self.error(msg="Invalid internal secret", err="permission-denied")

        raw_key = request.data["key"]
        model = request.data.get("model")
        key_hash = hash_key(raw_key)
        key = LLMApiKey.objects.filter(key_hash=key_hash).select_related("created_by").first()

        if not key:
            return self.success({"valid": False, "reason": "invalid-key"})

        if key.status == LLMKeyStatus.EXPIRED:
            return self.success({"valid": False, "reason": "expired"})

        if key.expires_at and key.expires_at <= timezone.now():
            key.status = LLMKeyStatus.EXPIRED
            key.save(update_fields=["status", "updated_at"])
            return self.success({"valid": False, "reason": "expired"})

        if key.status != LLMKeyStatus.ACTIVE:
            return self.success({"valid": False, "reason": "revoked"})

        if not _has_scope(key.scope, model):
            return self.success({"valid": False, "reason": "scope-denied"})

        key.last_used_at = timezone.now()
        key.total_requests = F("total_requests") + 1
        key.save(update_fields=["last_used_at", "total_requests", "updated_at"])

        LLMAuditLog.objects.create(
            actor=key.created_by,
            action="validate",
            target_key=key,
            metadata={"model": model, "path": request.data.get("path")},
        )

        key.refresh_from_db(fields=["total_requests", "total_prompt_tokens"])

        return self.success({
            "valid": True,
            "reason": "ok",
            "key_id": str(key.id),
            "scope": key.scope,
            "status": key.status,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "rate_limit": {"rpm": 60},
            "owner": {
                "id": key.created_by.id,
                "username": key.created_by.username,
                "realname": key.created_by.realname,
            },
        })


class LLMUsageReportAPI(CSRFExemptAPIView):
    @validate_serializer(LLMUsageReportSerializer)
    def post(self, request):
        if not _check_internal_secret(request):
            return self.error(msg="Invalid internal secret", err="permission-denied")

        key = LLMApiKey.objects.filter(id=request.data["key_id"]).first()
        if not key:
            return self.success({"ok": False, "reason": "key-not-found"})

        prompt_tokens = request.data.get("prompt_tokens", 0)
        key.total_prompt_tokens = F("total_prompt_tokens") + int(prompt_tokens)
        key.save(update_fields=["total_prompt_tokens", "updated_at"])

        return self.success({"ok": True})


class LLMRoutesAPI(CSRFExemptAPIView):
    def get(self, request):
        if not _check_internal_secret(request):
            return self.error(msg="Invalid internal secret", err="permission-denied")

        routes = LLMRouteMap.objects.filter(enabled=True).order_by("model_name", "priority", "-weight")
        data = [
            {
                "id": str(row["id"]),
                "model_name": row["model_name"],
                "upstream_url": row["upstream_url"],
                "priority": row["priority"],
                "weight": row["weight"],
                "enabled": row["enabled"],
            }
            for row in routes.values("id", "model_name", "upstream_url", "priority", "weight", "enabled")
        ]
        agg = routes.aggregate(updated_at=Max("updated_at"))
        updated_at = agg.get("updated_at")
        return self.success({
            "version": int(updated_at.timestamp()) if updated_at else 0,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "routes": data,
        })
