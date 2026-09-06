"""Views for the completed merge workflow."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.models import MergePlan, Mergeset
from core.services import build_merge_preview


class MergesetWorkflowCompleteView(LoginRequiredMixin, View):
    """Show the final summary for an approved, export-ready mergeset."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        """Render a completion screen only when export safety gates pass."""

        mergeset = get_object_or_404(
            Mergeset,
            pk=kwargs["pk"],
            owner=request.user,
        )
        merge_plan = mergeset.merge_plans.filter(
            status=MergePlan.Status.APPROVED
        ).first()
        if merge_plan is None:
            messages.error(request, "Approve the column mapping before completing the workflow.")
            return redirect("core:mergeset_column_mapping", pk=mergeset.pk)

        merge_preview = build_merge_preview(merge_plan)
        if merge_preview.blocking_errors:
            messages.error(request, "Resolve preview exceptions before completing the workflow.")
            return redirect("core:mergeset_column_mapping", pk=mergeset.pk)

        return render(
            request,
            "core/mergesets/workflow_complete.html",
            {
                "mergeset": mergeset,
                "merge_plan": merge_plan,
                "reconciliation": merge_preview.reconciliation,
            },
        )
