"""Build and run AI planning from parsed source files and chat history."""

import json
import os
from dataclasses import dataclass
from typing import Any

from core.models import (
    AIUsageRecord,
    MergePlan,
    MergePlanningMessage,
    MergePlanningSession,
    Mergeset,
    MergesetFile,
)
from core.services.ai_usage import ensure_user_has_ai_credits, record_ai_usage


DEFAULT_OPENAI_MODEL = "gpt-5.5"


class OpenAIPlanningError(RuntimeError):
    """Raised when the OpenAI planning request cannot be completed."""


@dataclass(frozen=True)
class PlanningContext:
    """Serializable context passed to the AI planning layer."""

    system_prompt: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PlanningTurnResult:
    """Result of one AI planning turn."""

    response_payload: dict[str, Any]
    assistant_message: MergePlanningMessage
    merge_plan: MergePlan | None


def build_merge_planning_context(session: MergePlanningSession) -> PlanningContext:
    """Build deterministic prompt context for one planning conversation."""

    mergeset = session.mergeset
    return PlanningContext(
        system_prompt=_build_system_prompt(),
        payload={
            "mergeset": _build_mergeset_payload(mergeset),
            "source_files": [
                _build_source_file_payload(index, source_file)
                for index, source_file in enumerate(
                    mergeset.source_files.filter(
                        parse_status=MergesetFile.ParseStatus.PARSED
                    ),
                    start=1,
                )
            ],
            "conversation": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in session.messages.all()
            ],
            "response_contract": _build_response_contract(),
        },
    )


def run_merge_planning_turn(
    session: MergePlanningSession,
    client: Any | None = None,
) -> PlanningTurnResult:
    """Ask OpenAI for the next planning response and persist the outcome."""

    response_payload = request_merge_planning_response(session, client=client)
    assistant_message = MergePlanningMessage.objects.create(
        session=session,
        role=MergePlanningMessage.Role.ASSISTANT,
        content=response_payload["assistant_message"],
    )
    merge_plan = None

    if response_payload["status"] == "mapping_ready":
        merge_plan = MergePlan.objects.create(
            mergeset=session.mergeset,
            session=session,
            status=MergePlan.Status.NEEDS_REVIEW,
            plan_json=response_payload,
            ai_summary=response_payload["assistant_message"],
        )
        session.status = MergePlanningSession.Status.MAPPING_READY
        session.save(update_fields=["status", "updated_at"])
    else:
        if session.status != MergePlanningSession.Status.COLLECTING_REQUIREMENTS:
            session.status = MergePlanningSession.Status.COLLECTING_REQUIREMENTS
            session.save(update_fields=["status", "updated_at"])

    return PlanningTurnResult(
        response_payload=response_payload,
        assistant_message=assistant_message,
        merge_plan=merge_plan,
    )


def request_merge_planning_response(
    session: MergePlanningSession,
    client: Any | None = None,
) -> dict[str, Any]:
    """Call OpenAI and return a validated planning response payload."""

    planning_context = build_merge_planning_context(session)
    openai_client = client or _build_openai_client()
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    try:
        ensure_user_has_ai_credits(session.mergeset.owner)
    except ValueError as error:
        raise OpenAIPlanningError(str(error)) from error
    response = openai_client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": planning_context.system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(planning_context.payload),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "merge_planning_response",
                "strict": True,
                "schema": _build_openai_response_schema(),
            }
        },
    )
    response_payload = _extract_response_payload(response)
    _validate_response_payload(response_payload)
    record_ai_usage(
        user=session.mergeset.owner,
        mergeset=session.mergeset,
        planning_session=session,
        request_type=AIUsageRecord.RequestType.PLANNING,
        model=model,
        response=response,
    )
    return response_payload


