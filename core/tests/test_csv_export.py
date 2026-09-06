"""Tests for safe CSV export values."""

from django.test import SimpleTestCase

from core.services.csv_export import escape_spreadsheet_formula


class CsvExportTests(SimpleTestCase):
    """Verify formula-like spreadsheet values are neutralized."""

    def test_escapes_formula_like_text(self) -> None:
        """Formula prefixes should be rendered as literal text."""

        for value in ("=SUM(A1:A2)", "+SUM(A1:A2)", "-cmd|A1", "@SUM(A1:A2)"):
            with self.subTest(value=value):
                self.assertEqual(escape_spreadsheet_formula(value), f"'{value}")

    def test_preserves_signed_numeric_amounts(self) -> None:
        """Valid numeric amounts should remain usable numeric cells."""

        self.assertEqual(escape_spreadsheet_formula("-4.50"), "-4.50")
        self.assertEqual(escape_spreadsheet_formula("+12.00"), "+12.00")
