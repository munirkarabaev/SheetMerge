"""Track token-based AI credits for completed OpenAI requests."""

from typing import Any

from django.db import transaction
from django.db.models import F

from core.models import AIUsageRecord, MergePlanningSession, Mergeset


def ensure_user_has_ai_credits(user: Any) -> None:
    """Require a positive token credit balance before starting an AI request."""

    user.refresh_from_db(fields=["ai_token_credit_balance"])
    if user.ai_token_credit_balance <= 0:
        raise ValueError("AI token credits are exhausted.")


def record_ai_usage(
    *,
    user: Any,
    mergeset: Mergeset,
    planning_session: MergePlanningSession | None,
    request_type: str,
    model: str,
    response: Any,
) -> AIUsageRecord:
    """Store token usage and deduct exactly one credit per used token."""

    token_usage = extract_response_token_usage(response)
    credits_used = token_usage["total_tokens"]
    with transaction.atomic():
        usage_record = AIUsageRecord.objects.create(
            user=user,
            mergeset=mergeset,
            planning_session=planning_session,
            request_type=request_type,
            model=model,
            input_tokens=token_usage["input_tokens"],
            output_tokens=token_usage["output_tokens"],
            total_tokens=token_usage["total_tokens"],
            credits_used=credits_used,
        )
        user.__class__.objects.filter(pk=user.pk).update(
            ai_token_credit_balance=F("ai_token_credit_balance") - credits_used
        )
    user.refresh_from_db(fields=["ai_token_credit_balance"])
    return usage_record


def extract_response_token_usage(response: Any) -> dict[str, int]:
    """Read token counts from an OpenAI Responses API object."""

    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    input_tokens = _read_usage_int(usage, "input_tokens")
    output_tokens = _read_usage_int(usage, "output_tokens")
    total_tokens = _read_usage_int(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _read_usage_int(usage: Any, name: str) -> int:
    """Return a non-negative integer usage value from object or dict data."""

    if isinstance(usage, dict):
        value = usage.get(name, 0)
    else:
        value = getattr(usage, name, 0)
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0
