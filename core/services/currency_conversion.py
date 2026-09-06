"""Deterministic currency conversion with export provenance."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from core.models import MergesetFile
from core.services.exchange_rates import (
    ExchangeRateError,
    ExchangeRateProvider,
    get_monthly_average_rate,
)
from core.services.preview_validation import parse_date, parse_decimal_amount


@dataclass(frozen=True)
class CurrencyConversionResult:
    """One converted amount and the data needed to audit it."""

    value: str
    warning: str | None = None
    blocking_error: str | None = None
    provenance: dict[str, str] | None = None


def convert_currency(
    original_amount: str,
    source_row: dict[str, str],
    file_mapping: dict,
    plan_json: dict,
    source_file: MergesetFile,
    target_column: str,
    amount_format: dict | None,
    rate_provider: ExchangeRateProvider | None,
) -> CurrencyConversionResult:
    """Convert one amount or return a blank value with an actionable exception."""

    amount = parse_decimal_amount(original_amount, amount_format)
    if amount is None:
        return _failure(source_file.original_name, "the amount could not be parsed.", "a valid amount")

    source_currency = (file_mapping.get("detected_currency", {}).get("currency") or "").strip()
    target_currency = (
        plan_json.get("currency_conversion", {}).get("target_currency")
        or plan_json.get("output_currency")
        or ""
    ).strip()
    if not source_currency or not target_currency:
        return _failure(
            source_file.original_name,
            "source or target currency is missing.",
            "source and target currencies",
        )

    row_date = _find_row_date(source_row, file_mapping)
    if row_date is None:
        return _failure(
            source_file.original_name,
            "no recognized row date was available for a monthly exchange rate.",
            "a recognized row date",
        )

    try:
        rate = get_monthly_average_rate(
            source_currency,
            target_currency,
            row_date.year,
            row_date.month,
            provider=rate_provider,
        )
    except ExchangeRateError as error:
        return _failure(
            source_file.original_name,
            f"exchange rate lookup failed: {error}",
            "an exchange rate",
        )

    converted_amount = _format_money(amount * rate.average_rate)
    return CurrencyConversionResult(
        value=converted_amount,
        provenance={
            "target_column": target_column,
            "original_amount": format(amount, "f"),
            "original_currency": rate.base_currency,
            "reporting_amount": converted_amount,
            "reporting_currency": rate.quote_currency,
            "exchange_rate": format(rate.average_rate, "f"),
            "rate_provider": rate.provider,
            "rate_period": f"{rate.year}-{rate.month:02d}",
            "rate_policy": "monthly_average",
            "rounding_policy": "half_up_2_decimal_places",
        },
    )


def _failure(source_name: str, reason: str, requirement: str) -> CurrencyConversionResult:
    """Return a blank converted value with reviewable failure details."""

    return CurrencyConversionResult(
        value="",
        warning=f"{source_name}: currency conversion failed because {reason}",
        blocking_error=f"{source_name}: currency conversion needs {requirement}.",
    )


def _find_row_date(source_row: dict[str, str], file_mapping: dict):
    """Find the first parseable date from the file's declared date mapping."""

    for mapping in file_mapping.get("mappings", []):
        if mapping.get("transform") != "parse_date":
            continue
        for column in mapping.get("source_columns", []):
            parsed_date = parse_date(source_row.get(column, ""))
            if parsed_date is not None:
                return parsed_date
    return None


def _format_money(amount: Decimal) -> str:
    """Round a converted amount using the stated export policy."""

    return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
