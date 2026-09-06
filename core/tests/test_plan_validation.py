"""Tests for semantic validation of AI-proposed merge plans."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import Mergeset, MergesetFile
from core.services.plan_validation import MergePlanValidationError, validate_merge_plan_payload


User = get_user_model()


class MergePlanValidationTests(TestCase):
    """Verify mapping-ready plans are safe before persistence."""

    def setUp(self) -> None:
        owner = User.objects.create_user(email="owner@example.com", password="test-pass-123")
        self.mergeset = Mergeset.objects.create(owner=owner, name="Statements")
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile("bank.csv", b"Date,Amount\n2026-01-01,10.00\n"),
            original_name="bank.csv",
            file_size=32,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Amount"],
            delimiter=",",
            row_count=1,
        )

    def payload(self) -> dict:
        return {
            "status": "mapping_ready",
            "output_currency": None,
            "currency_conversion": {"required": False, "target_currency": None},
            "final_columns": [{"name": "Date", "type": "date"}, {"name": "Amount", "type": "money"}],
            "file_mappings": [{
                "file_id": self.source_file.id,
                "detected_currency": {"currency": "USD", "confidence": "high"},
                "mappings": [
                    {"target_column": "Date", "source_columns": ["Date"], "transform": "parse_date"},
                    {"target_column": "Amount", "source_columns": ["Amount"], "transform": "parse_amount", "amount_format": {"decimal_separator": ".", "thousands_separator": ","}},
                ],
            }],
            "result_operations": [{"type": "sort", "column": "Date", "direction": "ascending"}],
        }

    def test_accepts_plan_with_known_columns_and_valid_rules(self) -> None:
        validate_merge_plan_payload(self.mergeset, self.payload())

    def test_rejects_unknown_source_column(self) -> None:
        payload = self.payload()
        payload["file_mappings"][0]["mappings"][0]["source_columns"] = ["Posted"]

        with self.assertRaisesMessage(MergePlanValidationError, "source column"):
            validate_merge_plan_payload(self.mergeset, payload)

    def test_rejects_invalid_amount_separator_rule(self) -> None:
        payload = self.payload()
        payload["file_mappings"][0]["mappings"][1]["amount_format"] = {
            "decimal_separator": ".",
            "thousands_separator": ".",
        }

        with self.assertRaisesMessage(MergePlanValidationError, "separators must differ"):
            validate_merge_plan_payload(self.mergeset, payload)

    def test_rejects_low_confidence_currency_conversion(self) -> None:
        payload = self.payload()
        payload["output_currency"] = "GBP"
        payload["currency_conversion"] = {"required": True, "target_currency": "GBP"}
        payload["file_mappings"][0]["detected_currency"]["confidence"] = "low"
        payload["file_mappings"][0]["mappings"][1]["transform"] = "convert_currency"

        with self.assertRaisesMessage(MergePlanValidationError, "low confidence"):
            validate_merge_plan_payload(self.mergeset, payload)
