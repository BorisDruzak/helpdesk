"""
Stage 11: OLA (Operational Level Agreement) — queue-level ack/processing таймеры.

Старт OLA: при создании тикета и при смене очереди.
ack: закрывается при назначении assignee_id.
processing: закрывается при смене очереди (handoff) или при переходе в Resolved/Closed.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketQueueOlaTarget
from config import TICKET_OLA_ENABLED
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.statuses import TERMINAL_STATUSES, WAITING_STATUSES, extract_priority_class


def _get_request_template(custom_fields: object) -> dict:
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    return request_template if isinstance(request_template, dict) else {}


def _ola_policy_metadata(policy: dict | None) -> dict[str, Any]:
    if not isinstance(policy, dict):
        return {}
    code = policy.get("code") or policy.get("policy_code") or policy.get("ola_policy_code") or policy.get("id")
    result: dict[str, Any] = {}
    if code is not None:
        result["code"] = str(code)
    if policy.get("version") is not None:
        result["version"] = str(policy.get("version"))
    result["source"] = str(policy.get("source") or policy.get("scope_level") or "request_template")
    return result


def _breach_actions(policy: dict | None) -> dict[str, Any]:
    actions = policy.get("breach_actions") if isinstance(policy, dict) else {}
    return dict(actions) if isinstance(actions, dict) else {}


def _normalized_status(value: Any) -> str:
    return str(value or "").strip().lower()


_STATUS_ALIASES = {
    "waiting_user": "waiting_on_user",
    "wait_user": "waiting_on_user",
    "waiting_approval": "waiting_on_approval",
    "waiting_internal": "waiting_on_internal_team",
    "waiting_internal_team": "waiting_on_internal_team",
    "waiting_vendor": "waiting_on_vendor",
}

_EVENT_STATUS_ALIASES = {
    "ticket_resolved": {"resolved"},
    "ticket_closed": {"closed"},
    "ticket_terminal": set(TERMINAL_STATUSES) | {"resolved", "closed"},
}


def _ticket_custom_value(ticket: Ticket, key: str) -> Any:
    if hasattr(ticket, key):
        value = getattr(ticket, key)
        if value is not None:
            return value
    current: Any = getattr(ticket, "custom_fields", None) or {}
    for part in str(key).split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _condition_matches(
    condition: Any,
    *,
    ticket: Ticket,
    trigger: str | None = None,
    status: str | None = None,
) -> bool:
    trigger_value = str(trigger or "").strip()
    current_status = _normalized_status(status if status is not None else getattr(ticket, "status", None))
    if isinstance(condition, str):
        raw = condition.strip()
        lowered = raw.lower()
        if trigger_value and lowered == trigger_value.lower():
            return True
        if lowered == current_status:
            return True
        status_alias = _STATUS_ALIASES.get(lowered)
        if status_alias and current_status == status_alias:
            return True
        event_statuses = _EVENT_STATUS_ALIASES.get(lowered)
        if event_statuses and current_status in event_statuses:
            return True
        if lowered.startswith("status in"):
            _, _, tail = lowered.partition("in")
            values = [item.strip(" '\"\t\r\n") for item in tail.strip().strip("[]()").split(",")]
            return current_status in {item for item in values if item}
        if lowered.startswith("status ="):
            return current_status == lowered.split("=", 1)[1].strip(" '\"")
        return False
    if not isinstance(condition, dict):
        return False

    event_name = condition.get("event") or condition.get("trigger")
    if event_name is not None and str(event_name).strip().lower() != trigger_value.lower():
        return False
    if condition.get("status") is not None and current_status != _normalized_status(condition.get("status")):
        return False
    if condition.get("status_equals") is not None and current_status != _normalized_status(condition.get("status_equals")):
        return False
    if condition.get("status_in") is not None:
        allowed = {_normalized_status(item) for item in condition.get("status_in") or []}
        if current_status not in allowed:
            return False

    known_keys = {"event", "trigger", "status", "status_equals", "status_in"}
    for key, expected in condition.items():
        if key in known_keys:
            continue
        if _ticket_custom_value(ticket, key) != expected:
            return False
    return True


def _conditions_allow(
    conditions: Any,
    *,
    ticket: Ticket,
    trigger: str | None = None,
    status: str | None = None,
    default: bool,
) -> bool:
    if not conditions:
        return default
    if not isinstance(conditions, list):
        conditions = [conditions]
    return any(_condition_matches(item, ticket=ticket, trigger=trigger, status=status) for item in conditions)


def _stop_conditions_for(policy: dict | None, kind: str) -> Any:
    if not isinstance(policy, dict):
        return None
    raw = policy.get("stop_conditions")
    if isinstance(raw, dict):
        return raw.get(kind)
    if kind == "processing":
        return raw
    return None


def _duration_to_minutes(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw.isdigit():
            return int(raw)
        multiplier = 1
        if raw.endswith("m"):
            raw = raw[:-1]
        elif raw.endswith("h"):
            raw = raw[:-1]
            multiplier = 60
        elif raw.endswith("d"):
            raw = raw[:-1]
            multiplier = 60 * 24
        try:
            return int(float(raw) * multiplier)
        except ValueError:
            return None
    return None


def _target_from_policy_map(target_map: object, priority: str) -> int | None:
    if not isinstance(target_map, dict):
        return None
    candidates = [priority]
    if priority != "P3":
        candidates.append("P3")
    for key in candidates:
        value = target_map.get(key)
        minutes = _duration_to_minutes(value)
        if minutes is not None:
            return minutes
    return None


def _targets_from_ola_policy(policy: dict, priority: str) -> Optional[tuple[int, int]]:
    if not isinstance(policy, dict):
        return None
    targets = policy.get("targets") if isinstance(policy.get("targets"), dict) else policy
    if not isinstance(targets, dict):
        return None
    ack_min = _target_from_policy_map(targets.get("ack"), priority)
    processing_min = _target_from_policy_map(targets.get("processing"), priority)
    if ack_min is None or processing_min is None:
        return None
    return ack_min, processing_min


def _get_template_ola_targets(ticket: Ticket, priority: str) -> Optional[tuple[int, int]]:
    request_template = _get_request_template(getattr(ticket, "custom_fields", None))
    policy = request_template.get("ola_policy") or {}
    return _targets_from_ola_policy(policy, priority)


async def _get_ola_policy(session: AsyncSession, ticket: Ticket) -> dict[str, Any]:
    policy = await resolve_effective_ticket_policy(session, ticket, "ola")
    return policy if isinstance(policy, dict) else {}


def _set_ola_runtime(ticket: Ticket, **updates: Any) -> dict:
    custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
    runtime = dict(custom_fields.get("ola_runtime") or {})
    runtime.update({key: value for key, value in updates.items() if value is not None})
    custom_fields["ola_runtime"] = runtime
    return custom_fields


async def _add_ola_event(
    session: AsyncSession,
    ticket: Ticket,
    event_type: str,
    payload: dict[str, Any],
) -> Optional[tuple]:
    from app.repos.ticket_events_repo import TicketEventsRepo

    return await TicketEventsRepo(session).add_event(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        agent_seq=None,
        event_type=event_type,
        payload=payload,
        trace_id=str(uuid.uuid4()),
    )


async def get_ola_targets_for_queue(
    session: AsyncSession,
    queue_id: int,
    priority: str,
) -> Optional[tuple[int, int]]:
    """(ack_min, processing_min) для очереди и приоритета или None."""
    if not TICKET_OLA_ENABLED:
        return None
    result = await session.execute(
        select(TicketQueueOlaTarget).where(
            TicketQueueOlaTarget.queue_id == queue_id,
            TicketQueueOlaTarget.priority == priority,
        )
    )
    row = result.scalar_one_or_none()
    if row is None and priority != "P3":
        fallback_result = await session.execute(
            select(TicketQueueOlaTarget).where(
                TicketQueueOlaTarget.queue_id == queue_id,
                TicketQueueOlaTarget.priority == "P3",
            )
        )
        row = fallback_result.scalar_one_or_none()
    if not row:
        return None
    return row.ack_min, row.processing_min


async def start_ola_for_ticket(
    session: AsyncSession,
    ticket: Ticket,
    started_at: Optional[datetime] = None,
    *,
    trigger: str = "ticket_created",
) -> bool:
    """
    Установить OLA для тикета: ola_queue_id, ola_started_at, ola_ack_due_at, ola_processing_due_at.
    Вызывать при создании тикета или смене очереди (если OLA включён).
    """
    if not TICKET_OLA_ENABLED or not ticket.queue_id:
        return False
    now = started_at or datetime.now(timezone.utc)
    priority = extract_priority_class(ticket) or "P3"
    policy = await _get_ola_policy(session, ticket)
    if not _conditions_allow(
        policy.get("start_conditions"),
        ticket=ticket,
        trigger=trigger,
        default=True,
    ):
        return False
    targets = _targets_from_ola_policy(policy, priority)
    if not targets:
        targets = await get_ola_targets_for_queue(
            session,
            ticket.queue_id,
            priority,
        )
    if not targets:
        return False
    ack_min, processing_min = targets
    ack_due = now + timedelta(minutes=ack_min)
    processing_due = now + timedelta(minutes=processing_min)
    policy_metadata = _ola_policy_metadata(policy)
    custom_fields = _set_ola_runtime(
        ticket,
        policy=policy_metadata,
        queue_id=ticket.queue_id,
        start_reason=trigger,
        started_at=now.isoformat(),
        targets={"ack_min": ack_min, "processing_min": processing_min},
        breach_actions=_breach_actions(policy),
    )
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket.ticket_id).values(
            ola_queue_id=ticket.queue_id,
            ola_started_at=now,
            ola_ack_due_at=ack_due,
            ola_processing_due_at=processing_due,
            ola_ack_at=None,
            ola_ack_breached_at=None,
            ola_processing_at=None,
            ola_processing_breached_at=None,
            ola_paused_at=None,
            ola_paused_seconds=None,
            custom_fields=custom_fields,
        )
    )
    await _add_ola_event(
        session,
        ticket,
        "ola_started",
        {
            "ticket_id": ticket.ticket_id,
            "trigger": trigger,
            "queue_id": ticket.queue_id,
            "priority": priority,
            "ola_policy": policy_metadata,
            "targets": {"ack_min": ack_min, "processing_min": processing_min},
            "ola_ack_due_at": ack_due.isoformat(),
            "ola_processing_due_at": processing_due.isoformat(),
            "breach_actions": _breach_actions(policy),
        },
    )
    return True


async def close_ola_ack(
    session: AsyncSession,
    ticket_id: str,
    at: Optional[datetime] = None,
    *,
    trigger: str = "assignee_set",
) -> bool:
    """Закрыть ack (назначение assignee). Записывает ola_ack_at."""
    if not TICKET_OLA_ENABLED:
        return False
    ticket = await session.get(Ticket, ticket_id)
    if not ticket or ticket.ola_ack_at is not None:
        return False
    policy = await _get_ola_policy(session, ticket)
    stop_conditions = _stop_conditions_for(policy, "ack")
    if not _conditions_allow(stop_conditions, ticket=ticket, trigger=trigger, default=True):
        return False
    now = at or datetime.now(timezone.utc)
    custom_fields = _set_ola_runtime(ticket, ack_stop_reason=trigger, ack_stopped_at=now.isoformat())
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket_id).values(ola_ack_at=now, custom_fields=custom_fields)
    )
    await _add_ola_event(
        session,
        ticket,
        "ola_ack_stopped",
        {
            "ticket_id": ticket_id,
            "trigger": trigger,
            "stopped_at": now.isoformat(),
            "ola_policy": _ola_policy_metadata(policy),
        },
    )
    return True


async def close_ola_processing(
    session: AsyncSession,
    ticket_id: str,
    at: Optional[datetime] = None,
    *,
    trigger: str = "processing_completed",
    status: str | None = None,
) -> bool:
    """Закрыть processing (handoff или Resolved/Closed). Записывает ola_processing_at."""
    if not TICKET_OLA_ENABLED:
        return False
    ticket = await session.get(Ticket, ticket_id)
    if not ticket or ticket.ola_processing_at is not None:
        return False
    policy = await _get_ola_policy(session, ticket)
    stop_conditions = _stop_conditions_for(policy, "processing")
    effective_status = status or ticket.status
    if not _conditions_allow(
        stop_conditions,
        ticket=ticket,
        trigger=trigger,
        status=effective_status,
        default=trigger in {"queue_changed", "handoff_completed", "processing_completed"}
        or _normalized_status(effective_status) in TERMINAL_STATUSES,
    ):
        return False
    now = at or datetime.now(timezone.utc)
    custom_fields = _set_ola_runtime(
        ticket,
        processing_stop_reason=trigger,
        processing_stop_status=effective_status,
        processing_stopped_at=now.isoformat(),
    )
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket_id).values(ola_processing_at=now, custom_fields=custom_fields)
    )
    await _add_ola_event(
        session,
        ticket,
        "ola_processing_stopped",
        {
            "ticket_id": ticket_id,
            "trigger": trigger,
            "status": effective_status,
            "stopped_at": now.isoformat(),
            "ola_policy": _ola_policy_metadata(policy),
        },
    )
    return True


async def pause_ola(
    session: AsyncSession,
    ticket_id: str,
    *,
    trigger: str = "status_changed",
    status: str | None = None,
) -> bool:
    if not TICKET_OLA_ENABLED:
        return False
    ticket = await session.get(Ticket, ticket_id)
    if not ticket or ticket.ola_paused_at is not None:
        return False
    policy = await _get_ola_policy(session, ticket)
    effective_status = status or ticket.status
    if not _conditions_allow(
        policy.get("pause_conditions"),
        ticket=ticket,
        trigger=trigger,
        status=effective_status,
        default=_normalized_status(effective_status) in WAITING_STATUSES,
    ):
        return False
    now = datetime.now(timezone.utc)
    custom_fields = _set_ola_runtime(
        ticket,
        pause_reason=trigger,
        pause_status=effective_status,
        paused_at=now.isoformat(),
    )
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket_id).values(ola_paused_at=now, custom_fields=custom_fields)
    )
    await _add_ola_event(
        session,
        ticket,
        "ola_paused",
        {
            "ticket_id": ticket_id,
            "trigger": trigger,
            "status": effective_status,
            "paused_at": now.isoformat(),
            "ola_policy": _ola_policy_metadata(policy),
        },
    )
    return True


async def resume_ola(
    session: AsyncSession,
    ticket_id: str,
    *,
    trigger: str = "status_changed",
    status: str | None = None,
) -> bool:
    if not TICKET_OLA_ENABLED:
        return False
    ticket = await session.get(Ticket, ticket_id)
    if not ticket or ticket.ola_paused_at is None:
        return False
    policy = await _get_ola_policy(session, ticket)
    effective_status = status or ticket.status
    if not _conditions_allow(
        policy.get("resume_conditions"),
        ticket=ticket,
        trigger=trigger,
        status=effective_status,
        default=_normalized_status(effective_status) not in WAITING_STATUSES,
    ):
        return False
    now = datetime.now(timezone.utc)
    added_pause_sec = int((now - ticket.ola_paused_at).total_seconds())
    total_paused = (ticket.ola_paused_seconds or 0) + added_pause_sec
    custom_fields = _set_ola_runtime(
        ticket,
        resume_reason=trigger,
        resume_status=effective_status,
        resumed_at=now.isoformat(),
        ola_paused_seconds=total_paused,
    )
    await session.execute(
        update(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .values(ola_paused_at=None, ola_paused_seconds=total_paused, custom_fields=custom_fields)
    )
    await _add_ola_event(
        session,
        ticket,
        "ola_resumed",
        {
            "ticket_id": ticket_id,
            "trigger": trigger,
            "status": effective_status,
            "resumed_at": now.isoformat(),
            "added_pause_sec": added_pause_sec,
            "ola_paused_seconds": total_paused,
            "ola_policy": _ola_policy_metadata(policy),
        },
    )
    return True


async def check_ola_breaches(session: AsyncSession, *, limit: int = 100) -> int:
    if not TICKET_OLA_ENABLED:
        return 0
    result = await session.execute(
        select(Ticket)
        .where(
            Ticket.status.notin_(list(TERMINAL_STATUSES)),
            (Ticket.ola_ack_due_at.isnot(None) | Ticket.ola_processing_due_at.isnot(None)),
        )
        .limit(limit)
    )
    now = datetime.now(timezone.utc)
    count = 0
    for ticket in result.scalars().all():
        updates: dict[str, Any] = {}
        paused = ticket.ola_paused_seconds or 0
        if ticket.ola_ack_due_at and ticket.ola_ack_at is None and ticket.ola_ack_breached_at is None:
            if now >= ticket.ola_ack_due_at + timedelta(seconds=paused):
                updates["ola_ack_breached_at"] = now
        if (
            ticket.ola_processing_due_at
            and ticket.ola_processing_at is None
            and ticket.ola_processing_breached_at is None
        ):
            if now >= ticket.ola_processing_due_at + timedelta(seconds=paused):
                updates["ola_processing_breached_at"] = now
        if not updates:
            continue
        policy = await _get_ola_policy(session, ticket)
        breach_types = [key for key in updates.keys() if key != "custom_fields"]
        breach_actions = _breach_actions(policy)
        breach_event_id = f"ola-breach-{ticket.ticket_id}-{'-'.join(breach_types)}"
        custom_fields = _set_ola_runtime(
            ticket,
            breached_at=now.isoformat(),
            breach_types=breach_types,
            breach_actions=breach_actions,
        )
        updates["custom_fields"] = custom_fields
        await session.execute(update(Ticket).where(Ticket.ticket_id == ticket.ticket_id).values(**updates))
        await _add_ola_event(
            session,
            ticket,
            "ola_breached",
            {
                "ticket_id": ticket.ticket_id,
                "breach_types": breach_types,
                "source_event_id": breach_event_id,
                "ts": now.isoformat(),
                "ola_policy": _ola_policy_metadata(policy),
                "breach_actions": breach_actions,
            },
        )
        if breach_actions:
            from tickets.policy_action_dispatcher import dispatch_policy_actions

            await dispatch_policy_actions(
                session,
                ticket=ticket,
                source_event_type="ola_breached",
                source_event_id=breach_event_id,
                actions=breach_actions,
                payload={
                    "ticket_id": ticket.ticket_id,
                    "breach_types": breach_types,
                    "ts": now.isoformat(),
                    "ola_policy": _ola_policy_metadata(policy),
                },
            )
        count += 1
    return count


def build_ola_block(ticket: Ticket) -> Optional[dict]:
    """Собрать OLA-блок для ответа GET /api/tickets/{id}/sla."""
    if not TICKET_OLA_ENABLED or ticket.ola_queue_id is None:
        return None
    return {
        "ola_queue_id": ticket.ola_queue_id,
        "ola_started_at": ticket.ola_started_at.isoformat() if ticket.ola_started_at else None,
        "ola_ack_due_at": ticket.ola_ack_due_at.isoformat() if ticket.ola_ack_due_at else None,
        "ola_ack_at": ticket.ola_ack_at.isoformat() if ticket.ola_ack_at else None,
        "ola_ack_breached_at": ticket.ola_ack_breached_at.isoformat() if ticket.ola_ack_breached_at else None,
        "ola_processing_due_at": ticket.ola_processing_due_at.isoformat() if ticket.ola_processing_due_at else None,
        "ola_processing_at": ticket.ola_processing_at.isoformat() if ticket.ola_processing_at else None,
        "ola_processing_breached_at": ticket.ola_processing_breached_at.isoformat() if ticket.ola_processing_breached_at else None,
        "ola_paused_at": ticket.ola_paused_at.isoformat() if ticket.ola_paused_at else None,
        "ola_paused_seconds": ticket.ola_paused_seconds,
        "ola_policy": (ticket.custom_fields or {}).get("ola_runtime", {}).get("policy")
        if isinstance(ticket.custom_fields, dict)
        else None,
    }
