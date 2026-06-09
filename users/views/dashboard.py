"""Authenticated dashboard views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardPageView(LoginRequiredMixin, TemplateView):
    """Render the first authenticated workspace page."""

    template_name = "users/dashboard.html"
