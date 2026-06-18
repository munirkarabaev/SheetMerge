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
