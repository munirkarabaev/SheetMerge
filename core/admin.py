"""Admin registrations for the core application."""

from django.contrib import admin

from core.models import (
    AIUsageRecord,
    MergePlan,
    MergePlanningMessage,
    MergePlanningSession,
    Mergeset,
    MergesetFile,
)


@admin.register(Mergeset)
class MergesetAdmin(admin.ModelAdmin):
    """Admin configuration for mergeset records."""

    list_display = ("name", "owner", "created_at", "updated_at")
    search_fields = ("name", "owner__email")


@admin.register(MergesetFile)
class MergesetFileAdmin(admin.ModelAdmin):
    """Admin configuration for uploaded source files."""

    list_display = ("original_name", "mergeset", "file_size", "uploaded_at")
    search_fields = ("original_name", "mergeset__name", "mergeset__owner__email")


@admin.register(MergePlanningSession)
class MergePlanningSessionAdmin(admin.ModelAdmin):
    """Admin configuration for AI planning sessions."""

    list_display = ("mergeset", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("mergeset__name", "mergeset__owner__email")


@admin.register(MergePlanningMessage)
class MergePlanningMessageAdmin(admin.ModelAdmin):
    """Admin configuration for planning chat messages."""

    list_display = ("session", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("session__mergeset__name", "content")


@admin.register(MergePlan)
class MergePlanAdmin(admin.ModelAdmin):
    """Admin configuration for generated merge plans."""

    list_display = ("mergeset", "session", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("mergeset__name", "mergeset__owner__email", "ai_summary")


@admin.register(AIUsageRecord)
class AIUsageRecordAdmin(admin.ModelAdmin):
    """Admin configuration for AI token credit usage."""

    list_display = (
        "user",
        "mergeset",
        "request_type",
        "model",
        "credits_used",
        "created_at",
    )
    list_filter = ("request_type", "model")
    search_fields = ("user__email", "mergeset__name")
    readonly_fields = (
        "user",
        "mergeset",
        "planning_session",
        "request_type",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "credits_used",
        "created_at",
    )
