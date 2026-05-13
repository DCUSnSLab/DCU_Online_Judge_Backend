from django.contrib import admin

from .models import (
    EvalAIUsage,
    EvalJob,
    EvalJobEvent,
    EvalJobRequester,
    EvalQualitative,
    EvalSubmissionSnapshot,
)


@admin.register(EvalSubmissionSnapshot)
class EvalSubmissionSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "contest", "user", "problem", "language", "captured_at")
    list_filter = ("contest", "language")
    search_fields = ("user__username", "problem__title")


@admin.register(EvalQualitative)
class EvalQualitativeAdmin(admin.ModelAdmin):
    list_display = ("id", "snapshot", "overall", "suggested_partial_score", "model_used", "updated_at")
    list_filter = ("model_used",)
    search_fields = ("snapshot__user__username",)


@admin.register(EvalAIUsage)
class EvalAIUsageAdmin(admin.ModelAdmin):
    list_display = ("id", "snapshot", "likelihood_score", "confidence", "model_used", "updated_at")
    list_filter = ("confidence", "model_used")


@admin.register(EvalJob)
class EvalJobAdmin(admin.ModelAdmin):
    list_display = ("id", "contest", "status", "n_done", "n_total", "n_failed", "force", "enqueued_at")
    list_filter = ("status", "force")
    search_fields = ("contest__title",)


@admin.register(EvalJobRequester)
class EvalJobRequesterAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "user", "joined_at")


@admin.register(EvalJobEvent)
class EvalJobEventAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "event_type", "ts")
    list_filter = ("event_type",)
