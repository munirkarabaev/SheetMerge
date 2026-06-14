"""Application configuration for the core app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configure core application startup."""

    name = "core"

    def ready(self) -> None:
        """Register model signal handlers."""

        from core import signals  # noqa: F401
