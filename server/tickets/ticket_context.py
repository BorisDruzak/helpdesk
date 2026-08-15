"""Server-owned ticket context snapshot for requester and diagnostic target identity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB, array
from sqlalchemy.ext.asyncio import AsyncSession

from domain_ports import (
    DomainPortContainer,
    PersonRef,
    RegistryNotFound,
    RegistryPort,
    RegistryUnavailable,
    RequesterRef,
    RequesterSnapshot,
    TicketParticipantProjection,
)
from registry.primary_agent_resolver import PrimaryAgentResolver

TICKET_CONTEXT_SCHEMA = "ticket_context_v1"
REQUESTER_HIDDEN_FIELDS = (
    "creator.person_id",
    "affected.person_id",
    "target_device.device_id",
    "target_device.binding_id",
    "diagnostic_target.device_id",
    "diagnostic_target.binding_id",
    "diagnostic_target.source",
    "policy_refs",
    "trace_id",
    "operation_id",
)


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _person_payload(
    person: TicketParticipantProjection,
    *,
    actor_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "person_id": person.person.external_id,
        "display_name": person.display_name,
        "full_name": person.full_name,
        "email": person.email,
        "department_id": person.department.external_id if person.department is not None else None,
        "location_id": person.location.external_id if person.location is not None else None,
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    return payload


def requester_reference_snapshot_from_person(
    person: object | None,
) -> tuple[RequesterRef | None, RequesterSnapshot | None]:
    """Build neutral requester persistence only from a server-loaded person."""

    external_ref = _clean(getattr(person, "person_id", None))
    if external_ref is None:
        return None, None
    requester_ref = RequesterRef(external_id=external_ref)
    display_name = _clean(getattr(person, "display_name", None)) or _clean(
        getattr(person, "full_name", None)
    )
    if display_name is None:
        raise ValueError("verified requester requires a non-empty display name snapshot")
    snapshot = RequesterSnapshot(
        person=PersonRef(external_id=external_ref),
        display_name=display_name,
    )
    return requester_ref, snapshot


def requester_reference_snapshot_from_record(
    row: Any,
) -> tuple[RequesterRef | None, RequesterSnapshot | None]:
    """Validate neutral requester values already persisted on a Helpdesk row."""

    external_ref = getattr(row, "requester_external_ref", None)
    raw_snapshot = getattr(row, "requester_snapshot_json", None)
    if external_ref is None and raw_snapshot is None:
        return None, None
    if external_ref is None or raw_snapshot is None:
        raise ValueError("requester external ref and snapshot must both be set")
    requester_ref = RequesterRef(external_id=external_ref)
    snapshot = RequesterSnapshot.model_validate(raw_snapshot) if raw_snapshot is not None else None
    if snapshot is not None and snapshot.person.external_id != requester_ref.external_id:
        raise ValueError("requester snapshot person does not match requester external ref")
    return requester_ref, snapshot


def requester_neutral_scope_clause(model: Any):
    snapshot = model.requester_snapshot_json
    person = snapshot["person"]
    return and_(
        model.requester_external_ref.is_not(None),
        func.length(model.requester_external_ref).between(1, 512),
        snapshot.is_not(None),
        snapshot != JSON.NULL,
        func.jsonb_typeof(snapshot) == "object",
        snapshot.op("-")(array(["person", "display_name"])) == cast({}, JSONB),
        func.jsonb_typeof(person) == "object",
        person.op("-")(array(["external_id"])) == cast({}, JSONB),
        func.jsonb_typeof(person["external_id"]) == "string",
        person["external_id"].astext == model.requester_external_ref,
        func.jsonb_typeof(snapshot["display_name"]) == "string",
        func.length(func.btrim(snapshot["display_name"].astext)).between(1, 256),
    )


def requester_legacy_scope_clause(model: Any):
    return and_(
        model.requester_external_ref.is_(None),
        or_(
            model.requester_snapshot_json.is_(None),
            model.requester_snapshot_json == JSON.NULL,
        ),
    )


def _target_source(*, resolved: bool, created_on_behalf: bool, reason_code: str | None) -> str:
    if resolved:
        return "affected_user_primary_agent" if created_on_behalf else "creator_primary_agent"
    if reason_code == "ambiguous_primary_device":
        return "ambiguous_primary_agent"
    return "no_primary_agent"


def _unresolved_agent_status(reason_code: str | None) -> str:
    if reason_code == "ambiguous_primary_device":
        return "ambiguous"
    return "missing"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _diagnostic_target_payload(target_device: dict[str, Any], *, source: str) -> dict[str, Any]:
    payload: dict[str, Any] = dict(target_device)
    payload["source"] = source
    return payload


def _target_label(target: dict[str, Any]) -> str | None:
    return _clean(target.get("hostname")) or _clean(target.get("label")) or _clean(target.get("asset_name"))


def _target_available(target: dict[str, Any]) -> bool:
    if not _clean(target.get("device_id")):
        return False
    status = _clean(target.get("agent_status"))
    if status in {"missing", "ambiguous", "offline"}:
        return False
    if target.get("online") is False:
        return False
    return True


def build_ticket_context_v1(
    *,
    creator: dict[str, Any],
    affected: dict[str, Any],
    diagnostic_target: dict[str, Any],
    requester_context: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    policy_refs: dict[str, Any] | None = None,
    created_on_behalf: bool | None = None,
    on_behalf_reason: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the canonical ticket_context_v1 snapshot while keeping legacy aliases."""

    source = _clean(diagnostic_target.get("source")) or "unknown"
    target_device = {
        key: diagnostic_target.get(key)
        for key in (
            "device_id",
            "binding_id",
            "asset_id",
            "agent_status",
            "online",
            "hostname",
            "agent_version",
            "relationship_type",
            "last_seen_at",
            "last_handshake_at",
            "reason_code",
            "candidate_count",
            "candidates",
        )
        if key in diagnostic_target
    }
    is_on_behalf = bool(
        created_on_behalf
        if created_on_behalf is not None
        else _clean(creator.get("person_id")) != _clean(affected.get("person_id"))
    )
    reason = _clean(on_behalf_reason)

    context: dict[str, Any] = {
        "schema": TICKET_CONTEXT_SCHEMA,
        "created_at": created_at or _utc_now_iso(),
        "created_on_behalf": is_on_behalf,
        "creator": dict(creator),
        "affected": dict(affected),
        "on_behalf": {
            "enabled": is_on_behalf,
            "reason": reason,
        },
        "requester_context": dict(requester_context or {}),
        "target_device": target_device,
        "diagnostic_target": {
            **diagnostic_target,
            "source": source,
        },
        "diagnostic_target_source": source,
        "form": dict(form or {}),
        "policy_refs": dict(policy_refs or {}),
        "redaction": {
            "requester_hidden_fields": list(REQUESTER_HIDDEN_FIELDS),
            "requester_projection": "project_requester_ticket_context",
            "history_projection": "redact_ticket_context_for_history",
        },
    }
    if reason:
        context["on_behalf_reason"] = reason
    return context


