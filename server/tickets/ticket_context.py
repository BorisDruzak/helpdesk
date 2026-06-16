"""Server-owned ticket context snapshot for requester and diagnostic target identity."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RegistryPerson
from registry.primary_agent_resolver import PrimaryAgentResolver

TICKET_CONTEXT_SCHEMA = "ticket_context_v1"


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _person_payload(person: RegistryPerson | None, *, fallback_person_id: str | None, actor_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "person_id": getattr(person, "person_id", None) or fallback_person_id,
        "display_name": _clean(getattr(person, "display_name", None)),
        "full_name": _clean(getattr(person, "full_name", None)),
        "email": _clean(getattr(person, "email", None)),
        "department_id": getattr(person, "department_id", None),
        "location_id": getattr(person, "location_id", None),
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    return payload


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


class TicketContextBuilder:
    """Build the stable server-owned ticket context snapshot stored on ticket create."""

    def __init__(self, session: AsyncSession, *, state: Any | None = None):
        self.session = session
        self.state = state

    async def build(
        self,
        *,
        creator_person_id: str,
        creator_actor_id: str | None = None,
        affected_person_id: str | None = None,
        on_behalf_reason: str | None = None,
    ) -> dict[str, Any]:
        creator_id = _clean(creator_person_id)
        if creator_id is None:
            raise ValueError("creator_person_id is required")
        affected_id = _clean(affected_person_id) or creator_id
        created_on_behalf = affected_id != creator_id

        creator = await self.session.get(RegistryPerson, creator_id)
        affected = await self.session.get(RegistryPerson, affected_id)
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

        context: dict[str, Any] = {
            "schema": TICKET_CONTEXT_SCHEMA,
            "created_on_behalf": created_on_behalf,
            "creator": _person_payload(creator, fallback_person_id=creator_id, actor_id=_clean(creator_actor_id)),
            "affected": _person_payload(affected, fallback_person_id=affected_id),
            "target_device": target_device,
            "diagnostic_target_source": _target_source(
                resolved=is_resolved,
                created_on_behalf=created_on_behalf,
                reason_code=reason_code,
            ),
        }
        reason = _clean(on_behalf_reason)
        if reason:
            context["on_behalf_reason"] = reason
        return context

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
