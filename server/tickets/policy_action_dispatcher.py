"""Shared dispatcher for SLA/OLA and workflow policy actions."""

from __future__ import annotations

from typing import Any, Iterable, TYPE_CHECKING

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketNotification, TicketQueueMember, TicketWatcher
from app.repos.notification_prefs_repo import DEFAULT_SUPPRESS_SELF
from app.repos.notification_repo import NotificationRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.notification_channels import ExternalNotificationProvider, normalize_delivery_result

if TYPE_CHECKING:
    from app.repos.notification_prefs_repo import NotificationPrefsRepo


_QUEUE_LEAD_ROLES = {"lead", "queue_lead", "queue-lead", "owner", "manager"}


def _unique(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        actor_id = str(value or "").strip()
        if not actor_id or actor_id in seen:
            continue
        seen.add(actor_id)
        result.append(actor_id)
    return result


def _enabled_channels(actions: dict[str, Any]) -> list[str]:
    raw = actions.get("channels") or actions.get("external_channels") or []
    if isinstance(raw, dict):
        items = [str(channel).strip().lower() for channel, enabled in raw.items() if bool(enabled)]
    elif isinstance(raw, list):
        items = [str(channel).strip().lower() for channel in raw]
    else:
        items = []
    return [channel for channel in _unique(items) if channel and channel != "web"]


def _notify_specs(actions: dict[str, Any]) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    if actions.get("notify_queue_lead"):
        specs.append(("notify_queue_lead", "queue_lead"))

    raw_notify = actions.get("notify")
    if isinstance(raw_notify, dict):
        for key, enabled in raw_notify.items():
            recipient_key = str(key or "").strip()
            if recipient_key and bool(enabled):
                specs.append((f"notify:{recipient_key}", recipient_key))
    elif isinstance(raw_notify, list):
        for value in raw_notify:
            recipient_key = str(value or "").strip()
            if recipient_key:
                specs.append((f"notify:{recipient_key}", recipient_key))

    return _unique_action_specs(specs)


def _unique_action_specs(specs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for action_key, recipient_key in specs:
        item = (str(action_key or "").strip(), str(recipient_key or "").strip())
        if not item[0] or not item[1] or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


async def _queue_leads(session: AsyncSession, queue_id: int | None) -> list[str]:
    if queue_id is None:
        return []
    stmt = select(TicketQueueMember.actor_id).where(
        TicketQueueMember.queue_id == queue_id,
        func.lower(TicketQueueMember.role_in_queue).in_(_QUEUE_LEAD_ROLES),
    )
    result = await session.execute(stmt)
    return _unique(result.scalars().all())


async def _queue_members(session: AsyncSession, queue_id: int | None) -> list[str]:
    if queue_id is None:
        return []
    stmt = select(TicketQueueMember.actor_id).where(TicketQueueMember.queue_id == queue_id)
    result = await session.execute(stmt)
    return _unique(result.scalars().all())


async def _watchers(session: AsyncSession, ticket_id: str) -> list[str]:
    stmt = select(TicketWatcher.actor_id).where(TicketWatcher.ticket_id == ticket_id)
    result = await session.execute(stmt)
    return _unique(result.scalars().all())


async def _resolve_recipients(
    session: AsyncSession,
    ticket: Ticket,
    recipient_key: str,
    actions: dict[str, Any],
) -> list[str]:
    key = str(recipient_key or "").strip()
    if key == "queue_lead":
        return await _queue_leads(session, ticket.queue_id)
    if key == "queue":
        return await _queue_members(session, ticket.queue_id)
    if key == "assignee":
        return _unique([ticket.assignee_id])
    if key == "requester":
        return _unique([ticket.requester_id])
    if key == "watchers":
        return await _watchers(session, ticket.ticket_id)
    if key in {"actor", "actors", "explicit_actors"}:
        raw = actions.get("actors") or actions.get("actor_ids") or actions.get("recipients") or []
        return _unique(raw if isinstance(raw, list) else [raw])
    return []


async def _notification_exists(
    session: AsyncSession,
    *,
    actor_id: str,
    ticket_id: str,
    event_type: str,
    source_event_id: str,
    action_key: str,
) -> bool:
    result = await session.execute(
        select(TicketNotification)
        .where(
            TicketNotification.actor_id == actor_id,
            TicketNotification.ticket_id == ticket_id,
            TicketNotification.event_type == event_type,
        )
        .order_by(TicketNotification.id.desc())
    )
    for item in result.scalars().all():
        payload = item.payload if isinstance(item.payload, dict) else {}
        if payload.get("source_event_id") == source_event_id and payload.get("policy_action_key") == action_key:
            return True
    return False


async def _recipient_allowed(
    *,
    actor_id: str,
    event_type: str,
    visibility: str,
    initiator_id: str | None,
    prefs_repo: "NotificationPrefsRepo | None",
) -> bool:
    if prefs_repo is None:
        return not (initiator_id and str(actor_id) == str(initiator_id) and DEFAULT_SUPPRESS_SELF)
    mute_internal, muted_types, suppress_self = await prefs_repo.get_or_default(actor_id)
    if initiator_id and str(actor_id) == str(initiator_id) and suppress_self:
        return False
    if mute_internal and visibility == "internal":
        return False
    return event_type not in muted_types


async def _record_audit_event(
    ticket_repo: TicketEventsRepo,
    ticket: Ticket,
    *,
    source_event_type: str,
    source_event_id: str,
    action_key: str,
    actor_id: str,
    payload: dict[str, Any],
) -> bool:
    event_id = f"policy-action-{ticket.ticket_id}-{source_event_id}-{action_key}-{actor_id}"
    inserted = await ticket_repo.add_event(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        agent_seq=None,
        event_type="policy_action_dispatched",
        payload={
            "ticket_id": ticket.ticket_id,
            "source_event_type": source_event_type,
            "source_event_id": source_event_id,
            "action_key": action_key,
            "actor_id": actor_id,
            **payload,
        },
        event_id=event_id,
    )
    return inserted is not None


async def _deliver_external(
    ticket_repo: TicketEventsRepo,
    ticket: Ticket,
    channel_provider: ExternalNotificationProvider,
    *,
    channels: list[str],
    actor_id: str,
    event_type: str,
    source_event_id: str,
    action_key: str,
    payload: dict[str, Any],
) -> int:
    created = 0
    for channel in channels:
        audit_payload: dict[str, Any] = {
            "channel": channel,
            "actor_id": actor_id,
            "ticket_id": ticket.ticket_id,
            "event_type": event_type,
        }
        try:
            result = await channel_provider.send(
                channel=channel,
                actor_id=actor_id,
                ticket_id=ticket.ticket_id,
                event_type=event_type,
                payload=payload,
            )
            audit_payload.update(normalize_delivery_result(result))
        except Exception as exc:
            audit_payload.update({"delivery_status": "failed", "error": str(exc)})
            logger.warning(
                f"[PolicyActionDispatcher] external delivery failed channel={channel} "
                f"actor_id={actor_id} ticket_id={ticket.ticket_id}: {exc}"
            )
        inserted = await ticket_repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="external_notification_delivery",
            payload=audit_payload,
            event_id=(
                f"external-policy-action-{ticket.ticket_id}-{source_event_id}-"
                f"{action_key}-{channel}-{actor_id}"
            ),
        )
        if inserted is not None:
            created += 1
    return created


async def dispatch_policy_actions(
    session: AsyncSession,
    *,
    ticket: Ticket,
    source_event_type: str,
    source_event_id: str,
    actions: dict[str, Any] | None,
    payload: dict[str, Any] | None = None,
    visibility: str = "internal",
    initiator_id: str | None = None,
    notification_repo: NotificationRepo | None = None,
    prefs_repo: "NotificationPrefsRepo | None" = None,
    channel_provider: ExternalNotificationProvider | None = None,
) -> dict[str, int]:
    """Resolve and deliver policy actions with recipient-level idempotency."""
    if not ticket or not isinstance(actions, dict) or not actions:
        return {"created_notifications": 0, "created_audit_events": 0, "external_deliveries": 0}

    notification_repo = notification_repo or NotificationRepo(session)
    ticket_repo = TicketEventsRepo(session)
    source_payload = dict(payload or {})
    source_event_id = str(source_event_id or "").strip()
    event_type = str(source_event_type or "").strip()
    if not source_event_id or not event_type:
        return {"created_notifications": 0, "created_audit_events": 0, "external_deliveries": 0}

    created_notifications = 0
    created_audit_events = 0
    external_deliveries = 0
    channels = _enabled_channels(actions)
    audit_enabled = bool(actions.get("create_internal_event", True))

    for action_key, recipient_key in _notify_specs(actions):
        recipients = await _resolve_recipients(session, ticket, recipient_key, actions)
        for actor_id in recipients:
            if not await _recipient_allowed(
                actor_id=actor_id,
                event_type=event_type,
                visibility=visibility,
                initiator_id=initiator_id,
                prefs_repo=prefs_repo,
            ):
                continue
            if await _notification_exists(
                session,
                actor_id=actor_id,
                ticket_id=ticket.ticket_id,
                event_type=event_type,
                source_event_id=source_event_id,
                action_key=action_key,
            ):
                continue
            notification_payload = {
                **source_payload,
                "source_event_type": event_type,
                "source_event_id": source_event_id,
                "policy_action_key": action_key,
                "policy_recipient_key": recipient_key,
                "breach_actions": actions,
            }
            await notification_repo.create(
                actor_id=actor_id,
                ticket_id=ticket.ticket_id,
                event_type=event_type,
                payload=notification_payload,
            )
            created_notifications += 1
            if audit_enabled:
                if await _record_audit_event(
                    ticket_repo,
                    ticket,
                    source_event_type=event_type,
                    source_event_id=source_event_id,
                    action_key=action_key,
                    actor_id=actor_id,
                    payload={"recipient_key": recipient_key},
                ):
                    created_audit_events += 1
            if channel_provider and channels:
                external_deliveries += await _deliver_external(
                    ticket_repo,
                    ticket,
                    channel_provider,
                    channels=channels,
                    actor_id=actor_id,
                    event_type=event_type,
                    source_event_id=source_event_id,
                    action_key=action_key,
                    payload=notification_payload,
                )

    return {
        "created_notifications": created_notifications,
        "created_audit_events": created_audit_events,
        "external_deliveries": external_deliveries,
    }
