"""Tests for approving reviewed merge plans."""

import csv
from io import StringIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import MergePlan, MergePlanningSession, Mergeset, MergesetFile


User = get_user_model()


class MappingApprovalTests(TestCase):
    """Verify mapping approval and approved-plan export behavior."""

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
        """Create users and a parsed source file."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(owner=self.owner, name="Statements")
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "bank.csv",
                b"Date,Amount\n2026-01-01,10.00\n",
            ),
            original_name="bank.csv",
            file_size=32,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Amount"],
            delimiter=",",
            row_count=1,
        )
        self.approve_url = reverse(
            "core:mergeset_approve_mapping",
            kwargs={"pk": self.mergeset.pk},
        )
        self.mapping_url = reverse(
            "core:mergeset_column_mapping",
            kwargs={"pk": self.mergeset.pk},
        )
        self.export_url = reverse(
            "core:mergeset_export_csv",
            kwargs={"pk": self.mergeset.pk},
        )

    def create_plan(self, target_column: str, status: str) -> MergePlan:
        """Create a merge plan that maps Amount into the named output column."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        return MergePlan.objects.create(
            mergeset=self.mergeset,
            session=session,
            status=status,
            ai_summary=f"Mapped {target_column}.",
            plan_json={
                "status": "mapping_ready",
                "assistant_message": "Ready.",
                "questions": [],
                "output_currency": None,
                "currency_conversion": {
                    "required": False,
                    "target_currency": None,
                    "rate_basis": "not_applicable",
                    "notes": "",
                },
                "final_columns": [{"name": target_column, "type": "money"}],
                "file_mappings": [
                    {
                        "file_id": self.source_file.id,
                        "filename": "bank.csv",
                        "detected_currency": {
                            "currency": None,
                            "confidence": "unknown",
                            "evidence": [],
                            "ambiguity": "",
                        },
                        "mappings": [
                            {
                                "target_column": target_column,
                                "source_columns": ["Amount"],
                                "transform": "copy",
                                "notes": "",
                            }
                        ],
                        "ignored_columns": [],
                    }
                ],
                "result_operations": [],
            },
        )

    def test_approve_mapping_requires_authentication(self) -> None:
        """Anonymous users should be redirected to login."""

        response = self.client.post(self.approve_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.approve_url}",
        )

    def test_approve_mapping_is_limited_to_owner(self) -> None:
        """Another user should not be able to approve a private plan."""

        self.create_plan("Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.other_user)

        response = self.client.post(self.approve_url)

        self.assertEqual(response.status_code, 404)

    def test_approve_mapping_marks_latest_plan_and_session_approved(self) -> None:
        """Approval should mark the latest plan as the chosen export plan."""

        old_plan = self.create_plan("Old Amount", MergePlan.Status.APPROVED)
        latest_plan = self.create_plan("Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.post(self.approve_url)

        self.assertRedirects(response, self.mapping_url)
        old_plan.refresh_from_db()
        latest_plan.refresh_from_db()
        latest_plan.session.refresh_from_db()
        self.assertEqual(old_plan.status, MergePlan.Status.NEEDS_REVIEW)
        self.assertEqual(latest_plan.status, MergePlan.Status.APPROVED)
        self.assertEqual(latest_plan.session.status, MergePlanningSession.Status.APPROVED)

    def test_column_mapping_shows_approval_action_and_approved_state(self) -> None:
        """Review page should expose approval and then show approved state."""

        self.create_plan("Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertContains(response, "Approve mapping")
        self.assertContains(response, self.approve_url)

        self.client.post(self.approve_url)
        response = self.client.get(self.mapping_url)

        self.assertContains(response, "Approved this mapping for export.")
        self.assertContains(response, "Status: Approved")
        self.assertContains(response, "Mapping approved")

    def test_export_prefers_approved_plan_over_newer_unapproved_plan(self) -> None:
        """CSV export should use the approved plan when one exists."""

        self.create_plan("Approved Amount", MergePlan.Status.APPROVED)
        self.create_plan("Latest Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[0], ["Approved Amount"])
        self.assertEqual(rows[1], ["10.00"])
