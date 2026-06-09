"""Views for authenticated project workflows."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from core.forms import ProjectForm
from core.models import Project


class OwnedProjectQuerysetMixin(LoginRequiredMixin):
    """Restrict project queries to the authenticated user's records."""

    def get_queryset(self):
        """Return only projects owned by the current user."""

        return Project.objects.filter(owner=self.request.user)


class ProjectListView(OwnedProjectQuerysetMixin, ListView):
    """Render the current user's projects."""

    model = Project
    template_name = "core/projects/project_list.html"
    context_object_name = "projects"


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """Create a project owned by the current user."""

    form_class = ProjectForm
    template_name = "core/projects/project_form.html"

    def form_valid(self, form):
        """Attach the logged-in user as the project owner."""

        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """Return the destination after project creation."""

        return reverse("core:project_detail", kwargs={"pk": self.object.pk})


class ProjectDetailView(OwnedProjectQuerysetMixin, DetailView):
    """Render a single owner-scoped project workspace."""

    model = Project
    template_name = "core/projects/project_detail.html"
    context_object_name = "project"
