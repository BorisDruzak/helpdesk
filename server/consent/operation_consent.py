from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Operation, Ticket
from consent.service import ConsentAccessError, UserConsentService


SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "session_token",
    "token",
)


def _redact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "<redacted-depth>"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEY_PARTS):
                redacted[key_text] = "<redacted>"
            else:
                redacted[key_text] = _redact_value(item, depth=depth + 1)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value[:500]
    return value


def _policy_snapshot(policy_decision: Any) -> dict[str, Any]:
    return {
        "allow": bool(getattr(policy_decision, "allow", False)),
        "requires_consent": bool(getattr(policy_decision, "requires_consent", False)),
        "reason": str(getattr(policy_decision, "reason", "") or ""),
        "required_role": str(getattr(policy_decision, "required_role", "") or ""),
    }


async def create_operation_user_consent(
    session: AsyncSession,
    *,
    operation: Operation,
    ticket: Ticket,
    requested_by_actor_id: str | None,
    requested_by_role: str | None,
    risk_level: str | None,
    tool_name: str | None,
    params: dict[str, Any] | None,
    policy_decision: Any = None,
    expires_at: datetime | None = None,
) -> None:
    requester_person_id = getattr(ticket, "requester_person_id", None)
    if not requester_person_id:
        raise ConsentAccessError(
            "requester-scoped user consent requires ticket requester_person_id",
            error_code="REQUESTER_SCOPE_REQUIRED",
            status=409,
        )
    device_id = getattr(operation, "device_id", None) or getattr(ticket, "device_id", None)
    if device_id and getattr(ticket, "device_id", None) and device_id != getattr(ticket, "device_id", None):
        raise ConsentAccessError(
            "operation device does not match ticket device",
            error_code="REQUESTER_SCOPE_MISMATCH",
            status=409,
        )

    await UserConsentService(session).create_request(
        subject_type="operation",
        subject_id=str(operation.operation_id),
        ticket_id=getattr(ticket, "ticket_id", None),
        device_id=device_id,
        requester_person_id=requester_person_id,
        requester_binding_id=getattr(ticket, "requester_binding_id", None),
        requester_account_session_id=getattr(ticket, "requester_account_session_id", None),
        requested_by_actor_id=requested_by_actor_id,
        requested_by_role=requested_by_role,
        risk_level=risk_level,
        policy_snapshot=_policy_snapshot(policy_decision) if policy_decision is not None else {},
        risk_explanation=str(getattr(policy_decision, "reason", "") or "") or None,
        requested_action_payload_redacted={
            "tool_name": tool_name,
            "params": _redact_value(params or {}),
        },
        title=f"Approve operation: {tool_name or operation.kind}",
        description="A support operation is waiting for requester consent.",
        expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(minutes=30)),
        metadata={"source": "operation_waiting_consent"},
    )
