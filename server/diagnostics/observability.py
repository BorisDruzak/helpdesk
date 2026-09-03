from __future__ import annotations

import inspect
import time
from typing import Any

from shared.redaction import REDACTED, redact_sensitive_payload


CAPABILITY_LIFECYCLE_EVENTS = frozenset(
    {
        "capability_run_started",
        "capability_run_succeeded",
        "capability_run_failed",
        "capability_run_blocked",
        "capability_evidence_linked",
    }
)

PRIVATE_RUNTIME_KEYS = frozenset(
    {
        "_credentials_ref",
        "credentials_ref",
        "_integration_config",
        "integration_config",
        "_mapping",
        "mapping",
    }
)

INTEGRATION_TARGETS = frozenset({"server_connector"})
EXTERNAL_TARGETS = frozenset({"server_connector", "observer_query"})
SOURCE_BY_TARGET = {
    "server_builtin": "diagnostic_server_builtin",
    "server_connector": "diagnostic_server_connector",
    "observer_query": "diagnostic_observer_query",
    "manual": "diagnostic_manual",
}


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def actor_id(actor: Any) -> str | None:
    value = getattr(actor, "actor_id", None)
    return str(value) if value else None


def actor_role(actor: Any) -> str | None:
    value = getattr(actor, "actor_role", None)
    return str(value) if value else None


def audit_source_for_target(execution_target: str | None) -> str:
    return SOURCE_BY_TARGET.get(str(execution_target or "").strip(), "diagnostic_capability")


def capability_audit_required(capability: Any) -> bool:
    risk_level = str(getattr(capability, "risk_level", "") or "").strip().lower()
    target = str(getattr(capability, "execution_target", "") or "").strip()
    if risk_level in {"medium", "high", "danger", "dangerous", "critical"}:
        return True
    if bool(getattr(capability, "requires_integration", False)):
        return True
    return target in EXTERNAL_TARGETS


def redact_diagnostic_payload(payload: Any) -> Any:
    return _strip_private_runtime_fields(redact_sensitive_payload(payload, extra_markers={"credential"}))


def build_metric_snapshot(
    *,
    result: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    readiness_failed: bool = False,
    evidence_linked: bool = False,
) -> dict[str, Any]:
    payload = result or {}
    status = str(payload.get("status") or "").strip().lower()
    error_code = str(payload.get("error_code") or "").strip()
    provider_error = bool(error_code and error_code not in {"CAPABILITY_NOT_READY", "CAPABILITY_TARGET_UNSUPPORTED"})
    return {
        "duration_ms": duration_ms,
        "result_status": status or None,
        "readiness_failure_count": 1 if readiness_failed else 0,
        "provider_error_count": 1 if provider_error else 0,
        "evidence_linked_count": 1 if evidence_linked else 0,
    }


def build_capability_audit_details(
    *,
    capability: Any,
    ticket_id: str | None,
    device_id: str | None,
    params: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    readiness: Any = None,
    duration_ms: int | None = None,
    idempotency_key: str | None = None,
    timeout_ms: int | None = None,
    evidence_id: str | None = None,
    stage: str,
) -> dict[str, Any]:
    readiness_dict = _readiness_dict(readiness)
    evidence = getattr(capability, "evidence", None) or {}
    result_payload = result or {}
    readiness_failed = bool(result_payload.get("error_code") == "CAPABILITY_NOT_READY")
    evidence_linked = bool(evidence_id or result_payload.get("diagnostic_evidence_id") or result_payload.get("evidence_persisted"))
    return redact_diagnostic_payload(
        {
            "stage": stage,
            "capability_id": getattr(capability, "id", None) or result_payload.get("capability_id"),
            "provider_id": getattr(capability, "provider_id", None) or result_payload.get("provider_id"),
            "provider_type": getattr(capability, "provider_type", None) or result_payload.get("provider_type"),
            "execution_target": getattr(capability, "execution_target", None) or result_payload.get("execution_target"),
            "execution_kind": result_payload.get("execution_kind"),
            "ticket_id": ticket_id,
            "device_id": device_id,
            "operation_id": result_payload.get("operation_id"),
            "query_id": result_payload.get("query_id"),
            "session_id": result_payload.get("session_id"),
            "idempotency_key": idempotency_key or result_payload.get("idempotency_key"),
            "timeout_ms": timeout_ms if timeout_ms is not None else result_payload.get("timeout_ms"),
            "audit_required": capability_audit_required(capability),
            "readiness": readiness_dict or None,
            "params_snapshot": dict(params or {}),
            "result_snapshot": _result_snapshot(result_payload),
            "metrics": build_metric_snapshot(
                result=result_payload,
                duration_ms=duration_ms,
                readiness_failed=readiness_failed,
                evidence_linked=evidence_linked,
            ),
            "diagnostic_evidence_id": evidence_id or result_payload.get("diagnostic_evidence_id"),
            "evidence": {
                "kind": evidence.get("kind"),
                "domain": evidence.get("domain"),
                "perspective": evidence.get("perspective"),
                "passport_eligible": bool(evidence.get("passport_eligible")),
            }
            if isinstance(evidence, dict)
            else None,
        }
    )


class NullCapabilityExecutionObserver:
    async def record_started(self, **_: Any) -> None:
        return None

    async def record_finished(self, **_: Any) -> None:
        return None

    async def record_evidence_linked(self, **_: Any) -> None:
        return None


