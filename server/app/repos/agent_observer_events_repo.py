"""Repository for bounded agent observer telemetry events."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentObserverEvent
from shared.redaction import redact_sensitive_payload


AGENT_OBSERVER_NAMESPACE = uuid.UUID("1e406a2e-6cd1-4b8f-8023-3e902ac337e6")
MAX_AGENT_OBSERVER_BATCH = 100
ALLOWED_SEVERITIES = {"info", "warning", "error", "critical"}
ALLOWED_ROOT_KINDS = {
    "agent_runtime",
    "agent_update",
    "tool_call",
    "module_install",
    "module_update",
    "module_remove",
}
ALLOWED_EVENT_TYPES = {
    "agent.startup",
    "agent.shutdown",
    "agent.crash_detected",
    "agent.ws.connecting",
    "agent.ws.connected",
    "agent.ws.reconnect",
    "agent.ws.handshake_sent",
    "agent.update.check",
    "agent.update.launcher",
    "agent.update.apply",
    "agent.tool.step",
    "agent.module.install_step",
    "agent.module.activate",
    "agent.telemetry.upload_failed",
}


def _compact(value: Any, *, max_len: int | None = None) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_len] if max_len else text


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return datetime.now(timezone.utc)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def synthetic_agent_observer_trace_id(event_id: str) -> str:
    return str(uuid.uuid5(AGENT_OBSERVER_NAMESPACE, f"agent_observer_event:{event_id}"))


def normalize_agent_observer_severity(value: Any) -> str:
    severity = str(value or "").strip().lower()
    return severity if severity in ALLOWED_SEVERITIES else "info"


def normalize_agent_observer_root_kind(value: Any) -> str:
    root_kind = str(value or "").strip().lower()
    return root_kind if root_kind in ALLOWED_ROOT_KINDS else "agent_runtime"


class AgentObserverEventsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ingest_batch(self, *, device_id: str, events: list[dict[str, Any]]) -> list[AgentObserverEvent]:
        accepted: list[AgentObserverEvent] = []
        safe_device_id = _compact(device_id, max_len=36)
        if not safe_device_id:
            return accepted

        for raw_event in list(events or [])[:MAX_AGENT_OBSERVER_BATCH]:
            if not isinstance(raw_event, dict):
                continue
            event_id = _compact(raw_event.get("event_id"), max_len=160)
            event_type = _compact(raw_event.get("event_type"), max_len=64)
            if not event_id or event_type not in ALLOWED_EVENT_TYPES:
                continue

            existing = (
                await self.session.execute(
                    select(AgentObserverEvent).where(AgentObserverEvent.event_id == event_id).limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                accepted.append(existing)
                continue

            attrs = raw_event.get("attrs_json")
            if not isinstance(attrs, dict):
                attrs = raw_event.get("attrs") if isinstance(raw_event.get("attrs"), dict) else {}
            trace_id = _compact(raw_event.get("trace_id"), max_len=36) or synthetic_agent_observer_trace_id(event_id)
            row = AgentObserverEvent(
                event_id=event_id,
                device_id=safe_device_id,
                install_id=_compact(raw_event.get("install_id"), max_len=128),
                machine_id=_compact(raw_event.get("machine_id"), max_len=128),
                agent_seq=int(raw_event["agent_seq"]) if str(raw_event.get("agent_seq") or "").strip().isdigit() else None,
                trace_id=trace_id,
                operation_id=_compact(raw_event.get("operation_id"), max_len=36),
                ticket_id=_compact(raw_event.get("ticket_id"), max_len=36),
                playbook_run_id=int(raw_event["playbook_run_id"]) if str(raw_event.get("playbook_run_id") or "").strip().isdigit() else None,
                playbook_step_run_id=int(raw_event["playbook_step_run_id"]) if str(raw_event.get("playbook_step_run_id") or "").strip().isdigit() else None,
                root_kind=normalize_agent_observer_root_kind(raw_event.get("root_kind")),
                event_type=event_type,
                severity=normalize_agent_observer_severity(raw_event.get("severity")),
                component=_compact(raw_event.get("component"), max_len=64) or "agent",
                stage=_compact(raw_event.get("stage"), max_len=64),
                status=_compact(raw_event.get("status"), max_len=32),
                tool_name=_compact(raw_event.get("tool_name")),
                module_name=_compact(raw_event.get("module_name"), max_len=128),
                started_at=_parse_datetime(raw_event["started_at"]) if raw_event.get("started_at") else None,
                finished_at=_parse_datetime(raw_event["finished_at"]) if raw_event.get("finished_at") else None,
                duration_ms=int(raw_event["duration_ms"]) if str(raw_event.get("duration_ms") or "").strip().isdigit() else None,
                attrs_json=redact_sensitive_payload(attrs),
                created_at=_parse_datetime(raw_event.get("created_at")),
                received_at=datetime.now(timezone.utc),
            )
            self.session.add(row)
            accepted.append(row)

        await self.session.flush()
        return accepted

    async def list_recent(
        self,
        *,
        device_id: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[AgentObserverEvent]:
        stmt = select(AgentObserverEvent)
        if device_id:
            stmt = stmt.where(AgentObserverEvent.device_id == device_id)
        if trace_id:
            stmt = stmt.where(AgentObserverEvent.trace_id == trace_id)
        stmt = stmt.order_by(AgentObserverEvent.created_at.desc(), AgentObserverEvent.id.desc()).limit(
            max(1, min(int(limit or 100), 500))
        )
        return list((await self.session.execute(stmt)).scalars().all())
