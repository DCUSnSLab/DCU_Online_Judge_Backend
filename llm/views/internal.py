import hashlib
import hmac

from django.utils import timezone

from utils.api import CSRFExemptAPIView, validate_serializer
from utils.shortcuts import get_env

from ..models import LLMAuditLog, LLMApiKey, LLMKeyStatus
from ..serializers import LLMValidateKeySerializer


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


class LLMValidateKeyAPI(CSRFExemptAPIView):
    @validate_serializer(LLMValidateKeySerializer)
    def post(self, request):
        expected_secret = get_env("LLM_INTERNAL_SHARED_SECRET", "")
        if expected_secret:
            client_secret = request.META.get("HTTP_X_INTERNAL_SECRET", "")
            if not hmac.compare_digest(client_secret, expected_secret):
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
        key.save(update_fields=["last_used_at", "updated_at"])

        LLMAuditLog.objects.create(
            actor=key.created_by,
            action="validate",
            target_key=key,
            metadata={"model": model, "path": request.data.get("path")},
        )

        return self.success({
            "valid": True,
            "reason": "ok",
            "key_id": str(key.id),
            "scope": key.scope,
            "status": key.status,
            "expires_at": key.expires_at,
            "rate_limit": {"rpm": 60},
            "owner": {
                "id": key.created_by.id,
                "username": key.created_by.username,
                "realname": key.created_by.realname,
            },
        })
