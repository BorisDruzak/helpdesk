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
from tickets.diagnostic_target import resolve_ticket_diagnostic_target
from tickets.diagnostic_policy import (
    HIGH_RISK_TOOL_LEVELS,
    collect_diagnostic_policy_auto_run_triggers,
    has_granted_high_risk_tool_consent,
)


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
    diagnostic_target = trigger.get("diagnostic_target") if isinstance(trigger.get("diagnostic_target"), dict) else {}
    return {
        "ticket": {"ticket_id": ticket_id},
        "device": {"device_id": device_id},
        "diagnostic_target": deepcopy(diagnostic_target),
        "scenario": {
            "playbook_key": trigger.get("playbook_key"),
            "class": trigger.get("module_kind") or "diagnostic",
            "trigger_event": trigger.get("event") or "ticket_created",
            "trigger_type": trigger.get("trigger_type") or trigger.get("event") or "ticket_created",
            "source": trigger.get("source") or "request_form",
        },
        "facts_package": {
            "request_form_key": fields.get("request_form_key"),
            "request_form_title": fields.get("request_form_title"),
            "request_form_data": deepcopy(fields.get("request_form_data") or {}),
            "request_form_summary": deepcopy(fields.get("request_form_summary") or []),
        },
        "diagnostic_policy": deepcopy(trigger.get("diagnostic_policy") or {}),
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


def _required_high_risk_tools(manifest: Any) -> list[dict[str, str]]:
    if not isinstance(manifest, dict):
        return []

    candidates: list[dict[str, Any]] = []
    for item in manifest.get("required_tools") or []:
        if isinstance(item, dict):
            candidates.append(item)
    for block in manifest.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        candidates.append(block)
        tool_manifest = block.get("tool_manifest")
        if isinstance(tool_manifest, dict):
            candidates.append({"tool": block.get("tool"), **tool_manifest})

    high_risk: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        risk_level = str(item.get("risk_level") or "").strip().lower()
        if risk_level not in HIGH_RISK_TOOL_LEVELS:
            continue
        tool_name = str(item.get("tool") or item.get("tool_name") or item.get("id") or "").strip()
        key = (tool_name, risk_level)
        if key in seen:
            continue
        seen.add(key)
        high_risk.append({"tool": tool_name, "risk_level": risk_level})
    return high_risk


def _requires_high_risk_consent(trigger: dict[str, Any]) -> bool:
    if trigger.get("source") != "diagnostic_policy":
        return False
    policy = trigger.get("diagnostic_policy")
    if not isinstance(policy, dict):
        return False
    if bool(policy.get("high_risk_consent_required")):
        return True
    consent = policy.get("consent")
    return isinstance(consent, dict) and bool(consent.get("required_for_high_risk_tools"))


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
    target = resolve_ticket_diagnostic_target(ticket, custom_fields)
    fallback_device_id = str(getattr(ticket, "device_id", "") or "")
    device_id = target.dispatch_device_id or ""
    if not ticket_id:
        return []
    started: list[int] = []
    ticket_repo = TicketEventsRepo(session)
    triggers = collect_ticket_created_playbook_triggers(custom_fields)
    policy_triggers, policy_skips = collect_diagnostic_policy_auto_run_triggers(
        ticket=ticket,
        custom_fields=custom_fields,
        state=state,
    )
    if policy_skips:
        fields = dict(custom_fields or getattr(ticket, "custom_fields", None) or {})
        diagnostics = dict(fields.get("diagnostics") if isinstance(fields.get("diagnostics"), dict) else {})
        existing_skips = diagnostics.get("autorun_skips")
        autorun_skips = list(existing_skips) if isinstance(existing_skips, list) else []
        for skip in policy_skips:
            autorun_skips.append(
                {
                    "playbook_key": skip.get("playbook_key"),
                    "reason": skip.get("reason"),
                    "source": skip.get("source") or "diagnostic_policy",
                    "diagnostic_target": deepcopy(skip.get("diagnostic_target") or target.payload()),
                }
            )
        diagnostics["autorun_skips"] = autorun_skips[-20:]
        diagnostics["last_autorun_skip_reason"] = policy_skips[-1].get("reason")
        diagnostics["diagnostic_target"] = deepcopy(policy_skips[-1].get("diagnostic_target") or target.payload())
        fields["diagnostics"] = diagnostics
        await ticket_repo.update_ticket(ticket_id, custom_fields=fields)
        custom_fields = fields

    for skip in policy_skips:
        skip_target = skip.get("diagnostic_target") if isinstance(skip.get("diagnostic_target"), dict) else target.payload()
        event_device_id = str(skip_target.get("target_device_id") or fallback_device_id or device_id)
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=event_device_id,
            agent_seq=None,
            event_type="diagnostic_autorun_skipped",
            payload={
                "trigger": "diagnostic_policy_auto_run",
                **skip,
            },
            trace_id=str(uuid.uuid4()),
        )
    triggers.extend(policy_triggers)
    if not device_id and triggers:
        skip_reason = target.skip_reason or "target_device_missing"
        for trigger in triggers:
            await ticket_repo.add_event(
                ticket_id=ticket_id,
                device_id=fallback_device_id,
                agent_seq=None,
                event_type="diagnostic_autorun_skipped",
                payload={
                    "trigger": trigger.get("trigger_type") or trigger.get("event") or "ticket_created",
                    "playbook_key": trigger.get("playbook_key"),
                    "reason": skip_reason,
                    "source": trigger.get("source") or "request_form",
                    "diagnostic_target": target.payload(),
                },
                trace_id=str(uuid.uuid4()),
            )
        return []
    if not triggers:
        return []

    for trigger in triggers:
        playbook_key = str(trigger.get("playbook_key") or "")
        trigger_target = trigger.get("diagnostic_target") if isinstance(trigger.get("diagnostic_target"), dict) else target.payload()
        trigger_device_id = str(trigger_target.get("target_device_id") or device_id)
        version = await _latest_published_playbook_version(session, playbook_key)
        if version is None:
            logger.warning(f"[playbook_form_trigger] published playbook not found key={playbook_key}")
            await ticket_repo.add_event(
                ticket_id=ticket_id,
                device_id=trigger_device_id,
                agent_seq=None,
                event_type="diagnostic_autorun_skipped",
                payload={
                    "trigger": trigger.get("trigger_type") or trigger.get("event") or "ticket_created",
                    "playbook_key": playbook_key,
                    "reason": "playbook_not_published",
                    "source": trigger.get("source") or "request_form",
                    "diagnostic_target": trigger_target,
                },
                trace_id=str(uuid.uuid4()),
            )
            continue
        high_risk_tools = _required_high_risk_tools(version.manifest_json)
        if (
            high_risk_tools
            and _requires_high_risk_consent(trigger)
            and not has_granted_high_risk_tool_consent(custom_fields or {})
        ):
            await ticket_repo.add_event(
                ticket_id=ticket_id,
                device_id=trigger_device_id,
                agent_seq=None,
                event_type="diagnostic_autorun_skipped",
                payload={
                    "trigger": "diagnostic_policy_auto_run",
                    "playbook_key": playbook_key,
                    "reason": "high_risk_consent_required",
                    "priority_class": (custom_fields or {}).get("priority_class"),
                    "source": "diagnostic_policy",
                    "high_risk_tools": [item["tool"] for item in high_risk_tools],
                    "high_risk_levels": [item["risk_level"] for item in high_risk_tools],
                    "diagnostic_target": trigger_target,
                },
                trace_id=str(uuid.uuid4()),
            )
            continue
        context = build_ticket_playbook_context(
            ticket_id=ticket_id,
            device_id=trigger_device_id,
            trigger=trigger,
            custom_fields=custom_fields,
        )
        trigger_type = str(trigger.get("trigger_type") or trigger.get("event") or "ticket_created").strip()
        idempotency_key = (
            f"ticket:{ticket_id}:playbook:{playbook_key}:diagnostic_policy_auto_run"
            if trigger.get("source") == "diagnostic_policy"
            else f"ticket:{ticket_id}:playbook:{playbook_key}:ticket_created"
        )
        try:
            run_id, _operation_id = await start_run(
                session,
                state,
                playbook_version_id=int(version.id),
                device_id=trigger_device_id,
                trigger_type=trigger_type,
                context_json=context,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            logger.warning(
                f"[playbook_form_trigger] failed to start key={playbook_key} ticket_id={ticket_id} err={exc}"
            )
            continue
        started.append(int(run_id))
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=trigger_device_id,
            agent_seq=None,
            event_type="playbook_started",
            payload={
                "playbook_key": playbook_key,
                "playbook_run_id": int(run_id),
                "trigger": trigger_type,
                "source": trigger.get("source") or "request_form",
                "facts_package": context["facts_package"],
                "diagnostic_policy": context["diagnostic_policy"],
                "diagnostic_target": trigger_target,
            },
            trace_id=str(uuid.uuid4()),
        )
    return started
