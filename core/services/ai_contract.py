"""Shared AI merge-plan response contract."""

from typing import Any


def build_openai_response_schema() -> dict[str, Any]:
    """Return the strict JSON schema requested from OpenAI."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "assistant_message",
            "questions",
            "output_currency",
            "currency_conversion",
            "final_columns",
            "file_mappings",
            "result_operations",
        ],
        "properties": {
            "status": {
                "type": "string",
                "enum": ["needs_clarification", "mapping_ready"],
            },
            "assistant_message": {"type": "string"},
            "questions": {"type": "array", "items": {"type": "string"}},
            "output_currency": {"type": ["string", "null"]},
            "currency_conversion": {
                "type": "object",
                "additionalProperties": False,
                "required": ["required", "target_currency", "rate_basis", "notes"],
                "properties": {
                    "required": {"type": "boolean"},
                    "target_currency": {"type": ["string", "null"]},
                    "rate_basis": {
                        "type": "string",
                        "enum": ["monthly_average", "not_applicable"],
                    },
                    "notes": {"type": "string"},
                },
            },
            "final_columns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "type"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                    },
                },
            },
            "file_mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "file_id",
                        "filename",
                        "detected_currency",
                        "mappings",
                        "ignored_columns",
                    ],
                    "properties": {
                        "file_id": {"type": "integer"},
                        "filename": {"type": "string"},
                        "detected_currency": _currency_detection_schema(),
                        "mappings": _column_mappings_schema(),
                        "ignored_columns": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "result_operations": _result_operations_schema(),
        },
    }


def build_response_contract() -> dict[str, Any]:
    """Describe the response shapes the AI integration should request."""

    return {
        "statuses": ["needs_clarification", "mapping_ready"],
        "workflow_rules": [
            "Return needs_clarification only when missing information blocks mapping.",
            "Return mapping_ready when final columns and mapping rules are clear.",
            "Treat confirmations such as yes, confirmed, I confirm, correct, or go ahead as approval of your previous interpretation.",
            "Do not ask the same clarification question twice after the user has answered it.",
            "Every clarification message must name the exact choice needed and why it affects the mapping.",
            "Assistant messages should sound natural and specific, not robotic or generic.",
            "If clarification is about a column, name the source columns or mapping options being compared.",
            "When status is mapping_ready, assistant_message must tell the user to proceed to column mapping.",
            "Preserve every final column requested by the user; do not silently drop requested columns.",
            "If the user asks to keep all columns, include all uploaded source headers as final columns unless they explicitly exclude some.",
            "Do not default to a Date, Description, Amount transaction layout unless the user requested that simplified layout.",
            "Use result_operations for whole-spreadsheet edits such as sorting rows after mapping.",
            "For uncertain mappings, make a best guess per file and ask the user to confirm or correct it.",
            "Clarification questions must name the file number, filename, and candidate source columns instead of asking abstractly.",
            "Detect source currencies from currency columns, headers, symbols, filenames, and sample rows.",
            "If currency conversion is requested but a source currency is ambiguous, ask a concrete file-specific question.",
            "Use output_currency and currency_conversion when the user asks to normalize amounts into one currency.",
            "For every parse_amount, signed-amount, or convert_currency mapping, specify amount_format with decimal_separator and thousands_separator.",
            "Use only the supported transform names exactly as written.",
        ],
        "needs_clarification": {
            "required_fields": ["status", "assistant_message", "questions"],
        },
        "mapping_ready": {
            "required_fields": [
                "status",
                "assistant_message",
                "output_currency",
                "currency_conversion",
                "final_columns",
                "file_mappings",
                "result_operations",
            ],
        },
        "currency_detection": {
            "confidence_values": ["high", "medium", "low", "unknown"],
            "evidence_examples": [
                "Currency column values",
                "amount symbols",
                "currency codes in headers",
                "filename hints",
                "sample row text",
            ],
        },
        "supported_transforms": supported_transforms(),
    }


def supported_transforms() -> list[str]:
    """Return transform names accepted in generated merge plans."""

    return [
        "copy",
        "parse_date",
        "parse_amount",
        "convert_currency",
        "debit_credit_to_signed_amount",
        "credit_debit_to_signed_amount",
        "combine_text",
        "constant_source_name",
        "ignore",
    ]


def _currency_detection_schema() -> dict[str, Any]:
    """Return schema for one file's detected currency evidence."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["currency", "confidence", "evidence", "ambiguity"],
        "properties": {
            "currency": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low", "unknown"],
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
            "ambiguity": {"type": "string"},
        },
    }


def _column_mappings_schema() -> dict[str, Any]:
    """Return schema for per-column mappings."""

    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_column", "source_columns", "transform", "notes"],
            "properties": {
                "target_column": {"type": "string"},
                "source_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "transform": {
                    "type": "string",
                    "enum": supported_transforms(),
                },
                "amount_format": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["decimal_separator", "thousands_separator"],
                    "properties": {
                        "decimal_separator": {"type": "string", "enum": [".", ","]},
                        "thousands_separator": {
                            "type": ["string", "null"],
                            "enum": [",", ".", " ", "'", None],
                        },
                    },
                },
                "notes": {"type": "string"},
            },
        },
    }


def _result_operations_schema() -> dict[str, Any]:
    """Return schema for whole-result operations."""

    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["type", "column", "direction"],
            "properties": {
                "type": {"type": "string", "enum": ["sort"]},
                "column": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["ascending", "descending"],
                },
            },
        },
    }
