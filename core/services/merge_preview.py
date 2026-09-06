"""Build spreadsheet previews from generated merge plans."""

import csv
from dataclasses import dataclass
from io import StringIO
import json

from core.models import MergePlan, MergesetFile
from core.services.csv_parser import decode_csv_content
from core.services.currency_conversion import convert_currency
from core.services.exchange_rates import ExchangeRateProvider
from core.services.preview_validation import (
    add_blocking_exception,
    parse_date,
    normalize_amount,
    validate_preview_value,
)
from core.services.reconciliation import ReconciliationSummary, build_reconciliation_summary


@dataclass(frozen=True)
class MergePreview:
    """Preview rows generated from a merge plan."""

    columns: list[str]
    rows: list[dict[str, str]]
    warnings: list[str]
    blocking_errors: list[str]
    conversion_provenance: list[list[dict[str, str]]]
    transaction_provenance: list[dict[str, str]]
    reconciliation: ReconciliationSummary


def build_merge_preview(
    merge_plan: MergePlan,
    limit: int | None = None,
    rate_provider: ExchangeRateProvider | None = None,
) -> MergePreview:
    """Apply a merge plan to uploaded CSV files and return preview rows."""

    final_columns = [
        column["name"]
        for column in merge_plan.plan_json.get("final_columns", [])
        if column.get("name")
    ]
    final_column_types = {
        column["name"]: column.get("type", "")
        for column in merge_plan.plan_json.get("final_columns", [])
        if column.get("name")
    }
    rows = []
    warnings = []
    blocking_errors = []
    provenance_by_row: dict[int, list[dict[str, str]]] = {}
    transaction_provenance_by_row: dict[int, dict[str, str]] = {}
    source_files = {
        source_file.id: source_file
        for source_file in merge_plan.mergeset.source_files.filter(
            parse_status=MergesetFile.ParseStatus.PARSED
        )
    }

    for file_mapping in merge_plan.plan_json.get("file_mappings", []):
        source_file = source_files.get(file_mapping.get("file_id"))
        if source_file is None:
            continue

        for source_row_number, source_row, original_values in _read_source_rows(source_file):
            conversion_provenance: list[dict[str, str]] = []
            row = _build_preview_row(
                final_columns,
                final_column_types,
                file_mapping,
                source_row,
                source_file,
                merge_plan.plan_json,
                warnings,
                blocking_errors,
                conversion_provenance,
                rate_provider,
            )
            rows.append(row)
            provenance_by_row[id(row)] = conversion_provenance
            transaction_provenance_by_row[id(row)] = _build_transaction_provenance(
                merge_plan,
                source_file,
                source_row_number,
                original_values,
                file_mapping,
                final_columns,
            )

    rows = _apply_result_operations(rows, merge_plan.plan_json.get("result_operations", []))
    if limit is not None:
        rows = rows[:limit]
    transaction_provenance = [transaction_provenance_by_row[id(row)] for row in rows]
    return MergePreview(
        columns=final_columns,
        rows=rows,
        warnings=warnings,
        blocking_errors=blocking_errors,
        conversion_provenance=[provenance_by_row[id(row)] for row in rows],
        transaction_provenance=transaction_provenance,
        reconciliation=build_reconciliation_summary(
            rows,
            transaction_provenance,
            final_column_types,
            blocking_errors,
            merge_plan.plan_json.get("output_currency"),
        ),
    )


def _read_source_rows(
    source_file: MergesetFile,
) -> list[tuple[int, dict[str, str], dict[str, str]]]:
    """Read stored CSV rows with their original source line and values."""

    source_file.file.open("rb")
    try:
        raw_content = source_file.file.read()
    finally:
        source_file.file.close()

    content = decode_csv_content(raw_content)
    reader = csv.DictReader(
        StringIO(content, newline=""),
        fieldnames=source_file.headers,
        delimiter=source_file.delimiter or ",",
    )
    next(reader, None)
    rows = []
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        original_values = {key: value or "" for key, value in row.items()}
        source_row = {key: value.strip() for key, value in original_values.items()}
        if any(source_row.values()):
            rows.append((row_number, source_row, original_values))
    return rows


def _build_transaction_provenance(
    merge_plan: MergePlan,
    source_file: MergesetFile,
    source_row_number: int,
    original_values: dict[str, str],
    file_mapping: dict,
    final_columns: list[str],
) -> dict[str, str]:
    """Return an auditable record for one deterministic output row."""

    transformations = [
        {
            "target_column": mapping.get("target_column", ""),
            "source_columns": mapping.get("source_columns", []),
            "transform": mapping.get("transform", "copy"),
            "amount_format": mapping.get("amount_format"),
        }
        for mapping in file_mapping.get("mappings", [])
        if mapping.get("target_column") in final_columns
    ]
    return {
        "source_file": source_file.original_name,
        "source_row_number": str(source_row_number),
        "original_values": json.dumps(original_values, ensure_ascii=False, sort_keys=True),
        "mapping_plan_version": f"plan-{merge_plan.pk}",
        "transformations": json.dumps(transformations, separators=(",", ":")),
        "review_state": merge_plan.status,
    }