class RuntimeAuditCapabilityExecutionObserver:
    """Writes capability lifecycle events into runtime audit for observer projection."""

    def __init__(self, *, state: Any = None) -> None:
        self.state = state

    async def record_started(self, **kwargs: Any) -> None:
        await self._record(
            event_type="capability_run_started",
            severity="info",
            stage="started",
            **kwargs,
        )

    async def record_finished(self, **kwargs: Any) -> None:
        result = kwargs.get("result") if isinstance(kwargs.get("result"), dict) else {}
        error = kwargs.get("error")
        event_type = _finished_event_type(result, error=error)
        await self._record(
            event_type=event_type,
            severity=_finished_severity(result, error=error),
            stage="finished",
            **kwargs,
        )

    async def record_evidence_linked(self, **kwargs: Any) -> None:
        await self._record(
            event_type="capability_evidence_linked",
            severity="info",
            stage="evidence_linked",
            **kwargs,
        )

    async def _record(
        self,
        *,
        event_type: str,
        severity: str,
        stage: str,
        capability: Any,
        ticket_id: str | None,
        device_id: str | None,
        actor: Any = None,
        params: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        readiness: Any = None,
        duration_ms: int | None = None,
        idempotency_key: str | None = None,
        timeout_ms: int | None = None,
        evidence_id: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        details = build_capability_audit_details(
            capability=capability,
            ticket_id=ticket_id,
            device_id=device_id,
            params=params,
            result=_result_with_error(result, error),
            readiness=readiness,
            duration_ms=duration_ms,
            idempotency_key=idempotency_key,
            timeout_ms=timeout_ms,
            evidence_id=evidence_id,
            stage=stage,
        )
        await self._persist_runtime_audit(
            device_id=device_id or "server",
            event_type=event_type,
            severity=severity,
            source=audit_source_for_target(getattr(capability, "execution_target", None)),
            operation_id=str((result or {}).get("operation_id") or "") or None,
            ticket_id=ticket_id,
            actor_id=actor_id(actor),
            actor_role=actor_role(actor),
            details_json=details,
        )

    async def _persist_runtime_audit(self, **kwargs: Any) -> None:
        from app.db import get_session
        from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo

        async with get_session() as session:
            audit = await AgentRuntimeAuditRepo(session).add(**kwargs)
            audit_id = audit.id
            await session.commit()
        await _maybe_enqueue_runtime_audit_trace(self.state, audit_id)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _maybe_enqueue_runtime_audit_trace(state: Any, audit_id: int | None) -> None:
    if state is None or audit_id is None:
        return
    runtime = getattr(state, "observer_refresh_runtime", None)
    if runtime is None and isinstance(state, dict):
        runtime = state.get("observer_refresh_runtime")
    if runtime is None or not hasattr(runtime, "enqueue_trace"):
        return
    try:
        from observer.service import _runtime_audit_trace_id

        trace_id = _runtime_audit_trace_id(audit_id)
        if trace_id:
            await _maybe_await(runtime.enqueue_trace(trace_id, delay_sec=0.0))
    except Exception:
        return


def _finished_event_type(result: dict[str, Any], *, error: BaseException | None = None) -> str:
    if error is not None:
        return "capability_run_failed"
    if result.get("error_code") == "CAPABILITY_NOT_READY":
        return "capability_run_blocked"
    status = str(result.get("status") or "").strip().lower()
    if status in {"error", "failed", "failure", "unsupported"} or result.get("error_code"):
        return "capability_run_failed"
    return "capability_run_succeeded"


def _finished_severity(result: dict[str, Any], *, error: BaseException | None = None) -> str:
    if error is not None:
        return "error"
    if result.get("error_code") == "CAPABILITY_NOT_READY":
        return "warning"
    status = str(result.get("status") or "").strip().lower()
    if status in {"error", "failed", "failure", "unsupported"} or result.get("error_code"):
        return "error"
    return "info"


def _result_with_error(result: dict[str, Any] | None, error: BaseException | None) -> dict[str, Any]:
    payload = dict(result or {})
    if error is not None:
        payload.setdefault("status", "error")
        payload.setdefault("error_code", type(error).__name__)
        payload.setdefault("error_message", str(error))
    return payload


def _readiness_dict(readiness: Any) -> dict[str, Any]:
    if readiness is None:
        return {}
    if hasattr(readiness, "to_dict"):
        value = readiness.to_dict()
        return dict(value) if isinstance(value, dict) else {}
    if isinstance(readiness, dict):
        return dict(readiness)
    return {"readiness": str(readiness)}


def _result_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "operation_id": result.get("operation_id"),
        "query_id": result.get("query_id"),
        "session_id": result.get("session_id"),
        "summary": result.get("summary") or result.get("message"),
        "error_code": result.get("error_code"),
        "error_message": result.get("error_message"),
        "diagnostic_status": result.get("diagnostic_status"),
        "output": result.get("output") if isinstance(result.get("output"), dict) else {},
        "evidence_preview": result.get("evidence_preview") if isinstance(result.get("evidence_preview"), dict) else None,
    }


def _strip_private_runtime_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            normalized = str(key or "").strip()
            if normalized in PRIVATE_RUNTIME_KEYS:
                out[normalized] = _redacted_runtime_field(normalized, value)
                continue
            out[normalized] = _strip_private_runtime_fields(value)
        return out
    if isinstance(payload, list):
        return [_strip_private_runtime_fields(item) for item in payload]
    return payload


def _redacted_runtime_field(key: str, value: Any) -> Any:
    if value in (None, "", {}, []):
        return value
    if key in {"_credentials_ref", "credentials_ref"}:
        return {"redacted": True, "reason": "credentials_ref"}
    if isinstance(value, dict):
        return {
            "redacted": True,
            "reason": key.strip("_"),
            "keys": sorted(str(item) for item in value.keys()),
        }
    return REDACTED
