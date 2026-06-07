"""Project domain models."""

from django.db import models


class Project(models.Model):
    """Represents a user workspace for future imports and transaction cleanup."""

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
