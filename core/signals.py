"""Signal handlers for cleaning up files removed from the database."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.models import MergesetFile


@receiver(post_delete, sender=MergesetFile)
def delete_mergeset_file_from_storage(
    sender,
    instance: MergesetFile,
    **kwargs,
) -> None:
    """Delete stored content after its database transaction commits."""

    if not instance.file.name:
        return

    storage = instance.file.storage
    stored_name = instance.file.name
    transaction.on_commit(lambda: storage.delete(stored_name))
