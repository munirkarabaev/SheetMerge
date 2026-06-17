"""Tests for the initial column-mapping workspace."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Mergeset, MergesetFile


User = get_user_model()


class ColumnMappingViewTests(TestCase):
    """Verify mapping readiness, ownership, and parsed-header rendering."""

    def setUp(self) -> None:
        """Create users and an owner-scoped mergeset."""

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
            "core:mergeset_mapping",
            kwargs={"pk": self.mergeset.pk},
        )

    def create_source_file(self, **overrides) -> MergesetFile:
        """Create source-file metadata for mapping-page tests."""

        values = {
            "mergeset": self.mergeset,
            "file": "mergesets/test/sources/bank.csv",
            "original_name": "bank.csv",
            "file_size": 100,
            "parse_status": MergesetFile.ParseStatus.PARSED,
            "headers": ["Transaction Date", "Description", "Amount"],
            "delimiter": ",",
            "row_count": 12,
        }
        values.update(overrides)
        return MergesetFile.objects.create(**values)

    def test_mapping_requires_authentication(self) -> None:
        """Anonymous users should be redirected to login."""

        response = self.client.get(self.mapping_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.mapping_url}",
        )

    def test_mapping_is_limited_to_owner(self) -> None:
        """Another user should not see a mergeset's parsed headers."""

        self.create_source_file()
        self.client.force_login(self.other_user)

        response = self.client.get(self.mapping_url)

        self.assertEqual(response.status_code, 404)

    def test_mapping_redirects_when_no_files_are_ready(self) -> None:
        """Mapping should not open before a parsed source file exists."""

        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )

    def test_upload_page_disables_mapping_action_without_parsed_files(self) -> None:
        """The upload step should explain why mapping is unavailable."""

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, 'class="ws-btn-disabled"')
        self.assertContains(
            response,
            "Upload at least one CSV and resolve parsing errors to continue.",
        )
        self.assertNotContains(response, f'href="{self.mapping_url}"')

    def test_mapping_redirects_when_any_file_failed_parsing(self) -> None:
        """All uploaded files must parse successfully before mapping."""

        self.create_source_file()
        self.create_source_file(
            original_name="broken.csv",
            parse_status=MergesetFile.ParseStatus.FAILED,
            headers=[],
            row_count=None,
            parse_error="Invalid row.",
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )

    def test_mapping_page_lists_parsed_headers_and_ai_panel(self) -> None:
        """Ready files should render their headers beside the assistant."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(self.mapping_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transaction Date")
        self.assertContains(response, "Description")
        self.assertContains(response, "Amount")
        self.assertContains(response, "Mapping assistant")
        self.assertContains(response, "Suggest mapping")

    def test_upload_page_enables_mapping_action_when_all_files_are_parsed(self) -> None:
        """The proceed action should link to mapping when parsing is complete."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "Proceed to column mapping")
        self.assertContains(response, self.mapping_url)
