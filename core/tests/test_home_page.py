"""Tests for the home page."""

from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    """Verify the initial landing page is wired correctly."""

    def test_home_page_returns_success(self) -> None:
        """The root URL should return an HTTP 200 response."""

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)

    def test_home_page_uses_expected_template(self) -> None:
        """The home page should render the expected templates."""

        response = self.client.get(reverse("core:home"))

        self.assertTemplateUsed(response, "core/home.html")
        self.assertTemplateUsed(response, "core/base.html")

    def test_home_page_contains_navigation_content(self) -> None:
        """The rendered page should include the primary navigation labels."""

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "SheetMerge")
        self.assertContains(response, "Home")
        self.assertContains(response, "Mergesets")
        self.assertContains(response, "Billing")
        self.assertContains(response, "Support")
