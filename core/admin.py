"""Admin registrations for the core application."""

from django.contrib import admin

from core.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin configuration for project records."""

    list_display = ("name", "owner", "created_at", "updated_at")
    search_fields = ("name", "owner__email")
