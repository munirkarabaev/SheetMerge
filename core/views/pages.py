"""Views for simple top-level product pages."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class BillingPageView(LoginRequiredMixin, TemplateView):
    """Render a minimal billing placeholder page."""

    template_name = "core/pages/billing.html"


class SupportPageView(LoginRequiredMixin, TemplateView):
    """Render a minimal support placeholder page."""

    template_name = "core/pages/support.html"
