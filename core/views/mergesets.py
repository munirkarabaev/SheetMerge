"""Views for authenticated mergeset workflows."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from core.forms import MergesetForm
from core.models import Mergeset


class OwnedMergesetQuerysetMixin(LoginRequiredMixin):
    """Restrict mergeset queries to the authenticated user's records."""

    def get_queryset(self):
        """Return only mergesets owned by the current user."""

        return Mergeset.objects.filter(owner=self.request.user)


class MergesetListView(OwnedMergesetQuerysetMixin, ListView):
    """Render the current user's mergesets."""

    model = Mergeset
    template_name = "core/mergesets/mergeset_list.html"
    context_object_name = "mergesets"


class MergesetCreateView(LoginRequiredMixin, CreateView):
    """Create a mergeset owned by the current user."""

    form_class = MergesetForm
    template_name = "core/mergesets/mergeset_form.html"

    def form_valid(self, form):
        """Attach the logged-in user as the mergeset owner."""

        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """Return the destination after mergeset creation."""

        return reverse("core:mergeset_detail", kwargs={"pk": self.object.pk})


class MergesetDetailView(OwnedMergesetQuerysetMixin, DetailView):
    """Render a single owner-scoped mergeset workspace."""

    model = Mergeset
    template_name = "core/mergesets/mergeset_detail.html"
    context_object_name = "mergeset"