def _build_openai_client() -> Any:
    """Create an OpenAI client from local environment configuration."""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIPlanningError("OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as error:
        raise OpenAIPlanningError("The openai Python package is not installed.") from error

    return OpenAI(api_key=api_key)


def _extract_response_payload(response: Any) -> dict[str, Any]:
    """Read a JSON payload from an OpenAI Responses API object."""

    output_text = getattr(response, "output_text", "")
    if not output_text:
        raise OpenAIPlanningError("OpenAI returned an empty planning response.")

    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise OpenAIPlanningError("OpenAI returned invalid planning JSON.") from error

    if not isinstance(payload, dict):
        raise OpenAIPlanningError("OpenAI planning response must be a JSON object.")
    return payload


def _validate_response_payload(payload: dict[str, Any]) -> None:
    """Validate the planning response shape before persistence."""

    status = payload.get("status")
    if status not in {"needs_clarification", "mapping_ready"}:
        raise OpenAIPlanningError("OpenAI returned an unsupported planning status.")
    if not isinstance(payload.get("assistant_message"), str):
        raise OpenAIPlanningError("OpenAI response is missing an assistant message.")
    if not isinstance(payload.get("questions"), list):
        raise OpenAIPlanningError("OpenAI response questions must be a list.")
    if not isinstance(payload.get("final_columns"), list):
        raise OpenAIPlanningError("OpenAI response final columns must be a list.")
    if not isinstance(payload.get("file_mappings"), list):
        raise OpenAIPlanningError("OpenAI response file mappings must be a list.")
    if not isinstance(payload.get("result_operations", []), list):
        raise OpenAIPlanningError("OpenAI response result operations must be a list.")


def _build_openai_response_schema() -> dict[str, Any]:
    """Return the strict JSON schema requested from OpenAI."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "assistant_message",
            "questions",
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
                    "required": ["file_id", "filename", "mappings", "ignored_columns"],
                    "properties": {
                        "file_id": {"type": "integer"},
                        "filename": {"type": "string"},
                        "mappings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "target_column",
                                    "source_columns",
                                    "transform",
                                    "notes",
                                ],
                                "properties": {
                                    "target_column": {"type": "string"},
                                    "source_columns": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "transform": {
                                        "type": "string",
                                        "enum": _supported_transforms(),
                                    },
                                    "notes": {"type": "string"},
                                },
                            },
                        },
                        "ignored_columns": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "result_operations": {
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
            },
        },
    }


def _build_system_prompt() -> str:
    """Return stable instructions for the merge planning assistant."""

    return (
        "You are SheetMerge's CSV column mapping planner. Review parsed CSV "
        "headers, sample rows, and the user's conversation. Ask concise "
        "clarifying questions when requirements are incomplete and make sure "
        "the confirmation message I show you how to write below is included "
        "in the clarifying message, don't make the user have to ask again. "
        "Only produce a mapping plan when the requested final columns and "
        "transformation rules are clear. If the user confirms your previous "
        "interpretation, accept that confirmation and return mapping_ready "
        "instead of asking for confirmation again. Do not repeat a question "
        "that the user has already answered. Ask only for missing information "
        "that blocks a safe column mapping. Write assistant_message in a "
        "natural, helpful tone, not a robotic checklist. When asking for "
        "clarification, state the exact decision you need the user to make, "
        "which source columns or mapping options you are choosing between, "
        "and why it matters. Guide the user without requiring them to inspect "
        "the spreadsheets. Make your best guess for each uncertain mapping "
        "and ask the user to confirm or correct it. Refer to files by "
        "file_number and filename, for example: 'For file 1 (bank.csv), I "
        "would use Posted Date as the date column. For file 2 (revolut.csv), "
        "I would use Completed Date. Is that right?' Do not ask abstract "
        "questions like 'which date field' without naming the specific files "
        "and columns. When returning mapping_ready, tell the user the plan is "
        "ready and they should proceed to column mapping. Preserve every "
        "final output column the user requests. If the user asks to keep all "
        "columns, all fields, or all data, create final columns for all "
        "available source headers across the uploaded files unless the user "
        "explicitly says to omit some. Do not collapse a wide spreadsheet "
        "into Date, Description, and Amount unless the user asked for that "
        "simplified transaction format. Do not ask for generic confirmation "
        "without summarizing what is being confirmed. Do not invent source "
        "columns."
    )


def _build_mergeset_payload(mergeset: Mergeset) -> dict[str, Any]:
    """Return identifying context for the current merge job."""

    return {
        "id": mergeset.id,
        "name": mergeset.name,
        "description": mergeset.description,
    }


def _build_source_file_payload(index: int, source_file: MergesetFile) -> dict[str, Any]:
    """Return parsed source-file context for AI planning."""

    return {
        "file_number": index,
        "id": source_file.id,
        "filename": source_file.original_name,
        "headers": source_file.headers,
        "delimiter": source_file.delimiter,
        "row_count": source_file.row_count,
        "sample_rows": source_file.sample_rows,
    }


def _build_response_contract() -> dict[str, Any]:
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
            "Use only the supported transform names exactly as written.",
        ],
        "needs_clarification": {
            "required_fields": ["status", "assistant_message", "questions"],
        },
        "mapping_ready": {
            "required_fields": [
                "status",
                "assistant_message",
                "final_columns",
                "file_mappings",
                "result_operations",
            ],
        },
        "supported_transforms": _supported_transforms(),
    }


def _supported_transforms() -> list[str]:
    """Return transform names accepted in generated merge plans."""

    return [
        "copy",
        "parse_date",
        "parse_amount",
        "debit_credit_to_signed_amount",
        "credit_debit_to_signed_amount",
        "combine_text",
        "constant_source_name",
        "ignore",
    ]
