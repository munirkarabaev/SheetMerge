"""Tests for the final approved merge workflow screen."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import MergePlan, MergePlanningSession, Mergeset, MergesetFile


User = get_user_model()


class WorkflowCompletionTests(TestCase):
    """Verify only safe, approved workflows reach the final screen."""

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

    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com", password="test-pass-123")
        self.mergeset = Mergeset.objects.create(owner=self.owner, name="Statements")
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "bank.csv",
                b"Date,Description,Amount\n2026-01-01,Ready,10.00\n",
            ),
            original_name="bank.csv",
            file_size=52,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Description", "Amount"],
            delimiter=",",
            row_count=1,
        )
        self.completion_url = reverse(
            "core:mergeset_workflow_complete",
            kwargs={"pk": self.mergeset.pk},
        )
        self.mapping_url = reverse(
            "core:mergeset_column_mapping",
            kwargs={"pk": self.mergeset.pk},
        )

    def create_plan(self, status: str, date_source: str = "Date") -> MergePlan:
        """Create a plan whose date mapping can be made deliberately invalid."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        return MergePlan.objects.create(
            mergeset=self.mergeset,
            session=session,
            status=status,
            plan_json={
                "final_columns": [
                    {"name": "Date", "type": "date"},
                    {"name": "Amount", "type": "money"},
                ],
                "file_mappings": [{
                    "file_id": self.source_file.id,
                    "mappings": [
                        {"target_column": "Date", "source_columns": [date_source], "transform": "parse_date"},
                        {"target_column": "Amount", "source_columns": ["Amount"], "transform": "parse_amount"},
                    ],
                }],
                "result_operations": [],
            },
        )

    def test_completion_requires_authentication(self) -> None:
        response = self.client.get(self.completion_url)

        self.assertRedirects(response, f"{reverse('account_login')}?next={self.completion_url}")

    def test_completion_requires_approved_plan(self) -> None:
        self.create_plan(MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.completion_url, follow=True)

        self.assertRedirects(response, self.mapping_url)
        self.assertContains(response, "Approve the column mapping before completing the workflow.")

    def test_completion_requires_exception_free_preview(self) -> None:
        self.create_plan(MergePlan.Status.APPROVED, date_source="Description")
        self.client.force_login(self.owner)

        response = self.client.get(self.completion_url, follow=True)

        self.assertRedirects(response, self.mapping_url)
        self.assertContains(response, "Resolve preview exceptions before completing the workflow.")

    def test_completion_renders_final_summary(self) -> None:
        plan = self.create_plan(MergePlan.Status.APPROVED)
        self.client.force_login(self.owner)

        response = self.client.get(self.completion_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workflow complete")
        self.assertContains(response, "Download CSV")
        self.assertContains(response, f"plan-{plan.pk}")
        self.assertContains(response, "10.00")
