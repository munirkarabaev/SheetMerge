"""Views for top-level application pages."""

from django.views.generic import TemplateView


class HomePageView(TemplateView):
    """Render the initial landing page for the application."""

    template_name = "core/home.html"
