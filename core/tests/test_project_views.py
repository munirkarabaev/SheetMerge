"""Tests for authenticated project views."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Project


User = get_user_model()


class ProjectViewTests(TestCase):
    """Verify list, create, and detail project flows."""

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

    def test_project_list_requires_authentication(self) -> None:
        """Anonymous users should be redirected away from the project list."""

        response = self.client.get(reverse("core:project_list"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:project_list')}",
        )

    def test_project_list_only_shows_current_users_projects(self) -> None:
        """Users should only see projects they own."""

        Project.objects.create(owner=self.owner, name="Owner project", description="")
        Project.objects.create(owner=self.other_user, name="Other project", description="")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("core:project_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owner project")
        self.assertNotContains(response, "Other project")

    def test_project_create_assigns_owner_to_request_user(self) -> None:
        """Created projects should automatically belong to the signed-in user."""

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("core:project_create"),
            {
                "name": "Created from form",
                "description": "Testing owner assignment",
            },
        )

        project = Project.objects.get(name="Created from form")
        self.assertRedirects(response, reverse("core:project_detail", kwargs={"pk": project.pk}))
        self.assertEqual(project.owner, self.owner)

    def test_project_detail_is_limited_to_owner(self) -> None:
        """Non-owners should not be able to open another user's project."""

        project = Project.objects.create(
            owner=self.owner,
            name="Private workspace",
            description="Hidden from other users",
        )
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("core:project_detail", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, 404)
