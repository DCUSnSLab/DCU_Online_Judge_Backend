from utils.api import serializers

from .models import LLMApiKey


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
