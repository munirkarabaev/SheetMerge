"""Tests for authentication and authenticated pages."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AuthenticationViewTests(TestCase):
    """Verify the login and signup pages plus dashboard access rules."""

    def test_login_page_renders_credentials_and_google_cta(self) -> None:
        """The login page should render both login methods."""

        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, "Log in")

    def test_signup_page_renders_email_signup_and_google_cta(self) -> None:
        """The signup page should render both signup methods."""

        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create account")
        self.assertContains(response, "Sign up with Google")

    def test_dashboard_requires_authentication(self) -> None:
        """Anonymous users should be redirected to the login page."""

        response = self.client.get(reverse("users:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('users:dashboard')}",
        )

    def test_authenticated_user_can_open_dashboard(self) -> None:
        """Signed-in users should reach the dashboard."""

        user = User.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("users:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")


class HomePageRedirectTests(TestCase):
    """Verify authenticated users are routed into the app."""

    def test_authenticated_user_is_redirected_from_marketing_home(self) -> None:
        """Signed-in users should land on the dashboard instead of the public home page."""

        user = User.objects.create_user(
            email="redirect@example.com",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("users:dashboard"))
