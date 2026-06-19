"""Build spreadsheet previews from generated merge plans."""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO

from core.models import MergePlan, MergesetFile
from core.services.csv_parser import decode_csv_content


@dataclass(frozen=True)
class MergePreview:
    """Preview rows generated from a merge plan."""

    columns: list[str]
    rows: list[dict[str, str]]


def build_merge_preview(merge_plan: MergePlan, limit: int | None = None) -> MergePreview:
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

        for source_row in _read_source_rows(source_file):
            rows.append(
                _build_preview_row(
                    final_columns,
                    final_column_types,
                    file_mapping,
                    source_row,
                    source_file,
                )
            )

    rows = _apply_result_operations(rows, merge_plan.plan_json.get("result_operations", []))
    if limit is not None:
        rows = rows[:limit]
    return MergePreview(columns=final_columns, rows=rows)


def _read_source_rows(source_file: MergesetFile) -> list[dict[str, str]]:
    """Read stored CSV rows as dictionaries keyed by parsed headers."""

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
    return [
        {key: (value or "").strip() for key, value in row.items()}
        for row in reader
        if row and any((value or "").strip() for value in row.values())
    ]


def _build_preview_row(
    final_columns: list[str],
    final_column_types: dict[str, str],
    file_mapping: dict,
    source_row: dict[str, str],
    source_file: MergesetFile,
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
        )
    return preview_row


def _apply_transform(
    mapping: dict,
    source_row: dict[str, str],
    source_file: MergesetFile,
    target_type: str = "",
) -> str:
    """Apply a supported transform to a source row."""

    source_columns = mapping.get("source_columns", [])
    values = [source_row.get(column, "") for column in source_columns]
    transform = mapping.get("transform")

    if transform == "combine_text":
        transformed_value = " ".join(value for value in values if value)
    elif transform == "constant_source_name":
        transformed_value = source_file.original_name
    elif transform == "parse_date":
        transformed_value = values[0] if values else ""
    elif transform == "debit_credit_to_signed_amount":
        transformed_value = _signed_amount(
            values[0] if values else "",
            values[1] if len(values) > 1 else "",
        )
    elif transform == "credit_debit_to_signed_amount":
        credit = values[0] if values else ""
        debit = values[1] if len(values) > 1 else ""
        transformed_value = _signed_amount(debit, credit)
    elif transform == "ignore":
        transformed_value = ""
    else:
        transformed_value = values[0] if values else ""

    if transform == "parse_date" or target_type == "date":
        return _normalize_date(transformed_value)
    return transformed_value


def _signed_amount(debit: str, credit: str) -> str:
    """Return one signed amount from debit and credit values."""

    debit_value = _clean_amount(debit)
    credit_value = _clean_amount(credit)
    if debit_value:
        return debit_value if debit_value.startswith("-") else f"-{debit_value}"
    return credit_value


def _clean_amount(value: str) -> str:
    """Normalize common currency formatting without changing precision."""

    cleaned_value = value.strip().replace(",", "").replace("£", "").replace("$", "")
    if cleaned_value.startswith("(") and cleaned_value.endswith(")"):
        return f"-{cleaned_value[1:-1]}"
    return cleaned_value


def _normalize_date(value: str) -> str:
    """Return a canonical ISO date when a common CSV date format is recognized."""

    parsed_date = _parse_date(value)
    if parsed_date is None:
        return value.strip()
    return parsed_date.isoformat()


def _parse_date(value: str) -> date | None:
    """Parse common bank-export date formats without guessing from row order."""

    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    try:
        return datetime.fromisoformat(cleaned_value.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    normalized_value = cleaned_value.replace(".", "/").replace("-", "/")
    formats = [
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    for date_format in formats:
        candidate = normalized_value if "/" in date_format else cleaned_value
        try:
            return datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    return None


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
        parsed_date = _parse_date(value)
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
