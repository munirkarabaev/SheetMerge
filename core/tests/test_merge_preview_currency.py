"""Tests for currency conversion in merge previews."""

from decimal import Decimal
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import ExchangeRate, MergePlan, MergePlanningSession, Mergeset, MergesetFile
from core.services import build_merge_preview


User = get_user_model()


class MergePreviewCurrencyTests(TestCase):
    """Verify deterministic currency conversion behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        """Use isolated storage for uploaded test files."""

        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove isolated uploaded files after the test class."""

        cls.settings_override.disable()
        shutil.rmtree(cls.media_root)
        super().tearDownClass()

    def setUp(self) -> None:
        """Create a parsed source file and merge plan."""

        owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(owner=owner, name="Currencies")
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "usd.csv",
                b"Date,Amount\n2026-05-15,10.00\n2026-05-20,2.50\n",
            ),
            original_name="usd.csv",
            file_size=52,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Amount"],
            delimiter=",",
            row_count=2,
        )
        self.session = MergePlanningSession.objects.create(mergeset=self.mergeset)

    def create_plan(self) -> MergePlan:
        """Create a plan with currency conversion enabled."""

        return MergePlan.objects.create(
            mergeset=self.mergeset,
            session=self.session,
            status=MergePlan.Status.NEEDS_REVIEW,
            plan_json={
                "output_currency": "GBP",
                "currency_conversion": {
                    "required": True,
                    "target_currency": "GBP",
                    "rate_basis": "monthly_average",
                    "notes": "Convert USD to GBP.",
                },
                "final_columns": [
                    {"name": "Date", "type": "date"},
                    {"name": "Amount", "type": "money"},
                ],
                "file_mappings": [
                    {
                        "file_id": self.source_file.id,
                        "filename": "usd.csv",
                        "detected_currency": {
                            "currency": "USD",
                            "confidence": "high",
                            "evidence": ["Currency column contains USD"],
                            "ambiguity": "",
                        },
                        "mappings": [
                            {
                                "target_column": "Date",
                                "source_columns": ["Date"],
                                "transform": "parse_date",
                                "notes": "",
                            },
                            {
                                "target_column": "Amount",
                                "source_columns": ["Amount"],
                                "transform": "convert_currency",
                                "notes": "",
                            },
                        ],
                        "ignored_columns": [],
                    }
                ],
                "result_operations": [],
            },
        )

    def test_convert_currency_uses_cached_monthly_rate(self) -> None:
        """Currency conversion should use the row month's cached rate."""

        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="GBP",
            year=2026,
            month=5,
            average_rate=Decimal("0.80000000"),
            provider="test",
        )

        preview = build_merge_preview(self.create_plan())

        self.assertEqual([row["Amount"] for row in preview.rows], ["8.00", "2.00"])
        self.assertEqual(preview.warnings, [])

    def test_convert_currency_blanks_amount_when_date_is_missing(self) -> None:
        """Rows without a usable date should leave converted amounts blank."""

        plan = self.create_plan()
        plan.plan_json["file_mappings"][0]["mappings"][0]["source_columns"] = [
            "Missing Date"
        ]
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual([row["Amount"] for row in preview.rows], ["", ""])
        self.assertEqual(len(preview.warnings), 1)
        self.assertIn("currency conversion failed", preview.warnings[0])
        self.assertIn("recognized row date", preview.warnings[0])
        self.assertEqual(len(preview.blocking_errors), 1)

    def test_convert_currency_keeps_original_amount_when_currency_is_missing(self) -> None:
        """Rows without a detected source currency should keep the source value."""

        plan = self.create_plan()
        plan.plan_json["file_mappings"][0]["detected_currency"]["currency"] = None
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows[0]["Amount"], "")
        self.assertEqual(len(preview.warnings), 1)
        self.assertIn("source or target currency is missing", preview.warnings[0])
        self.assertEqual(len(preview.blocking_errors), 1)

    def test_convert_currency_blanks_invalid_amount(self) -> None:
        """Invalid amount text should not appear in a converted-amount column."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile("bad.csv", b"Date,Amount\n2026-05-15,unknown\n"),
            original_name="bad.csv",
            file_size=32,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Amount"],
            delimiter=",",
            row_count=1,
        )
        plan = self.create_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows[0]["Amount"], "")
        self.assertEqual(len(preview.warnings), 1)
        self.assertIn("could not be parsed", preview.warnings[0])
        self.assertEqual(len(preview.blocking_errors), 1)
