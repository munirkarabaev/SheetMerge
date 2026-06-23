"""Tests for building spreadsheet previews from merge plans."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import MergePlan, MergePlanningSession, Mergeset, MergesetFile
from core.services import build_merge_preview


User = get_user_model()


class MergePreviewServiceTests(TestCase):
    """Verify deterministic preview generation from uploaded CSVs."""

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
        """Create a mergeset and parsed source file."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Monthly statements",
            description="",
        )
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "bank.csv",
                (
                    b"Transaction Date,Description,Debit,Credit\n"
                    b"2026-01-01,Cafe,4.50,\n"
                    b"2026-01-02,Salary,,2200.00\n"
                ),
            ),
            original_name="bank.csv",
            file_size=93,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=2,
        )
        self.session = MergePlanningSession.objects.create(mergeset=self.mergeset)

    def create_merge_plan(self) -> MergePlan:
        """Create a merge plan using common transaction transforms."""

        return MergePlan.objects.create(
            mergeset=self.mergeset,
            session=self.session,
            status=MergePlan.Status.NEEDS_REVIEW,
            plan_json={
                "final_columns": [
                    {"name": "Date", "type": "date"},
                    {"name": "Description", "type": "text"},
                    {"name": "Amount", "type": "money"},
                    {"name": "Source", "type": "text"},
                ],
                "file_mappings": [
                    {
                        "file_id": self.source_file.id,
                        "filename": "bank.csv",
                        "mappings": [
                            {
                                "target_column": "Date",
                                "source_columns": ["Transaction Date"],
                                "transform": "parse_date",
                            },
                            {
                                "target_column": "Description",
                                "source_columns": ["Description"],
                                "transform": "copy",
                            },
                            {
                                "target_column": "Amount",
                                "source_columns": ["Debit", "Credit"],
                                "transform": "debit_credit_to_signed_amount",
                            },
                            {
                                "target_column": "Source",
                                "source_columns": [],
                                "transform": "constant_source_name",
                            },
                        ],
                        "ignored_columns": [],
                    }
                ],
            },
        )

    def test_build_merge_preview_applies_mapping_to_source_rows(self) -> None:
        """Preview rows should match the final columns from the plan."""

        preview = build_merge_preview(self.create_merge_plan())

        self.assertEqual(preview.columns, ["Date", "Description", "Amount", "Source"])
        self.assertEqual(
            preview.rows,
            [
                {
                    "Date": "2026-01-01",
                    "Description": "Cafe",
                    "Amount": "-4.50",
                    "Source": "bank.csv",
                },
                {
                    "Date": "2026-01-02",
                    "Description": "Salary",
                    "Amount": "2200.00",
                    "Source": "bank.csv",
                },
            ],
        )

    def test_build_merge_preview_accepts_constant_filename_alias(self) -> None:
        """Existing plans using constant_filename should show the source name."""

        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["mappings"][3]["transform"] = (
            "constant_filename"
        )
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(
            [row["Source"] for row in preview.rows],
            ["bank.csv", "bank.csv"],
        )

    def test_build_merge_preview_does_not_double_negate_signed_debits(self) -> None:
        """Signed debit values should not receive a second minus sign."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "signed-debits.csv",
                (
                    b"Transaction Date,Description,Debit,Credit\n"
                    b"2026-01-01,Cafe,-4.50,\n"
                    b"2026-01-02,Refund,,2.00\n"
                    b"2026-01-03,Fee,(3.25),\n"
                ),
            ),
            original_name="signed-debits.csv",
            file_size=140,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=3,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(
            [row["Amount"] for row in preview.rows],
            ["-4.50", "2.00", "-3.25"],
        )

    def test_build_merge_preview_respects_row_limit(self) -> None:
        """Preview generation should cap rows for page rendering."""

        preview = build_merge_preview(self.create_merge_plan(), limit=1)

        self.assertEqual(len(preview.rows), 1)

    def test_build_merge_preview_applies_sort_operation(self) -> None:
        """Result operations should sort mapped rows after merging."""

        plan = self.create_merge_plan()
        plan.plan_json["result_operations"] = [
            {"type": "sort", "column": "Date", "direction": "descending"}
        ]
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows[0]["Date"], "2026-01-02")
        self.assertEqual(preview.rows[1]["Date"], "2026-01-01")

    def test_build_merge_preview_normalizes_common_date_formats(self) -> None:
        """Date transforms should convert source dates to one canonical format."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "mixed-dates.csv",
                (
                    b"Transaction Date,Description,Debit,Credit\n"
                    b"01/02/2026,Cafe,4.50,\n"
                    b"2026-03-04T10:15:00,Shop,6.00,\n"
                    b"5 Apr 2026,Train,7.25,\n"
                ),
            ),
            original_name="mixed-dates.csv",
            file_size=150,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=3,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(
            [row["Date"] for row in preview.rows],
            ["2026-02-01", "2026-03-04", "2026-04-05"],
        )

    def test_build_merge_preview_normalizes_date_typed_columns_when_copied(self) -> None:
        """Date output columns should normalize even when the transform is copy."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "copy-date.csv",
                b"Transaction Date,Description,Debit,Credit\n01/02/2026,Cafe,4.50,\n",
            ),
            original_name="copy-date.csv",
            file_size=80,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=1,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.plan_json["file_mappings"][0]["mappings"][0]["transform"] = "copy"
        plan.plan_json["file_mappings"][0]["mappings"][0]["source_columns"] = [
            "Transaction Date"
        ]
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows[0]["Date"], "2026-02-01")

    def test_build_merge_preview_sorts_normalized_dates_chronologically(self) -> None:
        """Sort operations should use chronological date order after normalization."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "unsorted-dates.csv",
                (
                    b"Transaction Date,Description,Debit,Credit\n"
                    b"15/01/2026,Middle,4.50,\n"
                    b"2026-01-03,First,6.00,\n"
                    b"02/02/2026,Last,7.25,\n"
                ),
            ),
            original_name="unsorted-dates.csv",
            file_size=150,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=3,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.plan_json["result_operations"] = [
            {"type": "sort", "column": "Date", "direction": "ascending"}
        ]
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(
            [row["Description"] for row in preview.rows],
            ["First", "Middle", "Last"],
        )
        self.assertEqual(
            [row["Date"] for row in preview.rows],
            ["2026-01-03", "2026-01-15", "2026-02-02"],
        )

    def test_build_merge_preview_keeps_unrecognized_dates_at_end_when_sorting(self) -> None:
        """Rows with unparseable dates should remain visible after valid dated rows."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "bad-date.csv",
                (
                    b"Transaction Date,Description,Debit,Credit\n"
                    b"not a date,Unknown,4.50,\n"
                    b"2026-01-03,Known,6.00,\n"
                ),
            ),
            original_name="bad-date.csv",
            file_size=100,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=2,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.plan_json["result_operations"] = [
            {"type": "sort", "column": "Date", "direction": "ascending"}
        ]
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(
            [row["Description"] for row in preview.rows],
            ["Known", "Unknown"],
        )
        self.assertEqual(preview.rows[-1]["Date"], "not a date")

    def test_build_merge_preview_defaults_to_all_rows(self) -> None:
        """Default preview generation should not truncate spreadsheet rows."""

        rows = [
            f"2026-02-{day:02d},Merchant {day},{day},"
            for day in range(1, 31)
        ]
        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "many.csv",
                ("Transaction Date,Description,Debit,Credit\n" + "\n".join(rows)).encode(),
            ),
            original_name="many.csv",
            file_size=1000,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=30,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(len(preview.rows), 30)
        self.assertEqual(preview.rows[-1]["Description"], "Merchant 30")

    def test_build_merge_preview_skips_missing_source_files(self) -> None:
        """Plans referencing unavailable files should not crash previewing."""

        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = 99999
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows, [])

    def test_build_merge_preview_reads_legacy_encoded_csv(self) -> None:
        """Preview generation should reuse tolerant CSV decoding."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "legacy.csv",
                b"Transaction Date,Description,Debit,Credit\n2026-03-01,Caf\xe9,5,\n",
            ),
            original_name="legacy.csv",
            file_size=64,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            delimiter=",",
            row_count=1,
        )
        plan = self.create_merge_plan()
        plan.plan_json["file_mappings"][0]["file_id"] = source_file.id
        plan.save(update_fields=["plan_json"])

        preview = build_merge_preview(plan)

        self.assertEqual(preview.rows[0]["Description"], "Café")
