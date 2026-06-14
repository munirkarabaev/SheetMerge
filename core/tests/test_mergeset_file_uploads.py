"""Tests for source-file uploads attached to mergesets."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.forms.uploads import MAX_UPLOAD_SIZE
from core.models import Mergeset, MergesetFile


User = get_user_model()


class MergesetFileUploadTests(TestCase):
    """Verify validation, ownership, and storage for source files."""

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
            description="Merge bank exports.",
        )
        self.upload_url = reverse(
            "core:mergeset_file_upload",
            kwargs={"pk": self.mergeset.pk},
        )

    def test_owner_can_upload_multiple_supported_files(self) -> None:
        """A single request should store every valid CSV and XLSX file."""

        self.client.force_login(self.owner)

        response = self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile("bank.csv", b"date,amount\n2026-01-01,10"),
                    SimpleUploadedFile(
                        "card.xlsx",
                        b"placeholder workbook content",
                        content_type=(
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),
                    ),
                ]
            },
        )

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )
        self.assertEqual(self.mergeset.source_files.count(), 2)
        self.assertSequenceEqual(
            self.mergeset.source_files.values_list("original_name", flat=True),
            ["bank.csv", "card.xlsx"],
        )

    def test_upload_records_size_and_uses_generated_storage_name(self) -> None:
        """Stored metadata should retain the original filename and byte size."""

        self.client.force_login(self.owner)
        uploaded_file = SimpleUploadedFile("source.csv", b"amount\n15")

        self.client.post(self.upload_url, {"files": [uploaded_file]})

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.original_name, "source.csv")
        self.assertEqual(source_file.file_size, 9)
        self.assertTrue(source_file.file.name.startswith(f"mergesets/{self.mergeset.pk}/sources/"))
        self.assertTrue(source_file.file.name.endswith(".csv"))

    def test_unsupported_file_extension_is_rejected(self) -> None:
        """Files outside the initial CSV/XLSX scope should not be stored."""

        self.client.force_login(self.owner)

        response = self.client.post(
            self.upload_url,
            {"files": [SimpleUploadedFile("notes.txt", b"not a spreadsheet")]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "only CSV and XLSX files are supported")
        self.assertFalse(MergesetFile.objects.exists())

    def test_oversized_file_is_rejected(self) -> None:
        """Source files above the per-file limit should not be stored."""

        self.client.force_login(self.owner)

        response = self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "large.csv",
                        b"x" * (MAX_UPLOAD_SIZE + 1),
                    )
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "files must be 10 MB or smaller")
        self.assertFalse(MergesetFile.objects.exists())

    def test_non_owner_cannot_upload_to_mergeset(self) -> None:
        """A user should not attach files to another user's mergeset."""

        self.client.force_login(self.other_user)

        response = self.client.post(
            self.upload_url,
            {"files": [SimpleUploadedFile("bank.csv", b"amount\n10")]},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MergesetFile.objects.exists())

    def test_upload_requires_authentication(self) -> None:
        """Anonymous upload attempts should redirect to login."""

        response = self.client.post(
            self.upload_url,
            {"files": [SimpleUploadedFile("bank.csv", b"amount\n10")]},
        )

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.upload_url}",
        )
        self.assertFalse(MergesetFile.objects.exists())

    def test_detail_page_lists_uploaded_source_files(self) -> None:
        """The mergeset workspace should show its uploaded filenames."""

        MergesetFile.objects.create(
            mergeset=self.mergeset,
            file=SimpleUploadedFile("stored.csv", b"amount\n10"),
            original_name="bank-january.csv",
            file_size=9,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "bank-january.csv")
        self.assertContains(response, "Uploaded")
