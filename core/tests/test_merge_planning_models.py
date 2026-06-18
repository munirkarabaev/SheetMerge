"""Tests for AI-assisted merge planning models."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    MergePlan,
    MergePlanningMessage,
    MergePlanningSession,
    Mergeset,
)


User = get_user_model()


class MergePlanningModelTests(TestCase):
    """Verify planning sessions, messages, and generated plans."""

    def setUp(self) -> None:
        """Create a user-owned mergeset for planning tests."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Monthly statements",
            description="",
        )

    def test_planning_session_defaults_to_collecting_requirements(self) -> None:
        """New sessions should start before a mapping plan is ready."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)

        self.assertEqual(
            session.status,
            MergePlanningSession.Status.COLLECTING_REQUIREMENTS,
        )
        self.assertEqual(self.mergeset.planning_sessions.count(), 1)
        self.assertIn("Monthly statements", str(session))

    def test_planning_messages_keep_conversation_order(self) -> None:
        """Messages should read back in chronological order."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        user_message = MergePlanningMessage.objects.create(
            session=session,
            role=MergePlanningMessage.Role.USER,
            content="Use Date, Description, and Amount.",
        )
        assistant_message = MergePlanningMessage.objects.create(
            session=session,
            role=MergePlanningMessage.Role.ASSISTANT,
            content="Should Amount be signed?",
        )

        self.assertSequenceEqual(
            list(session.messages.all()),
            [user_message, assistant_message],
        )
        self.assertEqual(str(user_message), "User message")

    def test_merge_plan_stores_structured_plan_for_review(self) -> None:
        """Generated plans should retain flexible mapping JSON and summary text."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        plan = MergePlan.objects.create(
            mergeset=self.mergeset,
            session=session,
            status=MergePlan.Status.NEEDS_REVIEW,
            plan_json={
                "final_columns": [{"name": "Date", "type": "date"}],
                "file_mappings": [],
            },
            ai_summary="Mapped transaction dates into Date.",
        )

        self.assertEqual(plan.status, MergePlan.Status.NEEDS_REVIEW)
        self.assertEqual(plan.plan_json["final_columns"][0]["name"], "Date")
        self.assertEqual(session.merge_plans.get(), plan)
        self.assertEqual(self.mergeset.merge_plans.get(), plan)
        self.assertIn("Monthly statements", str(plan))

    def test_deleting_mergeset_cascades_planning_records(self) -> None:
        """Planning records should not survive their owning mergeset."""

        session = MergePlanningSession.objects.create(mergeset=self.mergeset)
        MergePlanningMessage.objects.create(
            session=session,
            role=MergePlanningMessage.Role.USER,
            content="Create a clean spreadsheet.",
        )
        MergePlan.objects.create(mergeset=self.mergeset, session=session)

        self.mergeset.delete()

        self.assertFalse(MergePlanningSession.objects.exists())
        self.assertFalse(MergePlanningMessage.objects.exists())
        self.assertFalse(MergePlan.objects.exists())
