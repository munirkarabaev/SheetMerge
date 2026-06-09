"""Authenticated dashboard views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from core.models import Project


class DashboardPageView(LoginRequiredMixin, TemplateView):
    """Render the first authenticated workspace page."""

    template_name = "users/dashboard.html"

    def get_context_data(self, **kwargs):
        """Expose the current user's project count."""

        context = super().get_context_data(**kwargs)
        context["project_count"] = Project.objects.filter(owner=self.request.user).count()
        return context
