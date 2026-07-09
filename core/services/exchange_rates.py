"""Fetch and cache deterministic monthly exchange rates."""

import calendar
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Protocol

from django.db import IntegrityError, transaction

from core.models import ExchangeRate


class ExchangeRateError(RuntimeError):
    """Raised when an exchange rate cannot be resolved."""


class ExchangeRateProvider(Protocol):
    """Provider interface for monthly average exchange rates."""

    name: str

    def fetch_monthly_average_rate(
        self,
        base_currency: str,
        quote_currency: str,
        year: int,
        month: int,
    ) -> Decimal | None:
        """Return a monthly average rate, or None when unavailable."""


@dataclass(frozen=True)
class MonthlyExchangeRate:
    """Resolved monthly exchange-rate value."""

    base_currency: str
    quote_currency: str
    year: int
    month: int
    average_rate: Decimal
    provider: str
    cached: bool


_CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")
_FRANKFURTER_API_BASE_URL = "https://api.frankfurter.dev/v2"


class FrankfurterExchangeRateProvider:
    """Exchange-rate provider backed by Frankfurter's public API."""

    name = "frankfurter"

    def __init__(self, opener=urlopen, timeout: int = 10) -> None:
        """Accept an injectable opener for tests."""

        self.opener = opener
        self.timeout = timeout

    def fetch_monthly_average_rate(
        self,
        base_currency: str,
        quote_currency: str,
        year: int,
        month: int,
    ) -> Decimal | None:
        """Fetch one monthly grouped average rate from Frankfurter."""

        query = urlencode(
            {
                "from": f"{year}-{month:02d}-01",
                "to": f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}",
                "base": base_currency,
                "quotes": quote_currency,
                "group": "month",
            }
        )
        request = Request(
            f"{_FRANKFURTER_API_BASE_URL}/rates?{query}",
            headers={"Accept": "application/json"},
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"), parse_float=Decimal)
        except HTTPError as error:
            if error.code in {400, 404, 422}:
                return None
            raise ExchangeRateError("Frankfurter exchange-rate request failed.") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ExchangeRateError("Frankfurter exchange-rate request failed.") from error

        return _extract_frankfurter_rate(payload, quote_currency)


def get_monthly_average_rate(
    base_currency: str,
    quote_currency: str,
    year: int,
    month: int,
    provider: ExchangeRateProvider | None = None,
) -> MonthlyExchangeRate:
    """Return a cached or provider-fetched monthly average exchange rate."""

    base = _normalize_currency_code(base_currency)
    quote = _normalize_currency_code(quote_currency)
    _validate_year_month(year, month)

    if base == quote:
        return MonthlyExchangeRate(
            base_currency=base,
            quote_currency=quote,
            year=year,
            month=month,
            average_rate=Decimal("1"),
            provider="same_currency",
            cached=True,
        )

    cached_rate = ExchangeRate.objects.filter(
        base_currency=base,
        quote_currency=quote,
        year=year,
        month=month,
    ).first()
    if cached_rate:
        return _rate_from_model(cached_rate, cached=True)

    provider = provider or FrankfurterExchangeRateProvider()

    fetched_rate = provider.fetch_monthly_average_rate(base, quote, year, month)
    if fetched_rate is None:
        raise ExchangeRateError(
            f"{provider.name} has no exchange rate for {base}/{quote} {year}-{month:02d}."
        )

    average_rate = _normalize_rate(fetched_rate)
    try:
        with transaction.atomic():
            rate = ExchangeRate.objects.create(
                base_currency=base,
                quote_currency=quote,
                year=year,
                month=month,
                average_rate=average_rate,
                provider=provider.name,
            )
    except IntegrityError:
        rate = ExchangeRate.objects.get(
            base_currency=base,
            quote_currency=quote,
            year=year,
            month=month,
        )
        return _rate_from_model(rate, cached=True)

    return _rate_from_model(rate, cached=False)


def _normalize_currency_code(currency_code: str) -> str:
    """Return an uppercase ISO-style currency code."""

    normalized = currency_code.strip().upper()
    if not _CURRENCY_CODE_PATTERN.fullmatch(normalized):
        raise ExchangeRateError(f"Invalid currency code: {currency_code}.")
    return normalized


def _validate_year_month(year: int, month: int) -> None:
    """Validate the requested rate month."""

    if year < 1900:
        raise ExchangeRateError("Exchange-rate year must be 1900 or later.")
    if month < 1 or month > 12:
        raise ExchangeRateError("Exchange-rate month must be between 1 and 12.")


def _normalize_rate(rate: Decimal) -> Decimal:
    """Validate and normalize a provider rate."""

    try:
        normalized = Decimal(rate)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ExchangeRateError("Exchange-rate provider returned an invalid rate.") from error
    if normalized <= 0:
        raise ExchangeRateError("Exchange-rate provider returned a non-positive rate.")
    return normalized


def _extract_frankfurter_rate(payload: dict, quote_currency: str) -> Decimal | None:
    """Return the quoted rate from a Frankfurter time-series response."""

    rates = payload.get("rates")
    if not isinstance(rates, dict):
        return None
    if quote_currency in rates:
        return rates[quote_currency]

    for month_rates in rates.values():
        if isinstance(month_rates, dict) and quote_currency in month_rates:
            return month_rates[quote_currency]
    return None


def _rate_from_model(rate: ExchangeRate, cached: bool) -> MonthlyExchangeRate:
    """Build a service result from a stored rate."""

    return MonthlyExchangeRate(
        base_currency=rate.base_currency,
        quote_currency=rate.quote_currency,
        year=rate.year,
        month=rate.month,
        average_rate=rate.average_rate,
        provider=rate.provider,
        cached=cached,
    )
