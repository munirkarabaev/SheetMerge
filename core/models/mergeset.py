"""Mergeset domain models."""

from django.conf import settings
from django.db import models


class Mergeset(models.Model):
    """Represents one merge job containing files and review state."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mergesets",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return a readable identifier for admin and shell usage."""

        return self.name
