"""Uploaded source files attached to mergesets."""

from pathlib import Path
from uuid import uuid4

from django.db import models


def mergeset_file_upload_path(instance, filename: str) -> str:
    """Build a collision-resistant storage path for an uploaded source file."""

    suffix = Path(filename).suffix.lower()
    return f"mergesets/{instance.mergeset_id}/sources/{uuid4().hex}{suffix}"


class MergesetFile(models.Model):
    """Represents one source spreadsheet uploaded to a mergeset."""

    mergeset = models.ForeignKey(
        "core.Mergeset",
        on_delete=models.CASCADE,
        related_name="source_files",
    )
    file = models.FileField(upload_to=mergeset_file_upload_path)
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata."""

        ordering = ["uploaded_at", "id"]

    def __str__(self) -> str:
        """Return the user-facing source filename."""

        return self.original_name
