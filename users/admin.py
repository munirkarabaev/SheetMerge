"""Admin registrations for the users application."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.forms import CustomUserChangeForm, CustomUserCreationForm
from users.models import User


@admin.register(User)
class SheetMergeUserAdmin(UserAdmin):
    """Admin configuration for the custom user model."""

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ("email", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff", "is_active", "is_superuser")
    ordering = ("email",)
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )
