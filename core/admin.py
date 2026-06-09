"""Admin registrations for the core application."""

from django.contrib import admin

from core.models import Mergeset


@admin.register(Mergeset)
class MergesetAdmin(admin.ModelAdmin):
    """Admin configuration for mergeset records."""

    list_display = ("name", "owner", "created_at", "updated_at")
    search_fields = ("name", "owner__email")
