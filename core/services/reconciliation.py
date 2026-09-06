"""Build deterministic reconciliation summaries for merge review."""

from dataclasses import dataclass
from decimal import Decimal

from core.services.preview_validation import parse_decimal_amount


@dataclass(frozen=True)
class ReconciliationSummary:
    """Totals and unresolved exceptions for one generated merge result."""

    output_row_count: int
    source_rows: list[dict[str, str]]
    money_totals: list[dict[str, str]]
    exceptions: list[dict[str, str]]


def build_reconciliation_summary(
    rows: list[dict[str, str]],
    transaction_provenance: list[dict[str, str]],
    final_column_types: dict[str, str],
    blocking_errors: list[str],
    output_currency: str | None,
) -> ReconciliationSummary:
    """Summarize deterministic output rows for accountant-facing review."""

    source_counts: dict[str, int] = {}
    for provenance in transaction_provenance:
        source_file = provenance["source_file"]
        source_counts[source_file] = source_counts.get(source_file, 0) + 1

    money_totals = []
    for column, column_type in final_column_types.items():
        if column_type != "money":
            continue
        total = Decimal("0")
        valid_row_count = 0
        for row in rows:
            amount = parse_decimal_amount(row.get(column, ""))
            if amount is not None:
                total += amount
                valid_row_count += 1
        money_totals.append(
            {
                "column": column,
                "total": format(total, "f"),
                "currency": output_currency or "source currency",
                "valid_row_count": str(valid_row_count),
            }
        )

    return ReconciliationSummary(
        output_row_count=len(rows),
        source_rows=[
            {"source_file": source_file, "row_count": str(row_count)}
            for source_file, row_count in source_counts.items()
        ],
        money_totals=money_totals,
        exceptions=[
            {
                "category": _exception_category(error),
                "message": error,
                "status": "Open",
            }
            for error in blocking_errors
        ],
    )


def _exception_category(error: str) -> str:
    """Classify deterministic exceptions for review without hiding their text."""

    lower_error = error.lower()
    if "date" in lower_error:
        return "Date"
    if "amount" in lower_error:
        return "Amount"
    if "currency" in lower_error or "exchange rate" in lower_error:
        return "Currency conversion"
    return "Mapping"
