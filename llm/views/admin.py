import hashlib

from account.decorators import super_admin_required
from utils.api import APIView, validate_serializer
from utils.shortcuts import rand_str

from ..models import LLMAuditLog, LLMApiKey, LLMKeyStatus
from ..serializers import LLMApiKeySerializer, LLMKeyCreateSerializer, LLMKeyRevokeSerializer


def make_llm_key():
    return "dcu_llm_" + rand_str(48, type="lower_str")


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


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
