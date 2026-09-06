"""Validate deterministic merge-preview values before export."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


DEFAULT_AMOUNT_FORMAT = {"decimal_separator": ".", "thousands_separator": ","}


def clean_amount(value: str) -> str:
    """Remove supported currency symbols and accounting parentheses."""

    cleaned_value = (
        value.strip()
        .replace("£", "")
        .replace("$", "")
        .replace("€", "")
    )
    if cleaned_value.startswith("(") and cleaned_value.endswith(")"):
        return f"-{cleaned_value[1:-1]}"
    return cleaned_value


def parse_decimal_amount(
    value: str,
    amount_format: dict | None = None,
) -> Decimal | None:
    """Parse an amount using explicit decimal and thousands separators."""

    cleaned_value = clean_amount(value)
    if not cleaned_value:
        return None
    decimal_separator, thousands_separator = _amount_separators(amount_format)
    if decimal_separator is None or decimal_separator == thousands_separator:
        return None

    sign = ""
    if cleaned_value[0] in {"+", "-"}:
        sign, cleaned_value = cleaned_value[0], cleaned_value[1:]
    if not cleaned_value:
        return None

    integer_part, decimal_part = _split_amount_parts(cleaned_value, decimal_separator)
    if integer_part is None or decimal_part is None:
        return None
    if not _has_valid_grouping(integer_part, thousands_separator):
        return None
    normalized_integer = integer_part.replace(thousands_separator or "\0", "")
    normalized_value = f"{sign}{normalized_integer}"
    if decimal_part:
        normalized_value += f".{decimal_part}"
    try:
        return Decimal(normalized_value)
    except InvalidOperation:
        return None


def normalize_amount(value: str, amount_format: dict | None = None) -> str | None:
    """Return an explicitly parsed amount as canonical decimal text."""

    amount = parse_decimal_amount(value, amount_format)
    return format(amount, "f") if amount is not None else None


def parse_date(value: str) -> date | None:
    """Parse common bank-export date formats without guessing from row order."""

    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    try:
        return datetime.fromisoformat(cleaned_value.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    normalized_value = cleaned_value.replace(".", "/").replace("-", "/")
    formats = [
        "%Y/%m/%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y",
        "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
        "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
    ]
    for date_format in formats:
        candidate = normalized_value if "/" in date_format else cleaned_value
        try:
            return datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    return None


def add_blocking_exception(exceptions: list[str], exception: str) -> None:
    """Record each unique export-blocking exception once."""

    if exception not in exceptions:
        exceptions.append(exception)


def validate_preview_value(
    exceptions: list[str],
    source_name: str,
    target_column: str,
    target_type: str,
    transform: str,
    value: str,
    amount_format: dict | None = None,
) -> None:
    """Record invalid non-empty mapped date and amount values."""

    if not value.strip():
        return
    if (transform == "parse_date" or target_type == "date") and parse_date(value) is None:
        add_blocking_exception(
            exceptions,
            f"{source_name}: '{value}' is not a recognized date for {target_column}.",
        )
    if (
        target_type == "money"
        and transform != "convert_currency"
        and parse_decimal_amount(value, amount_format) is None
    ):
        add_blocking_exception(
            exceptions,
            f"{source_name}: '{value}' is not a valid amount for {target_column}.",
        )


def _amount_separators(amount_format: dict | None) -> tuple[str | None, str | None]:
    """Return configured separators, retaining the legacy default when absent."""

    if amount_format is None:
        amount_format = DEFAULT_AMOUNT_FORMAT
    decimal_separator = amount_format.get("decimal_separator", ".")
    if decimal_separator not in {".", ","}:
        return None, None
    default_thousands = "," if decimal_separator == "." else "."
    thousands_separator = amount_format.get("thousands_separator", default_thousands)
    if thousands_separator not in {",", ".", " ", "'", None}:
        return None, None
    return decimal_separator, thousands_separator


def _split_amount_parts(
    value: str,
    decimal_separator: str,
) -> tuple[str | None, str | None]:
    """Split one amount into integer and fractional components."""

    if value.count(decimal_separator) > 1:
        return None, None
    integer_part, separator, decimal_part = value.partition(decimal_separator)
    if not integer_part or (separator and (not decimal_part or not decimal_part.isdigit())):
        return None, None
    return integer_part, decimal_part


def _has_valid_grouping(integer_part: str, thousands_separator: str | None) -> bool:
    """Require three-digit groups whenever a thousands separator is present."""

    if thousands_separator is None or thousands_separator not in integer_part:
        return integer_part.isdigit()
    groups = integer_part.split(thousands_separator)
    return (
        bool(groups[0])
        and len(groups[0]) <= 3
        and groups[0].isdigit()
        and all(len(group) == 3 and group.isdigit() for group in groups[1:])
    )
