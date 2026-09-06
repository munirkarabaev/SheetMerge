"""Safe CSV serialization helpers."""

from core.services.preview_validation import parse_decimal_amount


FORMULA_PREFIXES = ("=", "+", "-", "@")


def escape_spreadsheet_formula(value: str) -> str:
    """Prevent spreadsheet applications from evaluating untrusted CSV text."""

    if not value.lstrip().startswith(FORMULA_PREFIXES):
        return value
    if parse_decimal_amount(value) is not None:
        return value
    return f"'{value}"
