"""Views for downloading generated merge results."""

import csv

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views import View

from core.models import MergePlan, Mergeset
from core.services import build_merge_preview
from core.services.csv_export import escape_spreadsheet_formula


CONVERSION_PROVENANCE_COLUMNS = [
    ("Conversion target column", "target_column"),
    ("Original amount", "original_amount"),
    ("Original currency", "original_currency"),
    ("Reporting amount", "reporting_amount"),
    ("Reporting currency", "reporting_currency"),
    ("Exchange rate", "exchange_rate"),
    ("Rate provider", "rate_provider"),
    ("Rate period", "rate_period"),
    ("Rate policy", "rate_policy"),
    ("Rounding policy", "rounding_policy"),
]

TRANSACTION_PROVENANCE_COLUMNS = [
    ("Provenance source file", "source_file"),
    ("Provenance source row", "source_row_number"),
    ("Provenance original values", "original_values"),
    ("Provenance mapping plan version", "mapping_plan_version"),
    ("Provenance transformations", "transformations"),
    ("Provenance review state", "review_state"),
]


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
        merge_plan = _get_export_merge_plan(mergeset)
        if merge_plan is None:
            if mergeset.merge_plans.exists():
                messages.error(
                    request,
                    "Approve the column mapping before exporting a CSV.",
                )
                return redirect("core:mergeset_column_mapping", pk=mergeset.pk)

            messages.error(request, "Generate an AI mapping plan before exporting.")
            return redirect("core:mergeset_ai_suggestions", pk=mergeset.pk)

        preview = build_merge_preview(merge_plan)
        if preview.blocking_errors:
            messages.error(
                request,
                "Resolve all preview exceptions before exporting a CSV.",
            )
            return redirect("core:mergeset_column_mapping", pk=mergeset.pk)

        filename = f"{slugify(mergeset.name) or 'sheetmerge-export'}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        has_conversion_provenance = any(preview.conversion_provenance)
        columns = list(preview.columns)
        columns.extend(column for column, _ in TRANSACTION_PROVENANCE_COLUMNS)
        if has_conversion_provenance:
            columns.extend(column for column, _ in CONVERSION_PROVENANCE_COLUMNS)

        writer = csv.writer(response)
        writer.writerow([escape_spreadsheet_formula(column) for column in columns])
        for row, transaction_provenance, conversion_provenance in zip(
            preview.rows,
            preview.transaction_provenance,
            preview.conversion_provenance,
        ):
            values = [row.get(column, "") for column in preview.columns]
            values.extend(
                transaction_provenance.get(key, "")
                for _, key in TRANSACTION_PROVENANCE_COLUMNS
            )
            if has_conversion_provenance:
                values.extend(
                    _format_provenance(conversion_provenance, key)
                    for _, key in CONVERSION_PROVENANCE_COLUMNS
                )
            writer.writerow(
                [
                    escape_spreadsheet_formula(value)
                    for value in values
                ]
            )
        return response


def _get_export_merge_plan(mergeset: Mergeset) -> MergePlan | None:
    """Return the explicitly approved merge plan, if one exists."""

    return mergeset.merge_plans.filter(
        status=MergePlan.Status.APPROVED
    ).first()


def _format_provenance(provenance: list[dict[str, str]], key: str) -> str:
    """Join one or more conversion records for a single exported row."""

    return " | ".join(record.get(key, "") for record in provenance)
