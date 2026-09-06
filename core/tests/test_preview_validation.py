"""Tests for deterministic preview validation."""

from django.test import SimpleTestCase

from core.services.preview_validation import normalize_amount, validate_preview_value


class PreviewValidationTests(SimpleTestCase):
    """Verify preview values surface export-blocking exceptions."""

    def test_invalid_date_and_amount_are_blocking_exceptions(self) -> None:
        """Non-empty invalid typed values should require correction before export."""

        exceptions: list[str] = []

        validate_preview_value(
            exceptions,
            "bank.csv",
            "Date",
            "date",
            "parse_date",
            "not-a-date",
        )
        validate_preview_value(
            exceptions,
            "bank.csv",
            "Amount",
            "money",
            "copy",
            "unknown",
        )

        self.assertEqual(len(exceptions), 2)
        self.assertIn("not a recognized date", exceptions[0])
        self.assertIn("not a valid amount", exceptions[1])

    def test_normalizes_explicit_us_and_european_amount_formats(self) -> None:
        """Configured separators should produce the same canonical amount text."""

        self.assertEqual(
            normalize_amount("1,234.50", {"decimal_separator": ".", "thousands_separator": ","}),
            "1234.50",
        )
        self.assertEqual(
            normalize_amount("1.234,50", {"decimal_separator": ",", "thousands_separator": "."}),
            "1234.50",
        )
        self.assertIsNone(
            normalize_amount("1,23,4.50", {"decimal_separator": ".", "thousands_separator": ","})
        )
