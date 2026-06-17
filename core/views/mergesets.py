"""Views for authenticated mergeset workflows."""

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView

from core.forms import MergesetFileUploadForm, MergesetForm
from core.models import Mergeset, MergesetFile
from core.services import parse_mergeset_file


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
        source_files = context["mergeset"].source_files.all()
        context["mapping_ready"] = (
            source_files.exists()
            and not source_files.exclude(
                parse_status=MergesetFile.ParseStatus.PARSED
            ).exists()
        )
        return context


class MergesetMappingView(OwnedMergesetQuerysetMixin, DetailView):
    """Render parsed source headers for column mapping."""

    model = Mergeset
    template_name = "core/mergesets/mergeset_mapping.html"
    context_object_name = "mergeset"

    def get(self, request, *args, **kwargs):
        """Require at least one successfully parsed file before mapping."""

        self.object = self.get_object()
        source_files = self.object.source_files.all()
        mapping_ready = (
            source_files.exists()
            and not source_files.exclude(
                parse_status=MergesetFile.ParseStatus.PARSED
            ).exists()
        )
        if not mapping_ready:
            messages.error(
                request,
                "Upload files and resolve all parsing errors before column mapping.",
            )
            return redirect("core:mergeset_detail", pk=self.object.pk)
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class MergesetDeleteView(LoginRequiredMixin, View):
    """Delete one owner-scoped mergeset and its related records."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        """Delete the mergeset and redirect to the owner's list."""

        mergeset = get_object_or_404(
            Mergeset,
            pk=kwargs["pk"],
            owner=request.user,
        )
        mergeset_name = mergeset.name
        mergeset.delete()
        messages.success(request, f'Deleted mergeset "{mergeset_name}".')
        return redirect("core:mergeset_list")


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
        """Persist and parse each uploaded CSV under the current mergeset."""

        parsed_count = 0
        for uploaded_file in form.cleaned_data["files"]:
            source_file = MergesetFile.objects.create(
                mergeset=self.mergeset,
                file=uploaded_file,
                original_name=Path(uploaded_file.name).name,
                file_size=uploaded_file.size,
            )
            parsed_count += parse_mergeset_file(source_file)

        messages.success(
            self.request,
            f"Uploaded {len(form.cleaned_data['files'])} source file(s); "
            f"parsed {parsed_count} successfully.",
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


class MergesetFileDeleteView(LoginRequiredMixin, View):
    """Delete one uploaded file from an owner-scoped mergeset."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        """Delete the file record and return to its mergeset."""

        source_file = get_object_or_404(
            MergesetFile.objects.select_related("mergeset"),
            pk=kwargs["file_pk"],
            mergeset_id=kwargs["pk"],
            mergeset__owner=request.user,
        )
        original_name = source_file.original_name
        mergeset_pk = source_file.mergeset_id
        source_file.delete()
        messages.success(request, f'Deleted source file "{original_name}".')
        return redirect("core:mergeset_detail", pk=mergeset_pk)
