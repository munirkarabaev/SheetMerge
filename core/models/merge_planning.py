"""Models for AI-assisted merge planning workflows."""

from django.db import models


class MergePlanningSession(models.Model):
    """Tracks one AI-assisted planning conversation for a mergeset."""

    class Status(models.TextChoices):
        """Planning states used by the AI suggestion workflow."""

        COLLECTING_REQUIREMENTS = "collecting_requirements", "Collecting requirements"
        MAPPING_READY = "mapping_ready", "Mapping ready"
        APPROVED = "approved", "Approved"

    mergeset = models.ForeignKey(
        "core.Mergeset",
        on_delete=models.CASCADE,
        related_name="planning_sessions",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.COLLECTING_REQUIREMENTS,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        """Return a readable identifier for admin and shell usage."""

        return f"{self.mergeset.name} planning session"


class MergePlanningMessage(models.Model):
    """Stores one user or assistant message in a planning session."""

    class Role(models.TextChoices):
        """Supported message roles in the planning conversation."""

        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(
        "core.MergePlanningSession",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata."""

        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        """Return a short readable message label."""

        return f"{self.get_role_display()} message"


class MergePlan(models.Model):
    """Stores an AI-generated mapping plan for review and approval."""

    class Status(models.TextChoices):
        """Review states for a generated merge plan."""

        DRAFT = "draft", "Draft"
        NEEDS_REVIEW = "needs_review", "Needs review"
        APPROVED = "approved", "Approved"

    mergeset = models.ForeignKey(
        "core.Mergeset",
        on_delete=models.CASCADE,
        related_name="merge_plans",
    )
    session = models.ForeignKey(
        "core.MergePlanningSession",
        on_delete=models.CASCADE,
        related_name="merge_plans",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    plan_json = models.JSONField(default=dict, blank=True)
    ai_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        """Return a readable identifier for admin and shell usage."""

        return f"{self.mergeset.name} merge plan"


class AIUsageRecord(models.Model):
    """Audit one completed AI request and its token credit cost."""

    class RequestType(models.TextChoices):
        """Supported AI request categories."""

        PLANNING = "planning", "Planning"
        REVISION = "revision", "Revision"

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="ai_usage_records",
    )
    mergeset = models.ForeignKey(
        "core.Mergeset",
        on_delete=models.CASCADE,
        related_name="ai_usage_records",
    )
    planning_session = models.ForeignKey(
        "core.MergePlanningSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_records",
    )
    request_type = models.CharField(max_length=16, choices=RequestType.choices)
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    credits_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata."""

        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        """Return a readable usage label."""

        return f"{self.get_request_type_display()} request used {self.credits_used} credits"
