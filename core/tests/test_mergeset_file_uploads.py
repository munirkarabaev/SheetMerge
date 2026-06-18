"""Tests for source-file uploads attached to mergesets."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.forms.uploads import MAX_UPLOAD_SIZE
from core.models import Mergeset, MergesetFile
from core.services.csv_parser import MAX_SAMPLE_ROWS


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

    def test_owner_can_upload_multiple_csv_files(self) -> None:
        """A single request should store and parse every valid CSV file."""

        self.client.force_login(self.owner)

        response = self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile("bank.csv", b"date,amount\n2026-01-01,10"),
                    SimpleUploadedFile("card.csv", b"posted,merchant,total\n2026-01-02,Cafe,5"),
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
            ["bank.csv", "card.csv"],
        )
        self.assertFalse(
            self.mergeset.source_files.exclude(
                parse_status=MergesetFile.ParseStatus.PARSED
            ).exists()
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
        """Files outside the CSV-only scope should not be stored."""

        self.client.force_login(self.owner)

        response = self.client.post(
            self.upload_url,
            {"files": [SimpleUploadedFile("workbook.xlsx", b"not a CSV")]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "only CSV files are supported")
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

    def test_upload_control_supports_a_persistent_multiple_file_queue(self) -> None:
        """The workspace should render multiple selection and queue behavior."""

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "multiple")
        self.assertContains(response, "data-file-queue")
        self.assertContains(response, "core/js/file_upload.js")

    def test_upload_parses_headers_and_row_count(self) -> None:
        """Successful parsing should store metadata for AI suggestions."""

        self.client.force_login(self.owner)

        self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "bank.csv",
                        b"\xef\xbb\xbfDate,Description,Amount\n"
                        b"2026-01-01,Cafe,10\n"
                        b"2026-01-02,Shop,20\n",
                    )
                ]
            },
        )

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.parse_status, MergesetFile.ParseStatus.PARSED)
        self.assertEqual(source_file.headers, ["Date", "Description", "Amount"])
        self.assertEqual(
            source_file.sample_rows,
            [
                ["2026-01-01", "Cafe", "10"],
                ["2026-01-02", "Shop", "20"],
            ],
        )
        self.assertEqual(source_file.delimiter, ",")
        self.assertEqual(source_file.row_count, 2)
        self.assertEqual(source_file.parse_error, "")
        self.assertIsNotNone(source_file.parsed_at)

    def test_upload_limits_sample_rows_for_ai_context(self) -> None:
        """Parsing should keep a bounded sample of non-empty rows."""

        self.client.force_login(self.owner)
        rows = [f"2026-01-{day:02d},Merchant {day},{day}" for day in range(1, 15)]

        self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "bank.csv",
                        ("date,description,amount\n" + "\n".join(rows)).encode(),
                    )
                ]
            },
        )

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.row_count, 14)
        self.assertEqual(len(source_file.sample_rows), MAX_SAMPLE_ROWS)
        self.assertEqual(
            source_file.sample_rows[0],
            ["2026-01-01", "Merchant 1", "1"],
        )
        self.assertEqual(
            source_file.sample_rows[-1],
            ["2026-01-10", "Merchant 10", "10"],
        )

    def test_inconsistent_csv_is_stored_with_parse_error(self) -> None:
        """A malformed CSV should remain available with a useful error."""

        self.client.force_login(self.owner)

        self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "broken.csv",
                        b"date,description,amount\n2026-01-01,Cafe\n",
                    )
                ]
            },
        )

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.parse_status, MergesetFile.ParseStatus.FAILED)
        self.assertEqual(source_file.headers, [])
        self.assertEqual(source_file.sample_rows, [])
        self.assertIsNone(source_file.row_count)
        self.assertIn("Row 2 has 2 columns; expected 3", source_file.parse_error)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )
        self.assertContains(response, "Parse failed")
        self.assertContains(response, source_file.parse_error)

    def test_semicolon_delimited_csv_is_detected(self) -> None:
        """Common CSV delimiters should be detected before row parsing."""

        self.client.force_login(self.owner)

        self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "bank.csv",
                        b"date;description;amount\n2026-01-01;Cafe;10\n",
                    )
                ]
            },
        )

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.parse_status, MergesetFile.ParseStatus.PARSED)
        self.assertEqual(source_file.headers, ["date", "description", "amount"])
        self.assertEqual(source_file.delimiter, ";")
        self.assertEqual(source_file.row_count, 1)

    def test_legacy_encoded_csv_is_parsed(self) -> None:
        """Common legacy text encodings should be accepted."""

        self.client.force_login(self.owner)

        self.client.post(
            self.upload_url,
            {
                "files": [
                    SimpleUploadedFile(
                        "legacy.csv",
                        b"description,amount\nCaf\xe9,10\n",
                    )
                ]
            },
        )

        source_file = MergesetFile.objects.get()
        self.assertEqual(source_file.parse_status, MergesetFile.ParseStatus.PARSED)
        self.assertEqual(source_file.headers, ["description", "amount"])
        self.assertEqual(source_file.sample_rows, [["Café", "10"]])
        self.assertEqual(source_file.row_count, 1)
        self.assertEqual(source_file.parse_error, "")