def validate_ticket_context_v1(context: dict[str, Any] | None) -> list[str]:
    if not isinstance(context, dict):
        return ["context must be an object"]
    errors: list[str] = []
    if context.get("schema") != TICKET_CONTEXT_SCHEMA:
        errors.append("schema must be ticket_context_v1")
    if not _clean(context.get("created_at")):
        errors.append("created_at is required")
    creator = _dict(context.get("creator"))
    affected = _dict(context.get("affected"))
    if not _clean(creator.get("person_id")):
        errors.append("creator.person_id is required")
    if not _clean(affected.get("person_id")):
        errors.append("affected.person_id is required")
    for key in ("on_behalf", "requester_context", "diagnostic_target", "form", "policy_refs", "redaction"):
        if not isinstance(context.get(key), dict):
            errors.append(f"{key} section is required")
    diagnostic_target = _dict(context.get("diagnostic_target"))
    if diagnostic_target and not _clean(diagnostic_target.get("source")):
        errors.append("diagnostic_target.source is required")
    return errors


def project_requester_ticket_context(
    context: dict[str, Any] | None,
    *,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = _dict(context)
    affected = _dict(raw.get("affected"))
    target = _dict(raw.get("diagnostic_target")) or _dict(raw.get("target_device"))
    on_behalf = _dict(raw.get("on_behalf"))
    source = _clean(target.get("source")) or _clean(raw.get("diagnostic_target_source"))
    reason_code = _clean(target.get("reason_code"))
    target_label = _target_label(target)
    status = _clean(target.get("agent_status"))

    return {
        "schema": raw.get("schema") or TICKET_CONTEXT_SCHEMA,
        "summary": {
            "created_on_behalf": bool(raw.get("created_on_behalf") or on_behalf.get("enabled")),
            "affected": _clean(affected.get("display_name")) or _clean(affected.get("full_name")) or "Сотрудник",
            "reason": _clean(on_behalf.get("reason")) or _clean(raw.get("on_behalf_reason")),
        },
        "diagnostic_target": {
            "label": target_label or "Основное устройство не определено",
            "available": _target_available(target),
            "status": status,
            "reason": reason_code,
            "text": _requester_target_text(source=source, status=status, reason_code=reason_code),
        },
        "form": _requester_form_projection(_dict(raw.get("form"))),
    }


def _requester_target_text(*, source: str | None, status: str | None, reason_code: str | None) -> str:
    if source == "ambiguous_primary_agent" or status == "ambiguous":
        return "Основное устройство нужно уточнить специалисту поддержки."
    if source == "no_primary_agent" or status == "missing":
        return "Основное устройство пока не найдено; обращение попадет в поддержку."
    if status == "offline":
        return "Основное устройство найдено, но сейчас не в сети."
    return "Диагностическое устройство определено сервером."


def _requester_form_projection(form: dict[str, Any]) -> dict[str, Any]:
    return {
        key: form.get(key)
        for key in ("key", "title", "service_title", "offering_title", "summary")
        if form.get(key) not in (None, "")
    }


def project_support_ticket_context(
    context: dict[str, Any] | None,
    *,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = _dict(context)
    target = _dict(raw.get("diagnostic_target")) or _dict(raw.get("target_device"))
    return {
        "schema": raw.get("schema"),
        "created_at": raw.get("created_at"),
        "creator": _dict(raw.get("creator")),
        "affected": _dict(raw.get("affected")),
        "created_on_behalf": bool(raw.get("created_on_behalf")),
        "on_behalf": _dict(raw.get("on_behalf")),
        "on_behalf_reason": raw.get("on_behalf_reason") or _dict(raw.get("on_behalf")).get("reason"),
        "diagnostic_target": target,
        "diagnostic_target_source": target.get("source") or raw.get("diagnostic_target_source"),
        "form": _dict(raw.get("form")),
        "policy_refs": _dict(raw.get("policy_refs")),
        "target_available": _target_available(target),
        "evidence_codes": _evidence_codes(target),
    }


def redact_ticket_context_for_requester(context: dict[str, Any] | None) -> dict[str, Any]:
    return project_requester_ticket_context(context, actor_context=None)


def redact_ticket_context_for_history(context: dict[str, Any] | None) -> dict[str, Any]:
    raw = _dict(context)
    target = _dict(raw.get("diagnostic_target")) or _dict(raw.get("target_device"))
    return {
        "schema": raw.get("schema"),
        "created_on_behalf": bool(raw.get("created_on_behalf")),
        "affected_display_name": _dict(raw.get("affected")).get("display_name"),
        "diagnostic_target_source": target.get("source") or raw.get("diagnostic_target_source"),
        "target_agent_status": target.get("agent_status"),
        "target_available": _target_available(target),
        "evidence_codes": _evidence_codes(target),
        "form": _requester_form_projection(_dict(raw.get("form"))),
    }


def _ticket_context_from_input(value: Any, custom_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(custom_fields, dict):
        return _dict(custom_fields.get("ticket_context"))
    if isinstance(value, dict):
        if isinstance(value.get("ticket_context"), dict):
            return value["ticket_context"]
        return value
    fields = _dict(getattr(value, "custom_fields", None))
    return _dict(fields.get("ticket_context"))


def resolve_diagnostic_target_from_ticket_context(
    ticket_or_context: Any,
    custom_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = _ticket_context_from_input(ticket_or_context, custom_fields)
    target = _dict(raw.get("diagnostic_target")) or _dict(raw.get("target_device"))
    return {
        "target_device_id": _clean(target.get("device_id")),
        "source": _clean(target.get("source")) or _clean(raw.get("diagnostic_target_source")) or "unknown",
        "agent_status": _clean(target.get("agent_status")),
        "reason_code": _clean(target.get("reason_code")),
        "target_available": _target_available(target),
        "evidence_codes": _evidence_codes(target),
    }


def ticket_context_resolved_event_payload(context: dict[str, Any]) -> dict[str, Any]:
    target = resolve_diagnostic_target_from_ticket_context(context)
    return {
        "schema": context.get("schema"),
        "created_on_behalf": bool(context.get("created_on_behalf")),
        "diagnostic_target_source": target["source"],
        "target_available": target["target_available"],
        "evidence_codes": target["evidence_codes"],
        "policy_sources": _dict(context.get("policy_refs")),
        "visibility": "internal/support",
    }


def _evidence_codes(target: dict[str, Any]) -> list[str]:
    if _target_available(target):
        return []
    codes: list[str] = []
    reason_code = _clean(target.get("reason_code"))
    if reason_code:
        codes.append(reason_code)
    status = _clean(target.get("agent_status"))
    if status in {"missing", "ambiguous", "offline"} and status not in codes:
        codes.append(f"target_agent_{status}")
    return codes


class TicketContextBuilder:
    """Build the stable server-owned ticket context snapshot stored on ticket create."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        state: Any | None = None,
        registry_port: RegistryPort | None = None,
    ):
        self.session = session
        self.state = state
        self.registry_port = registry_port or DomainPortContainer.from_config(
            registry_session=session
        ).registry

    async def requester_reference_snapshot(
        self,
        person_id: str | None,
    ) -> tuple[RequesterRef | None, RequesterSnapshot | None]:
        verified_person_id = _clean(person_id)
        if verified_person_id is None:
            return None, None
        outcome = await self.registry_port.requester_snapshot(
            PersonRef(external_id=verified_person_id)
        )
        if isinstance(outcome, RequesterSnapshot):
            if outcome.person.external_id != verified_person_id:
                raise ValueError("verified requester Registry projection is invalid")
            return RequesterRef(external_id=outcome.person.external_id), outcome
        if isinstance(outcome, RegistryNotFound):
            raise ValueError(f"verified requester person not found: {outcome.code}")
        if isinstance(outcome, RegistryUnavailable):
            raise ValueError(f"verified requester Registry read unavailable: {outcome.code}")
        raise ValueError("verified requester Registry projection is invalid")

    async def build(
        self,
        *,
        creator_person_id: str,
        creator_actor_id: str | None = None,
        affected_person_id: str | None = None,
        on_behalf_reason: str | None = None,
        requester_context: dict[str, Any] | None = None,
        form: dict[str, Any] | None = None,
        policy_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        creator_id = _clean(creator_person_id)
        if creator_id is None:
            raise ValueError("creator_person_id is required")
        affected_id = _clean(affected_person_id) or creator_id
        created_on_behalf = affected_id != creator_id

        creator = await self._ticket_participant(creator_id)
        affected = creator if affected_id == creator_id else await self._ticket_participant(affected_id)
        resolved = await PrimaryAgentResolver(self.session, state=self.state).resolve_for_person(affected_id)
        reason_code = _clean(resolved.get("reason_code")) if isinstance(resolved, dict) else None
        is_resolved = bool(resolved.get("resolved")) if isinstance(resolved, dict) else False

        target_device: dict[str, Any]
        if is_resolved:
            target_device = {
                "device_id": resolved.get("device_id"),
                "binding_id": resolved.get("binding_id"),
                "asset_id": resolved.get("asset_id"),
                "agent_status": _clean(resolved.get("connection_state")) or "unknown",
                "online": resolved.get("online"),
                "hostname": _clean(resolved.get("hostname")),
                "agent_version": _clean(resolved.get("agent_version")),
                "relationship_type": _clean(resolved.get("relationship_type")),
                "last_seen_at": resolved.get("last_seen_at"),
                "last_handshake_at": resolved.get("last_handshake_at"),
                "reason_code": reason_code,
            }
        else:
            target_device = {
                "device_id": None,
                "binding_id": None,
                "agent_status": _unresolved_agent_status(reason_code),
                "reason_code": reason_code,
                "candidate_count": int(resolved.get("candidate_count") or 0) if isinstance(resolved, dict) else 0,
            }
            candidates = resolved.get("candidates") if isinstance(resolved, dict) else None
            if isinstance(candidates, list) and candidates:
                target_device["candidates"] = [
                    {
                        "device_id": item.get("device_id"),
                        "binding_id": item.get("binding_id"),
                        "relationship_type": item.get("relationship_type"),
                    }
                    for item in candidates
                    if isinstance(item, dict)
                ]

        source = _target_source(
            resolved=is_resolved,
            created_on_behalf=created_on_behalf,
            reason_code=reason_code,
        )
        reason = _clean(on_behalf_reason)
        return build_ticket_context_v1(
            creator=_person_payload(creator, actor_id=_clean(creator_actor_id)),
            affected=_person_payload(affected),
            created_on_behalf=created_on_behalf,
            on_behalf_reason=reason,
            requester_context=requester_context or {},
            diagnostic_target=_diagnostic_target_payload(target_device, source=source),
            form=form or {},
            policy_refs=policy_refs or {},
        )

    async def _ticket_participant(self, person_id: str) -> TicketParticipantProjection:
        outcome = await self.registry_port.ticket_participant(PersonRef(external_id=person_id))
        if isinstance(outcome, TicketParticipantProjection):
            if outcome.person.external_id != person_id:
                raise ValueError("ticket participant Registry projection is invalid")
            return outcome
        if isinstance(outcome, RegistryNotFound):
            raise ValueError(f"ticket participant person not found: {outcome.code}")
        if isinstance(outcome, RegistryUnavailable):
            raise ValueError(f"ticket participant Registry read unavailable: {outcome.code}")
        raise ValueError("ticket participant Registry projection is invalid")

    @staticmethod
    def custom_fields(context: dict[str, Any]) -> dict[str, Any]:
        creator = context.get("creator") if isinstance(context.get("creator"), dict) else {}
        affected = context.get("affected") if isinstance(context.get("affected"), dict) else {}
        target = context.get("target_device") if isinstance(context.get("target_device"), dict) else {}

        fields: dict[str, Any] = {
            "ticket_context": context,
            "created_on_behalf": bool(context.get("created_on_behalf")),
            "creator_person_id": creator.get("person_id"),
            "creator_actor_id": creator.get("actor_id"),
            "creator_display_name": creator.get("display_name"),
            "affected_person_id": affected.get("person_id"),
            "affected_display_name": affected.get("display_name"),
            "affected_department_id": affected.get("department_id"),
            "affected_location_id": affected.get("location_id"),
            "target_device_id": target.get("device_id"),
            "target_binding_id": target.get("binding_id"),
            "target_agent_status": target.get("agent_status"),
            "target_hostname": target.get("hostname"),
            "target_agent_version": target.get("agent_version"),
            "diagnostic_target_source": context.get("diagnostic_target_source"),
        }
        if "asset_id" in target:
            fields["target_asset_id"] = target.get("asset_id")
        if target.get("reason_code"):
            fields["diagnostic_target_reason_code"] = target.get("reason_code")
        if "candidate_count" in target:
            fields["diagnostic_target_candidate_count"] = target.get("candidate_count")
        if context.get("on_behalf_reason"):
            fields["on_behalf_reason"] = context.get("on_behalf_reason")
        return fields
