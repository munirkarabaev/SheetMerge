"""Views for downloading generated merge results."""

import csv

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views import View

from core.models import Mergeset
from core.services import build_merge_preview


class MergesetCsvExportView(LoginRequiredMixin, View):
    """Download the latest merge plan result as a CSV file."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        """Return a CSV generated from the latest reviewable merge plan."""

        mergeset = get_object_or_404(
            Mergeset,
            pk=kwargs["pk"],
            owner=request.user,
        )
        merge_plan = mergeset.merge_plans.first()
        if merge_plan is None:
            messages.error(request, "Generate an AI mapping plan before exporting.")
            return redirect("core:mergeset_ai_suggestions", pk=mergeset.pk)

        preview = build_merge_preview(merge_plan)
        filename = f"{slugify(mergeset.name) or 'sheetmerge-export'}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(preview.columns)
        for row in preview.rows:
            writer.writerow([row.get(column, "") for column in preview.columns])
        return response
