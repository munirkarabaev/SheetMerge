"""Views for authenticated mergeset workflows."""

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, ListView

from core.forms import MergesetFileUploadForm, MergesetForm
from core.models import Mergeset, MergesetFile


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

    def get_context_data(self, **kwargs):
        """Add the source-file upload form to the workspace."""

        context = super().get_context_data(**kwargs)
        context["upload_form"] = MergesetFileUploadForm()
        return context


class MergesetFileUploadView(LoginRequiredMixin, FormView):
    """Store validated source files on an owner-scoped mergeset."""

    form_class = MergesetFileUploadForm
    template_name = "core/mergesets/mergeset_detail.html"
    http_method_names = ["post"]

    def dispatch(self, request, *args, **kwargs):
        """Resolve the mergeset while enforcing ownership."""

        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.mergeset = get_object_or_404(
            Mergeset,
            pk=kwargs["pk"],
            owner=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Persist each uploaded source file under the current mergeset."""

        for uploaded_file in form.cleaned_data["files"]:
            MergesetFile.objects.create(
                mergeset=self.mergeset,
                file=uploaded_file,
                original_name=Path(uploaded_file.name).name,
                file_size=uploaded_file.size,
            )

        messages.success(
            self.request,
            f"Uploaded {len(form.cleaned_data['files'])} source file(s).",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        """Render validation errors inside the mergeset workspace."""

        return self.render_to_response(
            {
                "mergeset": self.mergeset,
                "upload_form": form,
            }
        )

    def get_success_url(self):
        """Return to the mergeset after a successful upload."""

        return reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
