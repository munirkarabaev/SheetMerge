"""Tests for transaction-level merge provenance."""

import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import MergePlan, MergePlanningSession, Mergeset, MergesetFile
from core.services import build_merge_preview


User = get_user_model()


class TransactionProvenanceTests(TestCase):
    """Verify deterministic output retains its source audit trail."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root)
        super().tearDownClass()

    def test_provenance_tracks_original_row_after_sorting(self) -> None:
        """Sorting output rows must not detach their source audit records."""

        owner = User.objects.create_user(email="owner@example.com", password="test-pass-123")
        mergeset = Mergeset.objects.create(owner=owner, name="Statements")
        source_file = MergesetFile.objects.create(
            mergeset=mergeset,
            file=SimpleUploadedFile(
                "bank.csv",
                b"Date,Description,Amount\n2026-01-02,Second,20.00\n2026-01-01,First,10.00\n",
            ),
            original_name="bank.csv",
            file_size=80,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Description", "Amount"],
            delimiter=",",
            row_count=2,
        )
        session = MergePlanningSession.objects.create(mergeset=mergeset)
        plan = MergePlan.objects.create(
            mergeset=mergeset,
            session=session,
            status=MergePlan.Status.APPROVED,
            plan_json={
                "final_columns": [
                    {"name": "Date", "type": "date"},
                    {"name": "Description", "type": "text"},
                    {"name": "Amount", "type": "money"},
                ],
                "file_mappings": [{
                    "file_id": source_file.id,
                    "mappings": [
                        {"target_column": "Date", "source_columns": ["Date"], "transform": "parse_date"},
                        {"target_column": "Description", "source_columns": ["Description"], "transform": "copy"},
                        {"target_column": "Amount", "source_columns": ["Amount"], "transform": "parse_amount"},
                    ],
                }],
                "result_operations": [{"type": "sort", "column": "Date", "direction": "ascending"}],
            },
        )

        preview = build_merge_preview(plan)

        self.assertEqual([row["Description"] for row in preview.rows], ["First", "Second"])
        first_record = preview.transaction_provenance[0]
        self.assertEqual(first_record["source_file"], "bank.csv")
        self.assertEqual(first_record["source_row_number"], "3")
        self.assertEqual(json.loads(first_record["original_values"])["Description"], "First")
        self.assertEqual(first_record["mapping_plan_version"], f"plan-{plan.pk}")
        self.assertEqual(first_record["review_state"], MergePlan.Status.APPROVED)
        self.assertIn('"transform":"parse_amount"', first_record["transformations"])
