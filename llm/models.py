import uuid

from django.db import models
from django.utils import timezone

from account.models import User
from utils.models import JSONField


class LLMKeyStatus:
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"

    CHOICES = (
        (ACTIVE, "Active"),
        (REVOKED, "Revoked"),
        (EXPIRED, "Expired"),
    )


class LLMApiKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    key_prefix = models.CharField(max_length=20, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    scope = JSONField(default=dict)
    status = models.CharField(max_length=16, choices=LLMKeyStatus.CHOICES, default=LLMKeyStatus.ACTIVE, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    total_requests = models.BigIntegerField(default=0)
    total_prompt_tokens = models.BigIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="llm_keys")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_api_key"
        ordering = ("-created_at",)

    def is_usable(self):
        if self.status != LLMKeyStatus.ACTIVE:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True


class LLMRouteMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_name = models.CharField(max_length=255, db_index=True)
    upstream_url = models.CharField(max_length=1024)
    priority = models.IntegerField(default=100, db_index=True)
    weight = models.IntegerField(default=100)
    enabled = models.BooleanField(default=True, db_index=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="llm_route_updates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_route_map"
        ordering = ("model_name", "priority", "-weight", "upstream_url")


class LLMAuditLog(models.Model):
    id = models.AutoField(primary_key=True)
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="llm_audit_logs")
    action = models.CharField(max_length=32)
    target_key = models.ForeignKey(LLMApiKey, null=True, on_delete=models.SET_NULL, related_name="audit_logs")
    metadata = JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "llm_audit_log"
        ordering = ("-created_at",)
