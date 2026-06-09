"""Tests for mergeset ownership behavior."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.forms import MergesetForm
from core.models import Mergeset


User = get_user_model()


class MergesetOwnershipTests(TestCase):
    """Verify mergesets are tied to user accounts."""

    def test_mergeset_belongs_to_a_specific_owner(self) -> None:
        """Mergesets should retain the user that owns them."""

        owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        mergeset = Mergeset.objects.create(
            owner=owner,
            name="Primary mergeset",
            description="Initial test mergeset",
        )

        self.assertEqual(mergeset.owner, owner)
        self.assertEqual(owner.mergesets.count(), 1)

    def test_mergeset_form_does_not_expose_owner_field(self) -> None:
        """Public mergeset forms should not allow owner selection."""

        form = MergesetForm()

        self.assertNotIn("owner", form.fields)
