"""Tests for AI planning context construction."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    MergePlan,
    MergePlanningMessage,
    MergePlanningSession,
    Mergeset,
    MergesetFile,
)
from core.services import (
    OpenAIPlanningError,
    build_merge_planning_context,
    request_merge_planning_response,
    run_merge_planning_turn,
)


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


class MergePlanningContextTests(TestCase):
    """Verify the payload prepared for the OpenAI integration."""

    def setUp(self) -> None:
        """Create a user-owned mergeset and planning session."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Monthly statements",
            description="January bank and card exports.",
        )
        self.session = MergePlanningSession.objects.create(mergeset=self.mergeset)

    def test_context_includes_parsed_source_files(self) -> None:
        """Parsed source files should include headers, rows, and metadata."""

        source_file = MergesetFile.objects.create(
            mergeset=self.mergeset,
            file="mergesets/test/sources/bank.csv",
            original_name="bank.csv",
            file_size=100,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["Date", "Description", "Debit", "Credit"],
            sample_rows=[
                ["2026-01-01", "Cafe", "4.50", ""],
                ["2026-01-02", "Salary", "", "2200.00"],
            ],
            delimiter=",",
            row_count=2,
        )

        context = build_merge_planning_context(self.session)

        self.assertIn("CSV column mapping planner", context.system_prompt)
        self.assertEqual(
            context.payload["mergeset"],
            {
                "id": self.mergeset.id,
                "name": "Monthly statements",
                "description": "January bank and card exports.",
            },
        )
        self.assertEqual(
            context.payload["source_files"],
            [
                {
                    "id": source_file.id,
                    "filename": "bank.csv",
                    "headers": ["Date", "Description", "Debit", "Credit"],
                    "delimiter": ",",
                    "row_count": 2,
                    "sample_rows": [
                        ["2026-01-01", "Cafe", "4.50", ""],
                        ["2026-01-02", "Salary", "", "2200.00"],
                    ],
                }
            ],
        )

    def test_context_excludes_unparsed_source_files(self) -> None:
        """Only parsed files should be sent to the AI planning layer."""

        MergesetFile.objects.create(
            mergeset=self.mergeset,
            file="mergesets/test/sources/broken.csv",
            original_name="broken.csv",
            file_size=50,
            parse_status=MergesetFile.ParseStatus.FAILED,
            parse_error="Invalid row.",
        )

        context = build_merge_planning_context(self.session)

        self.assertEqual(context.payload["source_files"], [])

    def test_context_preserves_conversation_order(self) -> None:
        """Conversation messages should be sent in chronological order."""

        MergePlanningMessage.objects.create(
            session=self.session,
            role=MergePlanningMessage.Role.USER,
            content="Use Date, Description, and Amount.",
        )
        MergePlanningMessage.objects.create(
            session=self.session,
            role=MergePlanningMessage.Role.ASSISTANT,
            content="Should Amount be signed?",
        )

        context = build_merge_planning_context(self.session)

        self.assertEqual(
            context.payload["conversation"],
            [
                {
                    "role": MergePlanningMessage.Role.USER,
                    "content": "Use Date, Description, and Amount.",
                },
                {
                    "role": MergePlanningMessage.Role.ASSISTANT,
                    "content": "Should Amount be signed?",
                },
            ],
        )

    def test_context_describes_response_contract(self) -> None:
        """The payload should describe expected planning response shapes."""

        context = build_merge_planning_context(self.session)
        response_contract = context.payload["response_contract"]

        self.assertEqual(
            response_contract["statuses"],
            ["needs_clarification", "mapping_ready"],
        )
        self.assertIn(
            "questions",
            response_contract["needs_clarification"]["required_fields"],
        )
        self.assertIn(
            "file_mappings",
            response_contract["mapping_ready"]["required_fields"],
        )
        self.assertIn(
            "debit_credit_to_signed_amount",
            response_contract["supported_transforms"],
        )

    def test_context_tells_ai_to_accept_user_confirmation(self) -> None:
        """Prompt rules should prevent repeated confirmation loops."""

        context = build_merge_planning_context(self.session)

        self.assertIn("If the user confirms", context.system_prompt)
        self.assertIn("return mapping_ready", context.system_prompt)
        self.assertIn("Do not repeat a question", context.system_prompt)
        self.assertIn(
            "Treat confirmations",
            context.payload["response_contract"]["workflow_rules"][2],
        )

    def test_context_requires_specific_natural_clarifications(self) -> None:
        """Prompt rules should avoid vague or robotic assistant replies."""

        context = build_merge_planning_context(self.session)
        workflow_rules = context.payload["response_contract"]["workflow_rules"]

        self.assertIn("natural, helpful tone", context.system_prompt)
        self.assertIn("exact decision", context.system_prompt)
        self.assertIn("why it matters", context.system_prompt)
        self.assertIn("generic confirmation", context.system_prompt)
        self.assertIn("exact choice needed", workflow_rules[4])
        self.assertIn("natural and specific", workflow_rules[5])

    def test_context_requires_column_options_and_mapping_ready_guidance(self) -> None:
        """Prompt rules should make the next user action clear."""

        context = build_merge_planning_context(self.session)
        workflow_rules = context.payload["response_contract"]["workflow_rules"]

        self.assertIn("which source columns", context.system_prompt)
        self.assertIn("proceed to column mapping", context.system_prompt)
        self.assertIn("source columns or mapping options", workflow_rules[6])
        self.assertIn("proceed to column mapping", workflow_rules[7])

    def test_context_tells_ai_to_preserve_requested_wide_outputs(self) -> None:
        """Prompt rules should prevent collapsing wide files to defaults."""

        context = build_merge_planning_context(self.session)
        workflow_rules = context.payload["response_contract"]["workflow_rules"]

        self.assertIn("Preserve every final output column", context.system_prompt)
        self.assertIn("all available source headers", context.system_prompt)
        self.assertIn("Do not collapse a wide spreadsheet", context.system_prompt)
        self.assertIn("Preserve every final column", workflow_rules[8])
        self.assertIn("include all uploaded source headers", workflow_rules[9])
        self.assertIn("Date, Description, Amount", workflow_rules[10])

    def test_openai_request_uses_structured_output_schema(self) -> None:
        """The OpenAI request should ask for strict structured JSON."""

        client = FakeOpenAIClient(
            (
                '{"status":"needs_clarification","assistant_message":"Which '
                'columns do you want?","questions":["Which columns do you want?"],'
                '"final_columns":[],"file_mappings":[],"result_operations":[]}'
            )
        )

        payload = request_merge_planning_response(self.session, client=client)

        self.assertEqual(payload["status"], "needs_clarification")
        create_kwargs = client.responses.create_kwargs
        self.assertEqual(create_kwargs["model"], "gpt-5.5")
        self.assertEqual(create_kwargs["input"][0]["role"], "system")
        self.assertEqual(create_kwargs["input"][1]["role"], "user")
        self.assertEqual(
            create_kwargs["text"]["format"]["name"],
            "merge_planning_response",
        )
        self.assertTrue(create_kwargs["text"]["format"]["strict"])

    def test_planning_turn_saves_clarification_message(self) -> None:
        """Clarification responses should append an assistant message."""

        client = FakeOpenAIClient(
            (
                '{"status":"needs_clarification","assistant_message":"Should '
                'refunds be positive?","questions":["Should refunds be positive?"],'
                '"final_columns":[],"file_mappings":[],"result_operations":[]}'
            )
        )

        result = run_merge_planning_turn(self.session, client=client)

        self.assertIsNone(result.merge_plan)
        self.assertEqual(
            result.assistant_message.content,
            "Should refunds be positive?",
        )
        self.assertEqual(self.session.messages.count(), 1)
        self.session.refresh_from_db()
        self.assertEqual(
            self.session.status,
            MergePlanningSession.Status.COLLECTING_REQUIREMENTS,
        )

    def test_planning_turn_creates_merge_plan_when_mapping_ready(self) -> None:
        """Mapping-ready responses should create a reviewable merge plan."""

        client = FakeOpenAIClient(
            (
                '{"status":"mapping_ready","assistant_message":"I drafted the '
                'mapping.","questions":[],"final_columns":[{"name":"Date",'
                '"type":"date"}],"file_mappings":[{"file_id":1,"filename":'
                '"bank.csv","mappings":[{"target_column":"Date","source_columns":'
                '["Transaction Date"],"transform":"parse_date","notes":""}],'
                '"ignored_columns":["Balance"]}],"result_operations":[]}'
            )
        )

        result = run_merge_planning_turn(self.session, client=client)

        self.assertIsNotNone(result.merge_plan)
        self.assertEqual(MergePlan.objects.count(), 1)
        self.assertEqual(result.merge_plan.status, MergePlan.Status.NEEDS_REVIEW)
        self.assertEqual(result.merge_plan.ai_summary, "I drafted the mapping.")
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, MergePlanningSession.Status.MAPPING_READY)

    def test_openai_request_requires_api_key_without_injected_client(self) -> None:
        """The service should fail clearly when the API key is missing."""

        with self.settings():
            import os

            original_key = os.environ.pop("OPENAI_API_KEY", None)
            try:
                with self.assertRaisesMessage(
                    OpenAIPlanningError,
                    "OPENAI_API_KEY is not configured.",
                ):
                    request_merge_planning_response(self.session)
            finally:
                if original_key is not None:
                    os.environ["OPENAI_API_KEY"] = original_key
