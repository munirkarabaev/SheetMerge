"""Tests for the initial AI suggestion workspace."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import (
    MergePlanningMessage,
    MergePlanningSession,
    Mergeset,
    MergesetFile,
)


User = get_user_model()


class AISuggestionsViewTests(TestCase):
    """Verify suggestion readiness, ownership, and parsed-header rendering."""

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
        self.ai_suggestions_url = reverse(
            "core:mergeset_ai_suggestions",
            kwargs={"pk": self.mergeset.pk},
        )

    def create_source_file(self, **overrides) -> MergesetFile:
        """Create source-file metadata for AI suggestion page tests."""

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

    def test_ai_suggestions_require_authentication(self) -> None:
        """Anonymous users should be redirected to login."""

        response = self.client.get(self.ai_suggestions_url)

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.ai_suggestions_url}",
        )

    def test_ai_suggestions_are_limited_to_owner(self) -> None:
        """Another user should not see a mergeset's parsed headers."""

        self.create_source_file()
        self.client.force_login(self.other_user)

        response = self.client.get(self.ai_suggestions_url)

        self.assertEqual(response.status_code, 404)

    def test_ai_suggestions_redirect_when_no_files_are_ready(self) -> None:
        """AI suggestions should not open before a parsed source file exists."""

        self.client.force_login(self.owner)

        response = self.client.get(self.ai_suggestions_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )

    def test_upload_page_disables_ai_suggestions_without_parsed_files(self) -> None:
        """The upload step should explain why AI suggestions are unavailable."""

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, 'class="ws-btn-disabled"')
        self.assertContains(
            response,
            "Upload at least one CSV and resolve parsing errors to continue.",
        )
        self.assertContains(response, "Proceed to AI suggestions")
        self.assertContains(response, "AI suggestions")
        self.assertNotContains(response, "Proceed to column mapping")
        self.assertNotContains(response, "Column mapping")
        self.assertNotContains(response, f'href="{self.ai_suggestions_url}"')

    def test_ai_suggestions_redirect_when_any_file_failed_parsing(self) -> None:
        """All uploaded files must parse successfully before AI suggestions."""

        self.create_source_file()
        self.create_source_file(
            original_name="broken.csv",
            parse_status=MergesetFile.ParseStatus.FAILED,
            headers=[],
            row_count=None,
            parse_error="Invalid row.",
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.ai_suggestions_url)

        self.assertRedirects(
            response,
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
        )

    def test_ai_suggestions_page_renders_instructions_without_source_listing(self) -> None:
        """Ready files should render the AI assistant without source listings."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(self.ai_suggestions_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI suggestion assistant")
        self.assertContains(response, "Send message")
        self.assertContains(response, "Run AI merge plan")
        self.assertContains(response, "Your instructions")
        content = response.content.decode()
        textarea_start = content.index('id="ai-instructions"')
        textarea_end = content.index("</textarea>", textarea_start)
        self.assertNotIn("disabled", content[textarea_start:textarea_end])
        self.assertNotContains(response, "bank.csv")
        self.assertNotContains(response, "Transaction Date")
        self.assertNotContains(response, "Scanned source")
        self.assertNotContains(response, "Detected source columns")
        self.assertNotContains(response, "Awaiting suggestion")
        self.assertNotContains(response, "<select")

    def test_upload_page_enables_ai_suggestions_when_all_files_are_parsed(self) -> None:
        """The proceed action should link to AI suggestions when parsing is complete."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk})
        )

        self.assertContains(response, "Proceed to AI suggestions")
        self.assertNotContains(response, "Proceed to column mapping")
        self.assertNotContains(response, "Column mapping")
        self.assertContains(response, self.ai_suggestions_url)

    def test_ai_suggestions_page_creates_planning_session(self) -> None:
        """Opening AI suggestions should prepare a conversation session."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.get(self.ai_suggestions_url)

        self.assertEqual(response.status_code, 200)
        session = MergePlanningSession.objects.get()
        self.assertEqual(session.mergeset, self.mergeset)
        self.assertContains(response, "Collecting requirements")

    def test_ai_suggestions_page_renders_existing_messages(self) -> None:
        """Stored planning messages should appear in the assistant panel."""

        self.create_source_file()
        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        MergePlanningMessage.objects.create(
            session=session,
            role=MergePlanningMessage.Role.USER,
            content="Use Date, Description, and signed Amount.",
        )
        MergePlanningMessage.objects.create(
            session=session,
            role=MergePlanningMessage.Role.ASSISTANT,
            content="Should refunds be positive or negative?",
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.ai_suggestions_url)

        self.assertContains(response, "Use Date, Description, and signed Amount.")
        self.assertContains(response, "Should refunds be positive or negative?")
        self.assertContains(response, "ai-message--user")
        self.assertContains(response, "ai-message--assistant")

    def test_ai_suggestions_post_saves_user_message_and_placeholder_reply(self) -> None:
        """Posting instructions should append conversation messages."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.post(
            self.ai_suggestions_url,
            {"content": "Create Date, Description, Amount, and Source columns."},
        )

        self.assertRedirects(response, self.ai_suggestions_url)
        session = MergePlanningSession.objects.get()
        self.assertSequenceEqual(
            list(session.messages.values_list("role", flat=True)),
            [
                MergePlanningMessage.Role.USER,
                MergePlanningMessage.Role.ASSISTANT,
            ],
        )
        self.assertEqual(
            session.messages.first().content,
            "Create Date, Description, Amount, and Source columns.",
        )
        self.assertIn(
            "parsed CSV headers and sample rows",
            session.messages.last().content,
        )

    def test_ai_suggestions_post_rejects_blank_message(self) -> None:
        """Blank chat submissions should not create planning messages."""

        self.create_source_file()
        self.client.force_login(self.owner)

        response = self.client.post(self.ai_suggestions_url, {"content": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertTrue(MergePlanningSession.objects.exists())
        self.assertFalse(MergePlanningMessage.objects.exists())

    def test_ai_suggestions_post_is_limited_to_owner(self) -> None:
        """Another user should not append messages to a private mergeset."""

        self.create_source_file()
        self.client.force_login(self.other_user)

        response = self.client.post(
            self.ai_suggestions_url,
            {"content": "Map this file."},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MergePlanningMessage.objects.exists())
