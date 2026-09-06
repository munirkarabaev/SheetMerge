"""Tests for approving reviewed merge plans."""

import csv
from decimal import Decimal
from io import StringIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ExchangeRate, MergePlan, MergePlanningSession, Mergeset, MergesetFile


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
        self.detail_url = reverse(
            "core:mergeset_detail",
            kwargs={"pk": self.mergeset.pk},
        )
        self.ai_chat_url = reverse(
            "core:mergeset_ai_suggestions",
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
        self.assertNotContains(response, "Back to AI chat")

    def test_unapproved_mapping_keeps_ai_chat_back_link(self) -> None:
        """Unapproved review should still allow returning to AI chat."""

        self.create_plan("Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertContains(response, "Back to AI chat")

    def test_approved_mergeset_detail_redirects_to_mapping_review(self) -> None:
        """Opening an approved mergeset should resume at mapping review."""

        self.create_plan("Amount", MergePlan.Status.APPROVED)
        self.client.force_login(self.owner)

        response = self.client.get(self.detail_url)

        self.assertRedirects(response, self.mapping_url)

    def test_approved_mergeset_cannot_reopen_ai_chat(self) -> None:
        """Approved workflows should redirect AI chat access back to review."""

        self.create_plan("Amount", MergePlan.Status.APPROVED)
        self.client.force_login(self.owner)

        response = self.client.get(self.ai_chat_url)

        self.assertRedirects(response, self.mapping_url)

    def test_export_prefers_approved_plan_over_newer_unapproved_plan(self) -> None:
        """CSV export should use the approved plan when one exists."""

        self.create_plan("Approved Amount", MergePlan.Status.APPROVED)
        self.create_plan("Latest Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[0][0], "Approved Amount")
        self.assertEqual(rows[1][0], "10.00")

    def test_export_redirects_unapproved_plan_to_mapping_review(self) -> None:
        """CSV export should require the owner to approve the mapping first."""

        self.create_plan("Amount", MergePlan.Status.NEEDS_REVIEW)
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url, follow=True)

        self.assertRedirects(response, self.mapping_url)
        self.assertContains(response, "Approve the column mapping before exporting a CSV.")

    def test_export_blocks_approved_plan_with_currency_exception(self) -> None:
        """CSV export should not use an unconverted amount as converted output."""

        plan = self.create_plan("Amount", MergePlan.Status.APPROVED)
        plan.plan_json["output_currency"] = "GBP"
        plan.plan_json["currency_conversion"] = {
            "required": True,
            "target_currency": "GBP",
            "rate_basis": "monthly_average",
            "notes": "Convert USD to GBP.",
        }
        file_mapping = plan.plan_json["file_mappings"][0]
        file_mapping["detected_currency"]["currency"] = "USD"
        file_mapping["mappings"][0]["transform"] = "convert_currency"
        plan.save(update_fields=["plan_json"])
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url, follow=True)

        self.assertRedirects(response, self.mapping_url)
        self.assertContains(response, "Resolve all preview exceptions before exporting a CSV.")
        self.assertContains(response, "Resolve these exceptions before CSV export:")

    def test_export_escapes_formula_like_cell_values(self) -> None:
        """CSV export should make source text safe for spreadsheet applications."""

        self.source_file.file.save(
            "bank.csv",
            ContentFile(b'Date,Amount\n2026-01-01,"=SUM(1,1)"\n'),
            save=True,
        )
        plan = self.create_plan("Amount", MergePlan.Status.APPROVED)
        plan.plan_json["final_columns"][0]["type"] = "text"
        plan.save(update_fields=["plan_json"])
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[1][0], "'=SUM(1,1)")

    def test_export_includes_currency_conversion_provenance(self) -> None:
        """Converted CSV rows should expose the rate data used for audit."""

        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="GBP",
            year=2026,
            month=1,
            average_rate=Decimal("0.80000000"),
            provider="test_rates",
        )
        plan = self.create_plan("Amount", MergePlan.Status.APPROVED)
        plan.plan_json["output_currency"] = "GBP"
        plan.plan_json["currency_conversion"] = {
            "required": True,
            "target_currency": "GBP",
            "rate_basis": "monthly_average",
            "notes": "Convert USD to GBP.",
        }
        file_mapping = plan.plan_json["file_mappings"][0]
        file_mapping["detected_currency"]["currency"] = "USD"
        file_mapping["mappings"][0]["transform"] = "convert_currency"
        file_mapping["mappings"].append(
            {
                "target_column": "Unused Date",
                "source_columns": ["Date"],
                "transform": "parse_date",
                "notes": "",
            }
        )
        plan.save(update_fields=["plan_json"])
        self.client.force_login(self.owner)

        response = self.client.get(self.export_url)

        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[0][-10:], [
            "Conversion target column", "Original amount", "Original currency",
            "Reporting amount", "Reporting currency", "Exchange rate",
            "Rate provider", "Rate period", "Rate policy", "Rounding policy",
        ])
        self.assertEqual(rows[1][-10:], [
            "Amount", "10.00", "USD", "8.00", "GBP", "0.80000000",
            "test_rates", "2026-01", "monthly_average", "half_up_2_decimal_places",
        ])
