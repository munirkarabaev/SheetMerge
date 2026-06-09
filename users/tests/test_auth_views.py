"""Tests for authentication and authenticated pages."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AuthenticationViewTests(TestCase):
    """Verify the login and signup pages plus dashboard access rules."""

    def test_login_page_renders_credentials_and_google_cta(self) -> None:
        """The login page should render the default auth path safely."""

        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")
        self.assertContains(response, "Google sign-in is available once OAuth is configured.")

    def test_signup_page_renders_email_signup_and_google_cta(self) -> None:
        """The signup page should render the default signup path safely."""

        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your account")
        self.assertContains(response, "Google sign-up is available once OAuth is configured.")

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

    def test_signup_post_creates_user(self) -> None:
        """Submitting the signup form should create a new user."""

        response = self.client.post(
            reverse("account_signup"),
            {
                "email": "new-user@example.com",
                "password1": "test-pass-123",
                "password2": "test-pass-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="new-user@example.com").exists())
        self.assertLessEqual(len(mail.outbox), 1)


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
