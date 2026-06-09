"""Views for top-level application pages."""

from django.shortcuts import redirect
from django.views.generic import TemplateView


class HomePageView(TemplateView):
    """Render the initial landing page for the application."""

    template_name = "core/home.html"

    def dispatch(self, request, *args, **kwargs):
        """Route authenticated users into the app workspace."""

        if request.user.is_authenticated:
            return redirect("users:dashboard")
        return super().dispatch(request, *args, **kwargs)
