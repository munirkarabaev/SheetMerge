"""Template context processors for authentication views."""

from django.conf import settings


def authentication_context(request):
    """Expose auth configuration needed by shared templates."""

    return {
        "google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED,
    }
