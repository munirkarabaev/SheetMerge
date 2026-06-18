"""Tests for AI-assisted merge plan revisions."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import MergePlan, MergePlanningMessage, MergePlanningSession, Mergeset
from core.services import run_merge_plan_revision


User = get_user_model()


class FakeOpenAIResponse:
    """Small stand-in for an OpenAI Responses API object."""

    def __init__(self, output_text: str) -> None:
        """Store response text for service tests."""

        self.output_text = output_text


class FakeResponses:
    """Capture response creation arguments and return fixed text."""

    def __init__(self, output_text: str) -> None:
        """Store a fake output payload."""

        self.output_text = output_text
        self.create_kwargs = None

    def create(self, **kwargs):
        """Capture create kwargs and return a fake OpenAI response."""

        self.create_kwargs = kwargs
        return FakeOpenAIResponse(self.output_text)


class FakeOpenAIClient:
    """Fake OpenAI client exposing a responses resource."""

    def __init__(self, output_text: str) -> None:
        """Create a fake responses resource."""

        self.responses = FakeResponses(output_text)


class MergePlanRevisionServiceTests(TestCase):
    """Verify AI revision persistence and request shape."""

    def setUp(self) -> None:
        """Create a user-owned merge plan."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Monthly statements",
            description="",
        )
        self.session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        self.merge_plan = MergePlan.objects.create(
            mergeset=self.mergeset,
            session=self.session,
            status=MergePlan.Status.NEEDS_REVIEW,
            plan_json={
                "status": "mapping_ready",
                "assistant_message": "Ready for review.",
                "questions": [],
                "final_columns": [{"name": "Date", "type": "date"}],
                "file_mappings": [],
                "result_operations": [],
            },
        )

    def test_revision_creates_new_merge_plan_and_messages(self) -> None:
        """A revision should save the request, response, and new plan."""

        client = FakeOpenAIClient(
            (
                '{"status":"mapping_ready","assistant_message":"Sorted by Date.",'
                '"questions":[],"final_columns":[{"name":"Date","type":"date"}],'
                '"file_mappings":[],"result_operations":[{"type":"sort",'
                '"column":"Date","direction":"ascending"}]}'
            )
        )

        result = run_merge_plan_revision(
            self.merge_plan,
            "Sort it in chronological order.",
            client=client,
        )

        self.assertEqual(MergePlan.objects.count(), 2)
        self.assertEqual(result.merge_plan.ai_summary, "Sorted by Date.")
        self.assertEqual(
            result.merge_plan.plan_json["result_operations"],
            [{"type": "sort", "column": "Date", "direction": "ascending"}],
        )
        self.assertSequenceEqual(
            list(self.session.messages.values_list("role", flat=True)),
            [MergePlanningMessage.Role.USER, MergePlanningMessage.Role.ASSISTANT],
        )

    def test_revision_request_includes_instruction_and_current_plan(self) -> None:
        """The revision request should include enough context for OpenAI."""

        client = FakeOpenAIClient(
            (
                '{"status":"mapping_ready","assistant_message":"No changes needed.",'
                '"questions":[],"final_columns":[{"name":"Date","type":"date"}],'
                '"file_mappings":[],"result_operations":[]}'
            )
        )

        run_merge_plan_revision(self.merge_plan, "Keep this mapping.", client=client)

        request_content = client.responses.create_kwargs["input"][1]["content"]
        self.assertIn("Keep this mapping.", request_content)
        self.assertIn("current_plan", request_content)
        self.assertIn("result_operations", request_content)
