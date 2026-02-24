from utils.api import serializers

from .models import LLMApiKey, LLMRouteMap


class LLMKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    scope = serializers.DictField(required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class LLMKeyRevokeSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class LLMValidateKeySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=512)
    model = serializers.CharField(required=False, allow_blank=True)
    path = serializers.CharField(required=False, allow_blank=True)


class LLMUsageReportSerializer(serializers.Serializer):
    key_id = serializers.UUIDField()
    prompt_tokens = serializers.IntegerField(min_value=0, required=False, default=0)


class LLMRouteCreateSerializer(serializers.Serializer):
    model_name = serializers.CharField(max_length=255)
    upstream_url = serializers.CharField(max_length=1024)
    priority = serializers.IntegerField(required=False, default=100)
    weight = serializers.IntegerField(required=False, default=100)
    enabled = serializers.BooleanField(required=False, default=True)


class LLMRouteUpdateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    model_name = serializers.CharField(max_length=255, required=False)
    upstream_url = serializers.CharField(max_length=1024, required=False)
    priority = serializers.IntegerField(required=False)
    weight = serializers.IntegerField(required=False)
    enabled = serializers.BooleanField(required=False)


class LLMRouteDeleteSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class LLMApiKeySerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = LLMApiKey
        fields = (
            "id",
            "name",
            "key_prefix",
            "scope",
            "status",
            "expires_at",
            "last_used_at",
            "total_requests",
            "total_prompt_tokens",
            "created_at",
            "updated_at",
            "created_by",
        )

    def get_created_by(self, obj):
        return {
            "id": obj.created_by.id,
            "username": obj.created_by.username,
            "realname": obj.created_by.realname,
        }


class LLMRouteSerializer(serializers.ModelSerializer):
    updated_by = serializers.SerializerMethodField()

    class Meta:
        model = LLMRouteMap
        fields = (
            "id",
            "model_name",
            "upstream_url",
            "priority",
            "weight",
            "enabled",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def get_updated_by(self, obj):
        return {
            "id": obj.updated_by.id,
            "username": obj.updated_by.username,
            "realname": obj.updated_by.realname,
        }
