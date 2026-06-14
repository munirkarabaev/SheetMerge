"""Admin registrations for the core application."""

from django.contrib import admin

from core.models import Mergeset, MergesetFile


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