def _build_preview_row(
    final_columns: list[str],
    final_column_types: dict[str, str],
    file_mapping: dict,
    source_row: dict[str, str],
    source_file: MergesetFile,
    plan_json: dict,
    warnings: list[str],
    blocking_errors: list[str],
    conversion_provenance: list[dict[str, str]],
    rate_provider: ExchangeRateProvider | None,
) -> dict[str, str]:
    """Build one merged preview row from one source CSV row."""

    preview_row = {column: "" for column in final_columns}
    for mapping in file_mapping.get("mappings", []):
        target_column = mapping.get("target_column")
        if target_column not in preview_row:
            continue
        preview_row[target_column] = _apply_transform(
            mapping,
            source_row,
            source_file,
            final_column_types.get(target_column, ""),
            file_mapping,
            plan_json,
            warnings,
            blocking_errors,
            conversion_provenance,
            rate_provider,
        )
    return preview_row


def _apply_transform(
    mapping: dict,
    source_row: dict[str, str],
    source_file: MergesetFile,
    target_type: str = "",
    file_mapping: dict | None = None,
    plan_json: dict | None = None,
    warnings: list[str] | None = None,
    blocking_errors: list[str] | None = None,
    conversion_provenance: list[dict[str, str]] | None = None,
    rate_provider: ExchangeRateProvider | None = None,
) -> str:
    """Apply a supported transform to a source row."""

    source_columns = mapping.get("source_columns", [])
    values = [source_row.get(column, "") for column in source_columns]
    transform = mapping.get("transform")

    if transform == "combine_text":
        transformed_value = " ".join(value for value in values if value)
    elif transform in {"constant_source_name", "constant_filename"}:
        transformed_value = source_file.original_name
    elif transform == "parse_date":
        transformed_value = values[0] if values else ""
    elif transform == "debit_credit_to_signed_amount":
        transformed_value = _signed_amount(
            values[0] if values else "",
            values[1] if len(values) > 1 else "",
            mapping.get("amount_format"),
        )
    elif transform == "credit_debit_to_signed_amount":
        credit = values[0] if values else ""
        debit = values[1] if len(values) > 1 else ""
        transformed_value = _signed_amount(debit, credit, mapping.get("amount_format"))
    elif transform == "convert_currency":
        result = convert_currency(
            values[0] if values else "",
            source_row,
            file_mapping or {},
            plan_json or {},
            source_file,
            mapping.get("target_column", "this column"),
            mapping.get("amount_format"),
            rate_provider,
        )
        if result.warning:
            _add_warning(warnings if warnings is not None else [], result.warning)
        if result.blocking_error:
            add_blocking_exception(
                blocking_errors if blocking_errors is not None else [],
                result.blocking_error,
            )
        if result.provenance is not None:
            (conversion_provenance if conversion_provenance is not None else []).append(
                result.provenance
            )
        transformed_value = result.value
    elif transform == "ignore":
        transformed_value = ""
    else:
        transformed_value = values[0] if values else ""

    if transform == "parse_date" or target_type == "date":
        transformed_value = _normalize_date(transformed_value)
    if target_type == "money" and transform != "convert_currency":
        normalized_amount = normalize_amount(transformed_value, mapping.get("amount_format"))
        if normalized_amount is not None:
            transformed_value = normalized_amount
    validate_preview_value(
        blocking_errors if blocking_errors is not None else [],
        source_file.original_name,
        target_column=mapping.get("target_column", "this column"),
        target_type=target_type,
        transform=transform or "copy",
        value=transformed_value,
        amount_format=mapping.get("amount_format"),
    )
    return transformed_value


def _signed_amount(debit: str, credit: str, amount_format: dict | None) -> str:
    """Return one signed amount from debit and credit values."""

    debit_value = normalize_amount(debit, amount_format) or debit.strip()
    credit_value = normalize_amount(credit, amount_format) or credit.strip()
    if debit_value:
        return debit_value if debit_value.startswith("-") else f"-{debit_value}"
    return credit_value


def _add_warning(warnings: list[str], warning: str) -> None:
    """Append a warning once per preview."""

    if warning not in warnings:
        warnings.append(warning)


def _normalize_date(value: str) -> str:
    """Return a canonical ISO date when a common CSV date format is recognized."""

    parsed_date = parse_date(value)
    if parsed_date is None:
        return value.strip()
    return parsed_date.isoformat()


def _apply_result_operations(
    rows: list[dict[str, str]],
    operations: list[dict],
) -> list[dict[str, str]]:
    """Apply whole-result operations such as sorting."""

    for operation in operations:
        if operation.get("type") != "sort":
            continue
        column = operation.get("column")
        if not column:
            continue
        reverse = operation.get("direction") == "descending"
        rows = _sort_rows(rows, column, reverse=reverse)
    return rows


def _sort_rows(
    rows: list[dict[str, str]],
    column: str,
    reverse: bool = False,
) -> list[dict[str, str]]:
    """Sort dates chronologically when possible, otherwise sort as text."""

    dated_rows = []
    text_rows = []
    for index, row in enumerate(rows):
        value = row.get(column, "")
        parsed_date = parse_date(value)
        if parsed_date is None:
            text_rows.append((index, row))
            continue
        dated_rows.append((parsed_date, index, row))

    if dated_rows:
        sorted_dated_rows = sorted(
            dated_rows,
            key=lambda item: item[0],
            reverse=reverse,
        )
        return [row for _, _, row in sorted_dated_rows] + [row for _, row in text_rows]

    return sorted(rows, key=lambda row: row.get(column, ""), reverse=reverse)
