"""Ticket form triggers for diagnostic playbooks."""

from __future__ import annotations

from copy import deepcopy
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.db.models import Playbook, PlaybookVersion
from app.repos import TicketEventsRepo
from app.repos.playbook_repo import PlaybookRepo
from app.services.playbook_engine import start_run


def normalize_form_playbook_triggers(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("playbook_triggers must be an array")
    triggers: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("playbook trigger must be an object")
        event = str(item.get("event") or "ticket_created").strip().lower()
        playbook_key = str(item.get("playbook_key") or "").strip()
        module_kind = str(item.get("module_kind") or "diagnostic").strip().lower()
        if event != "ticket_created":
            raise ValueError("only ticket_created playbook trigger is supported")
        if not playbook_key:
            raise ValueError("playbook trigger requires playbook_key")
        if module_kind not in {"diagnostic", "remediation"}:
            raise ValueError("playbook trigger module_kind must be diagnostic or remediation")
        triggers.append(
            {
                "event": event,
                "playbook_key": playbook_key,
                "module_kind": module_kind,
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return triggers


def collect_ticket_created_playbook_triggers(custom_fields: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(custom_fields, dict):
        return []
    raw = custom_fields.get("request_form_playbook_triggers")
    try:
        triggers = normalize_form_playbook_triggers(raw)
    except ValueError:
        return []
    return [trigger for trigger in triggers if trigger.get("enabled") and trigger.get("event") == "ticket_created"]


def build_ticket_playbook_context(
    *,
    ticket_id: str,
    device_id: str,
    trigger: dict[str, Any],
    custom_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    fields = custom_fields or {}
    return {
        "ticket": {"ticket_id": ticket_id},
        "device": {"device_id": device_id},
        "scenario": {
            "playbook_key": trigger.get("playbook_key"),
            "class": trigger.get("module_kind") or "diagnostic",
            "trigger_event": trigger.get("event") or "ticket_created",
        },
        "facts_package": {
            "request_form_key": fields.get("request_form_key"),
            "request_form_title": fields.get("request_form_title"),
            "request_form_data": deepcopy(fields.get("request_form_data") or {}),
            "request_form_summary": deepcopy(fields.get("request_form_summary") or []),
        },
    }


async def _latest_published_playbook_version(session: Any, playbook_key: str) -> PlaybookVersion | None:
    result = await session.execute(
        select(PlaybookVersion)
        .join(Playbook, PlaybookVersion.playbook_id == Playbook.id)
        .where(
            Playbook.key == playbook_key,
            Playbook.archived.is_(False),
            PlaybookVersion.status == "published",
        )
        .order_by(PlaybookVersion.published_at.desc().nullslast(), PlaybookVersion.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def start_ticket_created_playbooks(
    *,
    session: Any,
    state: Any | None,
    ticket: Any,
    custom_fields: dict[str, Any] | None,
) -> list[int]:
    if state is None or ticket is None:
        return []
    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    device_id = str(getattr(ticket, "device_id", "") or "")
    if not ticket_id or not device_id:
        return []
    triggers = collect_ticket_created_playbook_triggers(custom_fields)
    if not triggers:
        return []

    started: list[int] = []
    ticket_repo = TicketEventsRepo(session)
    for trigger in triggers:
        playbook_key = str(trigger.get("playbook_key") or "")
        version = await _latest_published_playbook_version(session, playbook_key)
        if version is None:
            logger.warning(f"[playbook_form_trigger] published playbook not found key={playbook_key}")
            continue
        context = build_ticket_playbook_context(
            ticket_id=ticket_id,
            device_id=device_id,
            trigger=trigger,
            custom_fields=custom_fields,
        )
        try:
            run_id, _operation_id = await start_run(
                session,
                state,
                playbook_version_id=int(version.id),
                device_id=device_id,
                trigger_type="ticket_created",
                context_json=context,
                idempotency_key=f"ticket:{ticket_id}:playbook:{playbook_key}:ticket_created",
            )
        except Exception as exc:
            logger.warning(
                f"[playbook_form_trigger] failed to start key={playbook_key} ticket_id={ticket_id} err={exc}"
            )
            continue
        started.append(int(run_id))
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="playbook_started",
            payload={
                "playbook_key": playbook_key,
                "playbook_run_id": int(run_id),
                "trigger": "ticket_created",
                "facts_package": context["facts_package"],
            },
            trace_id=str(uuid.uuid4()),
        )
    return started
