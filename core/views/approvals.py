"""Views for approving reviewed merge plans."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from core.models import MergePlan, MergePlanningSession, Mergeset


class MergesetApproveMappingView(LoginRequiredMixin, View):
    """Approve the latest owner-scoped merge plan for export."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        """Mark the latest merge plan as approved."""

        mergeset = get_object_or_404(
            Mergeset,
            pk=kwargs["pk"],
            owner=request.user,
        )
        merge_plan = mergeset.merge_plans.first()
        if merge_plan is None:
            messages.error(request, "Generate an AI mapping plan before approval.")
            return redirect("core:mergeset_ai_suggestions", pk=mergeset.pk)

        mergeset.merge_plans.exclude(pk=merge_plan.pk).update(
            status=MergePlan.Status.NEEDS_REVIEW
        )
        merge_plan.status = MergePlan.Status.APPROVED
        merge_plan.save(update_fields=["status", "updated_at"])

        merge_plan.session.status = MergePlanningSession.Status.APPROVED
        merge_plan.session.save(update_fields=["status", "updated_at"])
        messages.success(request, "Approved this mapping for export.")
        return redirect("core:mergeset_column_mapping", pk=mergeset.pk)
