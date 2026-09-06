"""Tests for deterministic merge reconciliation summaries."""

from django.test import SimpleTestCase

from core.services.reconciliation import build_reconciliation_summary


class ReconciliationSummaryTests(SimpleTestCase):
    """Verify totals, source coverage, and exceptions are reviewable."""

    def test_summary_groups_sources_and_totals_money_columns(self) -> None:
        """Reconciliation should use normalized output rows and provenance."""

        summary = build_reconciliation_summary(
            rows=[
                {"Date": "2026-01-01", "Amount": "10.50"},
                {"Date": "2026-01-02", "Amount": "-2.25"},
                {"Date": "2026-01-03", "Amount": ""},
            ],
            transaction_provenance=[
                {"source_file": "bank.csv"},
                {"source_file": "bank.csv"},
                {"source_file": "card.csv"},
            ],
            final_column_types={"Date": "date", "Amount": "money"},
            blocking_errors=[
                "bank.csv: 'not-a-date' is not a recognized date for Date.",
                "card.csv: currency conversion needs an exchange rate.",
            ],
            output_currency="GBP",
        )

        self.assertEqual(summary.output_row_count, 3)
        self.assertEqual(
            summary.source_rows,
            [
                {"source_file": "bank.csv", "row_count": "2"},
                {"source_file": "card.csv", "row_count": "1"},
            ],
        )
        self.assertEqual(
            summary.money_totals,
            [
                {
                    "column": "Amount",
                    "total": "8.25",
                    "currency": "GBP",
                    "valid_row_count": "2",
                }
            ],
        )
        self.assertEqual(
            [exception["category"] for exception in summary.exceptions],
            ["Date", "Currency conversion"],
        )
        self.assertTrue(all(exception["status"] == "Open" for exception in summary.exceptions))
