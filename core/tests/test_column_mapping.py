"""Tests for the AI-generated column mapping review page."""

import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    MergePlan,
    MergePlanningSession,
    Mergeset,
    MergesetFile,
)
from core.services import OpenAIPlanningError


User = get_user_model()


class ColumnMappingViewTests(TestCase):
    """Verify access and rendering for merge plan review."""

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
        """Create users and a user-owned mergeset."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Monthly statements",
            description="",
        )
        self.mapping_url = reverse(
            "core:mergeset_column_mapping",
            kwargs={"pk": self.mergeset.pk},
        )
        self.export_url = reverse(
            "core:mergeset_export_csv",
            kwargs={"pk": self.mergeset.pk},
        )

    def create_source_file(self) -> MergesetFile:
        """Create a parsed source file so AI suggestions can open."""

        return MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile(
                "bank.csv",
                b"Transaction Date,Description,Debit,Credit\n2026-01-01,Cafe,4.50,\n",
            ),
            original_name="bank.csv",
            file_size=100,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Transaction Date", "Description", "Debit", "Credit"],
            sample_rows=[["2026-01-01", "Cafe", "4.50", ""]],
            delimiter=",",
            row_count=1,
        )

    def create_merge_plan(self) -> MergePlan:
        """Create a reviewable merge plan."""

        source_file = self.create_source_file()
        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        return MergePlan.objects.create(
            mergeset=self.mergeset,
            session=session,
            status=MergePlan.Status.NEEDS_REVIEW,
            ai_summary="I mapped the date and amount fields for review.",
            plan_json={
                "status": "mapping_ready",
                "assistant_message": "I mapped the date and amount fields.",
                "questions": [],
                "final_columns": [
                    {"name": "Date", "type": "date"},
                    {"name": "Amount", "type": "money"},
                ],
                "file_mappings": [
                    {
                        "file_id": source_file.id,
                        "filename": "bank.csv",
                        "mappings": [
                            {
                                "target_column": "Date",
                                "source_columns": ["Transaction Date"],
                                "transform": "parse_date",
                                "notes": "",
                            },
                            {
                                "target_column": "Amount",
                                "source_columns": ["Debit", "Credit"],
                                "transform": "debit_credit_to_signed_amount",
                                "notes": "",
                            },
                        ],
                        "ignored_columns": ["Balance"],
                    }
                ],
            },
        )

    def test_column_mapping_requires_authentication(self) -> None:
        """Anonymous users should be redirected to login."""

        response = self.client.get(self.mapping_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.mapping_url}",
        )

    def test_column_mapping_is_limited_to_owner(self) -> None:
        """Another user should not see a private mapping plan."""

        self.create_merge_plan()
        self.client.force_login(self.other_user)

        response = self.client.get(self.mapping_url)

        self.assertEqual(response.status_code, 404)

    def test_column_mapping_redirects_without_plan(self) -> None:
        """Review should require a generated merge plan."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_ai_suggestions", kwargs={"pk": self.mergeset.pk}),
        )

    def test_column_mapping_renders_plan_details(self) -> None:
        """The review page should show final columns and file mappings."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review the AI mapping plan")
        self.assertContains(response, "I mapped the date and amount fields for review.")
        self.assertContains(response, "Date")
        self.assertContains(response, "Amount")
        self.assertContains(response, "bank.csv")
        self.assertContains(response, "Transaction Date")
        self.assertContains(response, "Debit, Credit")
        self.assertContains(response, "debit_credit_to_signed_amount")
        self.assertContains(response, "Balance")
        self.assertContains(response, "Spreadsheet result")
        self.assertContains(response, "Show preview")
        self.assertContains(response, "data-preview-table hidden")
        self.assertContains(response, "core/js/column_mapping.js")
        self.assertContains(response, "Ask AI to edit the result")
        self.assertContains(response, "Ask AI to revise")
        self.assertContains(response, "data-revision-form")
        self.assertContains(response, "data-revision-loading")
        self.assertContains(response, "data-revision-error")
        self.assertContains(response, "-4.50")
        self.assertContains(response, "Back to AI chat")
        self.assertContains(response, "Download CSV")
        self.assertContains(response, self.export_url)

    def test_column_mapping_post_requests_ai_revision(self) -> None:
        """Submitting a revision should call the AI revision service."""

        merge_plan = self.create_merge_plan()
        self.client.force_login(self.owner)

        with patch("core.views.mergesets.run_merge_plan_revision") as mock_revision:
            response = self.client.post(
                self.mapping_url,
                {"instruction": "Sort it in chronological order."},
            )

        self.assertRedirects(response, self.mapping_url)
        mock_revision.assert_called_once_with(
            merge_plan,
            "Sort it in chronological order.",
        )

    def test_column_mapping_async_post_returns_reload_url(self) -> None:
        """Async revisions should let the browser wait before reloading."""

        merge_plan = self.create_merge_plan()
        self.client.force_login(self.owner)

        with patch("core.views.mergesets.run_merge_plan_revision") as mock_revision:
            response = self.client.post(
                self.mapping_url,
                {"instruction": "Add a Source column."},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"redirect_url": self.mapping_url})
        mock_revision.assert_called_once_with(merge_plan, "Add a Source column.")

    def test_column_mapping_async_post_returns_revision_error(self) -> None:
        """Async AI failures should return inline error text for the page."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        with patch(
            "core.views.mergesets.run_merge_plan_revision",
            side_effect=OpenAIPlanningError("OPENAI_API_KEY is not configured."),
        ):
            response = self.client.post(
                self.mapping_url,
                {"instruction": "Add a Source column."},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"error": "OPENAI_API_KEY is not configured."},
        )

    def test_column_mapping_async_post_rejects_blank_revision(self) -> None:
        """Blank async revision requests should return validation JSON."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        with patch("core.views.mergesets.run_merge_plan_revision") as mock_revision:
            response = self.client.post(
                self.mapping_url,
                {"instruction": ""},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("instruction", response.json()["errors"])
        mock_revision.assert_not_called()

    def test_column_mapping_post_rejects_blank_revision(self) -> None:
        """Blank revision requests should not call the AI service."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        with patch("core.views.mergesets.run_merge_plan_revision") as mock_revision:
            response = self.client.post(self.mapping_url, {"instruction": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        mock_revision.assert_not_called()

    def test_csv_export_requires_authentication(self) -> None:
        """Anonymous users should be redirected before CSV export."""

        response = self.client.get(self.export_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.export_url}",
        )

    def test_csv_export_is_limited_to_owner(self) -> None:
        """Another user should not export a private merge result."""

        self.create_merge_plan()
        self.client.force_login(self.other_user)

        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, 404)

    def test_csv_export_redirects_without_plan(self) -> None:
        """Export should require a generated merge plan."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_ai_suggestions", kwargs={"pk": self.mergeset.pk}),
        )

    def test_csv_export_downloads_latest_merge_preview(self) -> None:
        """CSV export should match the deterministic mapped preview rows."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="monthly-statements.csv"',
        )
        self.assertEqual(
            response.content.decode(),
            "Date,Amount\r\n2026-01-01,-4.50\r\n",
        )

    def test_ai_suggestions_links_to_existing_mapping_plan(self) -> None:
        """AI suggestions should link to review when a plan exists."""

        self.create_merge_plan()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_ai_suggestions", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "Review column mapping")
        self.assertContains(response, self.mapping_url)
