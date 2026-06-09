"""Tests for project ownership behavior."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.forms import ProjectForm
from core.models import Project


User = get_user_model()


class ProjectOwnershipTests(TestCase):
    """Verify projects are tied to user accounts."""

    def test_project_belongs_to_a_specific_owner(self) -> None:
        """Projects should retain the user that owns them."""

        owner = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        project = Project.objects.create(
            owner=owner,
            name="Primary workspace",
            description="Initial test project",
        )

        self.assertEqual(project.owner, owner)
        self.assertEqual(owner.projects.count(), 1)

    def test_project_form_does_not_expose_owner_field(self) -> None:
        """Public project forms should not allow owner selection."""

        form = ProjectForm()

        self.assertNotIn("owner", form.fields)
