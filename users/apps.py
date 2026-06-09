"""Application configuration for users."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Register the users app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
