"""Tests for exchange-rate lookup and caching."""

from decimal import Decimal
from urllib.error import HTTPError

from django.test import TestCase

from core.models import ExchangeRate
from core.services import (
    ExchangeRateError,
    FrankfurterExchangeRateProvider,
    get_monthly_average_rate,
)


class FakeExchangeRateProvider:
    """Small exchange-rate provider for deterministic service tests."""

    name = "fake_rates"

    def __init__(self, rate: Decimal | None) -> None:
        """Store the rate returned by the fake provider."""

        self.rate = rate
        self.calls = []

    def fetch_monthly_average_rate(
        self,
        base_currency: str,
        quote_currency: str,
        year: int,
        month: int,
    ) -> Decimal | None:
        """Capture the request and return the configured rate."""

        self.calls.append((base_currency, quote_currency, year, month))
        return self.rate


class FakeHTTPResponse:
    """Context-manager response for fake HTTP calls."""

    def __init__(self, body: str) -> None:
        """Store the response body."""

        self.body = body

    def __enter__(self):
        """Return the response for context-manager usage."""

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """No cleanup is needed for fake responses."""

    def read(self) -> bytes:
        """Return the encoded response body."""

        return self.body.encode("utf-8")


class FakeHTTPOpener:
    """Capture Frankfurter requests and return a configured response."""

    def __init__(self, body: str | None = None, error: HTTPError | None = None) -> None:
        """Store the response or error."""

        self.body = body
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        """Capture the request and return a fake response."""

        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return FakeHTTPResponse(self.body or "{}")


class ExchangeRateServiceTests(TestCase):
    """Verify monthly exchange-rate resolution."""

    def test_returns_cached_rate_without_provider_call(self) -> None:
        """Existing rates should be used before provider fetches."""

        ExchangeRate.objects.create(
            base_currency="USD",
            quote_currency="GBP",
            year=2026,
            month=4,
            average_rate=Decimal("0.79000000"),
            provider="cached_provider",
        )
        provider = FakeExchangeRateProvider(Decimal("0.80000000"))

        result = get_monthly_average_rate("usd", "gbp", 2026, 4, provider=provider)

        self.assertEqual(result.average_rate, Decimal("0.79000000"))
        self.assertEqual(result.provider, "cached_provider")
        self.assertTrue(result.cached)
        self.assertEqual(provider.calls, [])

    def test_fetches_and_stores_missing_rate(self) -> None:
        """Missing rates should be fetched once and stored for reuse."""

        provider = FakeExchangeRateProvider(Decimal("0.81234567"))

        result = get_monthly_average_rate("EUR", "GBP", 2026, 5, provider=provider)

        self.assertEqual(result.average_rate, Decimal("0.81234567"))
        self.assertEqual(result.provider, "fake_rates")
        self.assertFalse(result.cached)
        self.assertEqual(provider.calls, [("EUR", "GBP", 2026, 5)])
        stored_rate = ExchangeRate.objects.get()
        self.assertEqual(stored_rate.base_currency, "EUR")
        self.assertEqual(stored_rate.quote_currency, "GBP")

    def test_default_provider_fetches_from_frankfurter(self) -> None:
        """Frankfurter should be usable as the real default provider."""

        opener = FakeHTTPOpener(
            '[{"date":"2026-05-01","base":"EUR","quote":"GBP","rate":0.81234567}]'
        )
        provider = FrankfurterExchangeRateProvider(opener=opener, timeout=3)

        result = get_monthly_average_rate("EUR", "GBP", 2026, 5, provider=provider)

        self.assertEqual(result.average_rate, Decimal("0.81234567"))
        self.assertEqual(result.provider, "frankfurter")
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 3)
        self.assertIn("base=EUR", request.full_url)
        self.assertIn("quotes=GBP", request.full_url)
        self.assertIn("group=month", request.full_url)
        self.assertEqual(request.headers["User-agent"], "SheetMerge/0.1")

    def test_same_currency_returns_one_without_storage(self) -> None:
        """No provider or database row is needed for same-currency conversion."""

        result = get_monthly_average_rate("GBP", "gbp", 2026, 6)

        self.assertEqual(result.average_rate, Decimal("1"))
        self.assertEqual(result.provider, "same_currency")
        self.assertTrue(result.cached)
        self.assertFalse(ExchangeRate.objects.exists())

    def test_requires_valid_currency_codes(self) -> None:
        """Currency codes should be three-letter ISO-style values."""

        with self.assertRaisesMessage(ExchangeRateError, "Invalid currency code"):
            get_monthly_average_rate("US", "GBP", 2026, 1)

    def test_requires_valid_month(self) -> None:
        """Invalid months should fail before provider calls."""

        provider = FakeExchangeRateProvider(Decimal("1.2"))

        with self.assertRaisesMessage(ExchangeRateError, "month must be between 1 and 12"):
            get_monthly_average_rate("USD", "GBP", 2026, 13, provider=provider)

        self.assertEqual(provider.calls, [])

    def test_raises_when_provider_has_no_rate(self) -> None:
        """Unavailable provider data should fail clearly and not create cache rows."""

        provider = FakeExchangeRateProvider(None)

        with self.assertRaisesMessage(ExchangeRateError, "has no exchange rate"):
            get_monthly_average_rate("USD", "GBP", 2026, 7, provider=provider)

        self.assertFalse(ExchangeRate.objects.exists())

    def test_frankfurter_returns_none_for_not_found_response(self) -> None:
        """Frankfurter 404-style responses should become unavailable rates."""

        error = HTTPError(
            url="https://api.frankfurter.dev/v2/rates",
            code=404,
            msg="Not found",
            hdrs=None,
            fp=None,
        )
        provider = FrankfurterExchangeRateProvider(opener=FakeHTTPOpener(error=error))

        with self.assertRaisesMessage(ExchangeRateError, "has no exchange rate"):
            get_monthly_average_rate("USD", "GBP", 2026, 7, provider=provider)

    def test_frankfurter_rejects_malformed_response(self) -> None:
        """Malformed provider responses should fail clearly."""

        provider = FrankfurterExchangeRateProvider(opener=FakeHTTPOpener("not-json"))

        with self.assertRaisesMessage(ExchangeRateError, "Frankfurter exchange-rate request failed"):
            get_monthly_average_rate("USD", "GBP", 2026, 7, provider=provider)

    def test_rejects_non_positive_provider_rate(self) -> None:
        """Provider rates must be positive."""

        provider = FakeExchangeRateProvider(Decimal("0"))

        with self.assertRaisesMessage(ExchangeRateError, "non-positive rate"):
            get_monthly_average_rate("USD", "GBP", 2026, 7, provider=provider)

        self.assertFalse(ExchangeRate.objects.exists())
