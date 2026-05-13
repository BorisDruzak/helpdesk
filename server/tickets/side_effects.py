"""Workflow side-effect execution, audit and metrics helpers."""

from __future__ import annotations

import inspect
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from loguru import logger


SideEffectOperation = Callable[[], Awaitable[Any] | Any]

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|secret|password|authorization|api[_-]?key)=([^,\s;&]+)"),
    re.compile(r"(?i)(bearer\s+)([a-z0-9._\-]+)"),
)
_SIDE_EFFECT_FAILURES: Counter[tuple[str, str]] = Counter()


class WorkflowSideEffectError(RuntimeError):
    """Raised after a critical side-effect failure has been audited."""

    def __init__(self, result: dict):
        super().__init__(
            f"critical workflow side effect failed: "
            f"{result.get('side_effect')}.{result.get('action')}"
        )
        self.result = result


def _redact_error_message(message: str) -> str:
    redacted = str(message or "")
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=<redacted>", redacted)
    return redacted


def reset_workflow_side_effect_metrics() -> None:
    _SIDE_EFFECT_FAILURES.clear()


def get_workflow_side_effect_metric(side_effect: str, action: str) -> int:
    return _SIDE_EFFECT_FAILURES[(side_effect, action)]


def _record_failure_metric(side_effect: str, action: str) -> None:
    _SIDE_EFFECT_FAILURES[(side_effect, action)] += 1


async def _maybe_await(value: Awaitable[Any] | Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def run_workflow_side_effect(
    *,
    ticket_repo: Any,
    ticket_id: str,
    device_id: str | None = None,
    side_effect: str,
    action: str,
    trigger: str | None,
    from_status: str | None,
    to_status: str | None,
    actor_id: str | None,
    actor_role: str | None,
    critical: bool,
    operation: SideEffectOperation,
    event_payload: dict | None = None,
    correlation_id: str | None = None,
    retryable: bool = True,
) -> dict:
    """Run a workflow side effect and make failures observable.

    Critical failures are logged/audited/metriced first, then raised as
    `WorkflowSideEffectError`. Non-critical failures return a structured result.
    """

    context = {
        "ticket_id": ticket_id,
        "side_effect": side_effect,
        "action": action,
        "trigger": trigger,
        "from_status": from_status,
        "to_status": to_status,
        "actor_role": actor_role,
        "correlation_id": correlation_id,
    }
    try:
        value = await _maybe_await(operation())
        status = "executed" if value is not False else "no_op"
        result = {
            "status": status,
            "side_effect": side_effect,
            "action": action,
            "retryable": False,
        }
        if isinstance(value, dict):
            result.update(value)
            result.setdefault("status", status)
            result.setdefault("side_effect", side_effect)
            result.setdefault("action", action)
        if event_payload is not None:
            event_payload.setdefault("workflow_side_effect_results", []).append(result)
        return result
    except Exception as exc:
        error_message = _redact_error_message(str(exc))
        result = {
            "status": "failed",
            "side_effect": side_effect,
            "action": action,
            "error_class": exc.__class__.__name__,
            "error_message_redacted": error_message,
            "retryable": retryable,
            "critical": critical,
        }
        if event_payload is not None:
            event_payload.setdefault("workflow_side_effect_results", []).append(result)
        _record_failure_metric(side_effect, action)
        logger.exception("[WorkflowSideEffect] failure {context}", context=context)

        audit_payload = {
            **context,
            "actor_id": actor_id,
            "error_class": result["error_class"],
            "error_message_redacted": error_message,
            "retryable": retryable,
            "critical": critical,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await ticket_repo.add_event(
                ticket_id=ticket_id,
                device_id=device_id or "",
                agent_seq=None,
                event_type="workflow_side_effect_failed",
                payload=audit_payload,
                trace_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "[WorkflowSideEffect] failed to write audit event {context}",
                context=context,
            )
        if critical:
            raise WorkflowSideEffectError(result) from exc
        return result
