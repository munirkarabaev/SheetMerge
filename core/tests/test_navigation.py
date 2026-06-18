"""Tests for primary navigation state."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Mergeset, MergesetFile


User = get_user_model()


class PrimaryNavigationTests(TestCase):
    """Verify the current section is highlighted in the navbar."""

    def setUp(self) -> None:
        """Create an authenticated workspace for protected pages."""

        self.user = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.mergeset = Mergeset.objects.create(
            owner=self.user,
            name="Navigation test",
            description="",
        )
        MergesetFile.objects.create(
            mergeset=self.mergeset,
            file="mergesets/test/sources/navigation.csv",
            original_name="navigation.csv",
            file_size=100,
            parse_status=MergesetFile.ParseStatus.PARSED,
            headers=["date", "amount"],
            delimiter=",",
            row_count=1,
        )

    def assert_active_link(self, response, label: str) -> None:
        """Assert that one navigation link is marked as the current page."""

        self.assertContains(
            response,
            f'topnav__link topnav__link--active"',
            count=1,
        )
        self.assertContains(response, 'aria-current="page"', count=1)
        active_link = (
            'class="topnav__link topnav__link--active"'
        )
        content = response.content.decode()
        active_start = content.index(active_link)
        active_end = content.index("</a>", active_start)
        self.assertIn(f">{label}</a>", content[active_start:active_end + 4])

    def test_home_tab_is_active_on_public_home(self) -> None:
        """The public landing page should select Home."""

        response = self.client.get(reverse("core:home"))

        self.assert_active_link(response, "Home")

    def test_home_tab_is_active_on_dashboard(self) -> None:
        """The authenticated landing page should select Home."""

        self.client.force_login(self.user)

        response = self.client.get(reverse("users:dashboard"))

        self.assert_active_link(response, "Home")

    def test_mergesets_tab_is_active_across_mergeset_pages(self) -> None:
        """List, create, and detail pages should select Mergesets."""

        self.client.force_login(self.user)
        urls = [
            reverse("core:mergeset_list"),
            reverse("core:mergeset_create"),
            reverse("core:mergeset_detail", kwargs={"pk": self.mergeset.pk}),
            reverse("core:mergeset_ai_suggestions", kwargs={"pk": self.mergeset.pk}),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assert_active_link(response, "Mergesets")

    def test_billing_tab_is_active(self) -> None:
        """The billing page should select Billing."""

        self.client.force_login(self.user)

        response = self.client.get(reverse("core:billing"))

        self.assert_active_link(response, "Billing")

    def test_support_tab_is_active(self) -> None:
        """The support page should select Support."""

        self.client.force_login(self.user)

        response = self.client.get(reverse("core:support"))

        self.assert_active_link(response, "Support")
