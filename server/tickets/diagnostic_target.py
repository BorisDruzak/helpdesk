"""Resolve the device that diagnostics must target for a ticket."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class TicketDiagnosticTarget:
    target_device_id: str | None
    fallback_device_id: str | None
    source: str
    agent_status: str | None = None
    reason_code: str | None = None
    created_on_behalf: bool = False
    creator_person_id: str | None = None
    affected_person_id: str | None = None
    affected_display_name: str | None = None

    @property
    def dispatch_device_id(self) -> str | None:
        return self.target_device_id or (self.fallback_device_id if self.source == "legacy_ticket_device" else None)

    @property
    def skip_reason(self) -> str | None:
        if self.dispatch_device_id:
            return None
        if self.reason_code == "ambiguous_primary_device" or self.source == "ambiguous_primary_agent":
            return "target_device_ambiguous"
        return "target_device_missing"

    def payload(self) -> dict[str, Any]:
        return {
            "target_device_id": self.dispatch_device_id,
            "legacy_ticket_device_id": self.fallback_device_id,
            "source": self.source,
            "agent_status": self.agent_status,
            "reason_code": self.reason_code,
            "created_on_behalf": self.created_on_behalf,
            "creator_person_id": self.creator_person_id,
            "affected_person_id": self.affected_person_id,
            "affected_display_name": self.affected_display_name,
        }


def resolve_ticket_diagnostic_target(ticket: Any, custom_fields: dict[str, Any] | None = None) -> TicketDiagnosticTarget:
    fields = custom_fields if isinstance(custom_fields, dict) else _dict(getattr(ticket, "custom_fields", None))
    context = _dict(fields.get("ticket_context"))
    target_device = _dict(context.get("target_device"))
    affected = _dict(context.get("affected"))
    creator = _dict(context.get("creator"))

    flat_target = _clean(fields.get("target_device_id"))
    context_target = _clean(target_device.get("device_id"))
    fallback_device_id = _clean(getattr(ticket, "device_id", None))
    has_context = bool(context or flat_target or fields.get("diagnostic_target_source") or fields.get("target_agent_status"))
    source = (
        _clean(fields.get("diagnostic_target_source"))
        or _clean(context.get("diagnostic_target_source"))
        or ("legacy_ticket_device" if fallback_device_id and not has_context else "unknown")
    )
    agent_status = _clean(fields.get("target_agent_status")) or _clean(target_device.get("agent_status"))
    reason_code = _clean(target_device.get("reason_code"))

    return TicketDiagnosticTarget(
        target_device_id=flat_target or context_target,
        fallback_device_id=fallback_device_id,
        source=source,
        agent_status=agent_status,
        reason_code=reason_code,
        created_on_behalf=bool(fields.get("created_on_behalf") or context.get("created_on_behalf")),
        creator_person_id=_clean(fields.get("creator_person_id")) or _clean(creator.get("person_id")),
        affected_person_id=_clean(fields.get("affected_person_id")) or _clean(affected.get("person_id")),
        affected_display_name=_clean(affected.get("display_name")),
    )
