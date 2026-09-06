"""Semantic validation for AI-proposed merge plans."""

import re

from core.models import Mergeset, MergesetFile
from core.services.ai_contract import supported_transforms


class MergePlanValidationError(ValueError):
    """Raised when a structured AI response is unsafe to persist or execute."""


_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_AMOUNT_TRANSFORMS = {
    "parse_amount",
    "convert_currency",
    "debit_credit_to_signed_amount",
    "credit_debit_to_signed_amount",
}


def validate_merge_plan_payload(mergeset: Mergeset, payload: dict) -> None:
    """Ensure a mapping-ready plan references only deterministic local data."""

    if payload.get("status") != "mapping_ready":
        return

    final_columns = payload.get("final_columns", [])
    names = [column.get("name", "").strip() for column in final_columns]
    if not names or any(not name for name in names) or len(names) != len(set(names)):
        raise MergePlanValidationError("Mapping-ready plans need unique, non-empty final columns.")

    _validate_currency_policy(payload)
    parsed_files = {
        source_file.id: source_file
        for source_file in mergeset.source_files.filter(
            parse_status=MergesetFile.ParseStatus.PARSED
        )
    }
    for file_mapping in payload.get("file_mappings", []):
        _validate_file_mapping(file_mapping, parsed_files, set(names), payload)
    _validate_result_operations(payload.get("result_operations", []), set(names))


def _validate_file_mapping(
    file_mapping: dict,
    parsed_files: dict[int, MergesetFile],
    final_columns: set[str],
    payload: dict,
) -> None:
    """Validate one source-file mapping against parsed local headers."""

    source_file = parsed_files.get(file_mapping.get("file_id"))
    if source_file is None:
        raise MergePlanValidationError("Plan references an unknown or unparsed source file.")
    source_headers = set(source_file.headers)
    detected_currency = file_mapping.get("detected_currency", {})
    for mapping in file_mapping.get("mappings", []):
        transform = mapping.get("transform")
        target_column = mapping.get("target_column")
        if transform not in supported_transforms():
            raise MergePlanValidationError(f"Plan uses unsupported transform: {transform}.")
        if target_column not in final_columns:
            raise MergePlanValidationError("Plan maps into a column not declared as final output.")
        source_columns = mapping.get("source_columns", [])
        if transform not in {"constant_source_name", "ignore"} and not source_columns:
            raise MergePlanValidationError("Plan mapping is missing its source column.")
        if any(column not in source_headers for column in source_columns):
            raise MergePlanValidationError("Plan references a source column that does not exist.")
        if transform in _AMOUNT_TRANSFORMS:
            _validate_amount_format(mapping.get("amount_format"))
        if transform == "convert_currency":
            _validate_conversion_mapping(detected_currency, payload)


def _validate_amount_format(amount_format: dict | None) -> None:
    """Validate explicit locale rules when an amount mapping provides them."""

    if amount_format is None:
        return
    decimal = amount_format.get("decimal_separator")
    thousands = amount_format.get("thousands_separator")
    if decimal not in {".", ","} or thousands not in {",", ".", " ", "'", None}:
        raise MergePlanValidationError("Plan has invalid amount locale separators.")
    if decimal == thousands:
        raise MergePlanValidationError("Amount decimal and thousands separators must differ.")


def _validate_currency_policy(payload: dict) -> None:
    """Validate plan-level currency intent before row conversion can occur."""

    output_currency = payload.get("output_currency")
    conversion = payload.get("currency_conversion", {})
    target_currency = conversion.get("target_currency") or output_currency
    if output_currency and not _CURRENCY_CODE.fullmatch(output_currency):
        raise MergePlanValidationError("Plan has an invalid output currency code.")
    if conversion.get("required") and not (
        isinstance(target_currency, str) and _CURRENCY_CODE.fullmatch(target_currency)
    ):
        raise MergePlanValidationError("Currency conversion requires a valid target currency.")


def _validate_conversion_mapping(detected_currency: dict, payload: dict) -> None:
    """Require a confident source currency before a conversion can execute."""

    currency = detected_currency.get("currency")
    confidence = detected_currency.get("confidence")
    if not isinstance(currency, str) or not _CURRENCY_CODE.fullmatch(currency):
        raise MergePlanValidationError("Currency conversion requires a valid source currency.")
    if confidence not in {"high", "medium"}:
        raise MergePlanValidationError(
            "Currency conversion with low confidence requires user clarification."
        )
    if not payload.get("currency_conversion", {}).get("required"):
        raise MergePlanValidationError("Currency conversion transform requires conversion intent.")


def _validate_result_operations(operations: list[dict], final_columns: set[str]) -> None:
    """Ensure whole-result operations can be executed deterministically."""

    for operation in operations:
        if operation.get("type") != "sort" or operation.get("column") not in final_columns:
            raise MergePlanValidationError("Plan has an invalid result operation.")
        if operation.get("direction") not in {"ascending", "descending"}:
            raise MergePlanValidationError("Plan has an invalid sort direction.")
