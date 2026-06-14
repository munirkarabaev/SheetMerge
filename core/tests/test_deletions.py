"""Tests for owner-scoped mergeset and source-file deletion."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Mergeset, MergesetFile


User = get_user_model()


class MergesetDeletionTests(TestCase):
    """Verify deletion access control, cascades, and storage cleanup."""

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
        """Create users, a mergeset, and one stored source file."""

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
        self.source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile("bank.csv", b"date,amount\n2026-01-01,10\n"),
            original_name="bank.csv",
            file_size=29,
        )
        self.stored_name = self.source_file.file.name

    def test_owner_can_delete_uploaded_file_and_stored_content(self) -> None:
        """Deleting one source file should remove its row and stored content."""

        self.client.force_login(self.owner)
        delete_url = reverse(
            "core:mergeset_file_delete",
            kwargs={"pk": self.mergeset.pk, "file_pk": self.source_file.pk},
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(delete_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )
        self.assertFalse(MergesetFile.objects.exists())
        self.assertFalse(self.source_file.file.storage.exists(self.stored_name))
        self.assertTrue(Mergeset.objects.filter(pk=self.mergeset.pk).exists())

    def test_non_owner_cannot_delete_uploaded_file(self) -> None:
        """A user should not delete another user's uploaded file."""

        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "core:mergeset_file_delete",
                kwargs={"pk": self.mergeset.pk, "file_pk": self.source_file.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(MergesetFile.objects.filter(pk=self.source_file.pk).exists())
        self.assertTrue(self.source_file.file.storage.exists(self.stored_name))

    def test_file_delete_requires_matching_mergeset(self) -> None:
        """A file cannot be deleted through another mergeset's URL."""

        other_mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Other statements",
            description="",
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "core:mergeset_file_delete",
                kwargs={"pk": other_mergeset.pk, "file_pk": self.source_file.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(MergesetFile.objects.filter(pk=self.source_file.pk).exists())

    def test_owner_can_delete_mergeset_with_cascaded_file_cleanup(self) -> None:
        """Deleting a mergeset should cascade records and stored files."""

        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("core:mergeset_delete", kwargs={"pk": self.mergeset.pk})
            )

        self.assertRedirects(response, reverse("core:mergeset_list"))
        self.assertFalse(Mergeset.objects.filter(pk=self.mergeset.pk).exists())
        self.assertFalse(MergesetFile.objects.exists())
        self.assertFalse(self.source_file.file.storage.exists(self.stored_name))

    def test_non_owner_cannot_delete_mergeset(self) -> None:
        """A user should not delete another user's mergeset."""

        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("core:mergeset_delete", kwargs={"pk": self.mergeset.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Mergeset.objects.filter(pk=self.mergeset.pk).exists())
        self.assertTrue(MergesetFile.objects.filter(pk=self.source_file.pk).exists())

    def test_delete_endpoints_require_authentication(self) -> None:
        """Anonymous deletion attempts should redirect to login."""

        urls = [
            reverse("core:mergeset_delete", kwargs={"pk": self.mergeset.pk}),
            reverse(
                "core:mergeset_file_delete",
                kwargs={"pk": self.mergeset.pk, "file_pk": self.source_file.pk},
            ),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(
                    response,
                    f"{reverse('account_login')}?next={url}",
                )

    def test_delete_endpoints_reject_get_requests(self) -> None:
        """Destructive endpoints should only accept POST requests."""

        self.client.force_login(self.owner)
        urls = [
            reverse("core:mergeset_delete", kwargs={"pk": self.mergeset.pk}),
            reverse(
                "core:mergeset_file_delete",
                kwargs={"pk": self.mergeset.pk, "file_pk": self.source_file.pk},
            ),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 405)

    def test_workspace_shows_mergeset_and_file_delete_options(self) -> None:
        """The workspace should expose both destructive actions."""

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "Delete mergeset")
        self.assertContains(
            response,
            reverse(
                "core:mergeset_file_delete",
                kwargs={"pk": self.mergeset.pk, "file_pk": self.source_file.pk},
            ),
        )
