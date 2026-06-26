"""Tests for authenticated mergeset views."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Mergeset


User = get_user_model()


class MergesetViewTests(TestCase):
    """Verify list, create, and detail mergeset flows."""

    def setUp(self) -> None:
        """Create baseline users for access-control tests."""

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="test-pass-123",
        )

    def test_mergeset_list_requires_authentication(self) -> None:
        """Anonymous users should be redirected away from the mergeset list."""

        response = self.client.get(reverse("core:mergeset_list"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:mergeset_list')}",
        )

    def test_mergeset_list_only_shows_current_users_mergesets(self) -> None:
        """Users should only see mergesets they own."""

        Mergeset.objects.create(owner=self.owner, name="Owner mergeset", description="")
        Mergeset.objects.create(owner=self.other_user, name="Other mergeset", description="")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("core:mergeset_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owner mergeset")
        self.assertNotContains(response, "Other mergeset")

    def test_mergeset_create_assigns_owner_to_request_user(self) -> None:
        """Created mergesets should automatically belong to the signed-in user."""

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("core:mergeset_create"),
            {
                "name": "Created from form",
                "description": "Testing owner assignment",
            },
        )

        mergeset = Mergeset.objects.get(name="Created from form")
        self.assertRedirects(response, reverse("core:mergeset_detail", kwargs={"pk": mergeset.pk}))
        self.assertEqual(mergeset.owner, self.owner)
        self.assertEqual(mergeset.description, "Testing owner assignment")

    def test_mergeset_create_page_labels_description_as_context(self) -> None:
        """The setup form should explain that context feeds AI planning."""

        self.client.force_login(self.owner)

        response = self.client.get(reverse("core:mergeset_create"))

        self.assertContains(response, "Configure merge job")
        self.assertContains(response, "Context")
        self.assertContains(response, "sent to the AI")
        self.assertNotContains(response, ">Description</label>")

    def test_mergeset_detail_is_limited_to_owner(self) -> None:
        """Non-owners should not be able to open another user's mergeset."""

        mergeset = Mergeset.objects.create(
            owner=self.owner,
            name="Private mergeset",
            description="Hidden from other users",
        )
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("core:mergeset_detail", kwargs={"pk": mergeset.pk}))

        self.assertEqual(response.status_code, 404)

    def test_billing_page_requires_authentication(self) -> None:
        """Anonymous users should be redirected away from billing."""

        response = self.client.get(reverse("core:billing"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:billing')}",
        )

    def test_support_page_requires_authentication(self) -> None:
        """Anonymous users should be redirected away from support."""

        response = self.client.get(reverse("core:support"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:support')}",
        )
