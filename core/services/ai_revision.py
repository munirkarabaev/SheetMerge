"""Revise generated merge plans using AI instructions from the review page."""

import json
import os
from dataclasses import dataclass
from typing import Any

from core.models import MergePlan, MergePlanningMessage
from core.services.ai_planning import (
    DEFAULT_OPENAI_MODEL,
    OpenAIPlanningError,
    _build_openai_client,
    _build_openai_response_schema,
    _extract_response_payload,
    _validate_response_payload,
)
from core.services.merge_preview import build_merge_preview


@dataclass(frozen=True)
class PlanRevisionResult:
    """Result of one AI plan revision."""

    response_payload: dict[str, Any]
    assistant_message: MergePlanningMessage
    merge_plan: MergePlan


def run_merge_plan_revision(
    merge_plan: MergePlan,
    instruction: str,
    client: Any | None = None,
) -> PlanRevisionResult:
    """Ask OpenAI to revise a merge plan and persist the new version."""

    MergePlanningMessage.objects.create(
        session=merge_plan.session,
        role=MergePlanningMessage.Role.USER,
        content=instruction,
    )
    response_payload = request_merge_plan_revision(merge_plan, instruction, client=client)
    assistant_message = MergePlanningMessage.objects.create(
        session=merge_plan.session,
        role=MergePlanningMessage.Role.ASSISTANT,
        content=response_payload["assistant_message"],
    )
    revised_plan = MergePlan.objects.create(
        mergeset=merge_plan.mergeset,
        session=merge_plan.session,
        status=MergePlan.Status.NEEDS_REVIEW,
        plan_json=response_payload,
        ai_summary=response_payload["assistant_message"],
    )
    return PlanRevisionResult(
        response_payload=response_payload,
        assistant_message=assistant_message,
        merge_plan=revised_plan,
    )


def request_merge_plan_revision(
    merge_plan: MergePlan,
    instruction: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Call OpenAI for a revised mapping plan."""

    openai_client = client or _build_openai_client()
    response = openai_client.responses.create(
        model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        input=[
            {"role": "system", "content": _build_revision_system_prompt()},
            {"role": "user", "content": json.dumps(_build_revision_payload(merge_plan, instruction))},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "merge_plan_revision",
                "strict": True,
                "schema": _build_openai_response_schema(),
            }
        },
    )
    response_payload = _extract_response_payload(response)
    _validate_response_payload(response_payload)
    if response_payload["status"] != "mapping_ready":
        raise OpenAIPlanningError("Plan revisions must return a ready mapping plan.")
    return response_payload


def _build_revision_system_prompt() -> str:
    """Return instructions for revising an existing plan."""

    return (
        "You revise an existing SheetMerge mapping plan. Keep the current "
        "final columns and file mappings unless the user explicitly asks to "
        "change them. For whole-spreadsheet edits such as sorting rows, update "
        "result_operations instead of changing column mappings. Return a full "
        "mapping_ready plan, not a partial patch."
    )


def _build_revision_payload(merge_plan: MergePlan, instruction: str) -> dict[str, Any]:
    """Build context for an AI plan revision."""

    preview = build_merge_preview(merge_plan, limit=10)
    return {
        "instruction": instruction,
        "current_plan": merge_plan.plan_json,
        "preview": {
            "columns": preview.columns,
            "rows": preview.rows,
        },
    }
