"""
Сервис маршрутизации тикетов (Этап 2).

- First-match по priority_order правил из ticket_routing_rules.
- Fallback: servicedesk_l1.
- Manual queue lock в custom_fields (routing_lock, routing_lock_reason, routing_lock_at).
- События: routing_applied, queue_changed.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.db.models import Ticket
from tickets.public_access import is_public_unbound_ticket
from tickets.statuses import extract_priority_class, get_requester_display_name, get_requester_profile

FALLBACK_QUEUE_CODE = "servicedesk_l1"
ROUTING_LOCK_KEY = "routing_lock"
ROUTING_LOCK_REASON_KEY = "routing_lock_reason"
ROUTING_LOCK_AT_KEY = "routing_lock_at"


def _get_ticket_context(ticket: Ticket, device_metadata: Optional[dict]) -> Dict[str, Any]:
    """Контекст тикета для правил: поля тикета + devices.metadata (location, device_type и т.д.)."""
    requester_profile = get_requester_profile(ticket)
    requester_display_name = get_requester_display_name(ticket)
    is_public_ticket = str(getattr(ticket, "requester_id", "") or "").startswith("public:")
    ctx = {
        "ticket_id": ticket.ticket_id,
        "device_id": ticket.device_id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "priority_class": extract_priority_class(ticket),
        "impact": ticket.impact,
        "urgency": ticket.urgency,
        "importance": ticket.importance,
        "queue_id": ticket.queue_id,
        "category_id": ticket.category_id,
        "service_id": ticket.service_id,
        "subcategory_id": ticket.subcategory_id,
        "assignee_id": ticket.assignee_id,
        "requester_id": ticket.requester_id,
        "requester_display_name": requester_display_name,
        "requester_profile": requester_profile,
        "is_public_ticket": is_public_ticket,
        "public_ticket_unbound": is_public_unbound_ticket(ticket),
    }
    if requester_profile:
        ctx["building"] = requester_profile.get("building")
        ctx["room"] = requester_profile.get("room")
        ctx["phone"] = requester_profile.get("phone")
    if device_metadata and isinstance(device_metadata, dict):
        ctx["device_metadata"] = device_metadata
        ctx["location"] = device_metadata.get("location")
        ctx["device_type"] = device_metadata.get("device_type")
    return ctx


def _evaluate_condition(condition: Optional[dict], context: Dict[str, Any]) -> bool:
    """
    Оценка condition_json правила.
    Формат: {"field": "priority", "op": "eq", "value": "P1"}
    или {"and": [cond1, cond2]}, {"or": [cond1, cond2]}.
    Если condition пустой/None — правило срабатывает (match all).
    """
    if not condition:
        return True
    if "and" in condition:
        return all(
            _evaluate_condition(c, context) for c in condition["and"]
        )
    if "or" in condition:
        return any(
            _evaluate_condition(c, context) for c in condition["or"]
        )
    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")
    if field is None or op is None:
        return True
    # Вложенные поля типа device_metadata.location
    actual = context
    for part in field.split("."):
        actual = actual.get(part) if isinstance(actual, dict) else None
        if actual is None:
            break
    if op == "eq":
        return actual == value
    if op == "ne":
        return actual != value
    if op == "in":
        return value is not None and actual in value
    if op == "nin":
        return value is not None and actual not in value
    if op == "contains":
        return isinstance(actual, str) and value is not None and value in actual
    if op == "is_null":
        return (value is True and actual is None) or (value is False and actual is not None)
    return False


def has_routing_lock(custom_fields: Optional[dict]) -> bool:
    """Проверка, установлен ли ручной lock очереди."""
    if not custom_fields or not isinstance(custom_fields, dict):
        return False
    return bool(custom_fields.get(ROUTING_LOCK_KEY))


def set_routing_lock(
    custom_fields: Optional[dict],
    reason: str,
) -> dict:
    """Установить routing lock в custom_fields."""
    cf = dict(custom_fields) if custom_fields and isinstance(custom_fields, dict) else {}
    cf[ROUTING_LOCK_KEY] = True
    cf[ROUTING_LOCK_REASON_KEY] = reason
    cf[ROUTING_LOCK_AT_KEY] = datetime.now(timezone.utc).isoformat()
    return cf


def clear_routing_lock(custom_fields: Optional[dict]) -> dict:
    """Снять routing lock."""
    cf = dict(custom_fields) if custom_fields and isinstance(custom_fields, dict) else {}
    cf.pop(ROUTING_LOCK_KEY, None)
    cf.pop(ROUTING_LOCK_REASON_KEY, None)
    cf.pop(ROUTING_LOCK_AT_KEY, None)
    return cf


class TicketRoutingService:
    """Маршрутизация тикетов по правилам (first-match) с fallback в servicedesk_l1."""

    def __init__(self, session, ticket_repo, devices_repo=None):
        self.session = session
        self.ticket_repo = ticket_repo
        self.devices_repo = devices_repo

    async def get_device_metadata(self, device_id: str) -> Optional[dict]:
        """Метаданные устройства (location, device_type и т.д.) для правил."""
        if not self.devices_repo:
            return None
        try:
            device = await self.devices_repo.get_by_device_id(device_id)
            if device and getattr(device, "device_metadata", None):
                return device.device_metadata
        except Exception as e:
            logger.debug(f"[Routing] Failed to get device metadata for {device_id}: {e}")
        return None

    async def resolve_queue_id(
        self,
        ticket: Ticket,
        device_metadata: Optional[dict] = None,
    ) -> Optional[int]:
        """
        Определить очередь по правилам: first-match по priority_order.
        Если ни одно правило не подошло — fallback servicedesk_l1.
        """
        if device_metadata is None and ticket.device_id:
            device_metadata = await self.get_device_metadata(ticket.device_id)
        context = _get_ticket_context(ticket, device_metadata)
        rules = await self.ticket_repo.get_routing_rules_ordered()
        for rule in rules:
            if _evaluate_condition(rule.condition_json, context):
                logger.debug(
                    f"[Routing] Rule id={rule.id} matched ticket_id={ticket.ticket_id} -> queue_id={rule.target_queue_id}"
                )
                return rule.target_queue_id
        queue = await self.ticket_repo.get_queue_by_code(FALLBACK_QUEUE_CODE)
        if queue:
            logger.debug(f"[Routing] Fallback to {FALLBACK_QUEUE_CODE} queue_id={queue.id}")
            return queue.id
        return None

    async def apply_routing(
        self,
        ticket_id: str,
        device_id: str,
        *,
        force_clear_lock: bool = False,
        add_events_fn=None,
    ) -> Optional[int]:
        """
        Применить маршрутизацию к тикету: обновить queue_id (если нет lock или force_clear_lock),
        записать события routing_applied / queue_changed.
        add_events_fn(ticket_id, device_id, event_type, payload) — опционально, для записи в ticket_events.
        Returns: новый queue_id или None.
        """
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket:
            return None
        if not force_clear_lock and has_routing_lock(ticket.custom_fields):
            logger.debug(f"[Routing] Ticket {ticket_id} has routing lock, skip auto-routing")
            return ticket.queue_id
        new_queue_id = await self.resolve_queue_id(ticket)
        if new_queue_id is None:
            return ticket.queue_id
        old_queue_id = ticket.queue_id
        if new_queue_id == old_queue_id:
            return new_queue_id
        custom = clear_routing_lock(ticket.custom_fields) if force_clear_lock else (ticket.custom_fields or {})
        await self.ticket_repo.update_ticket(
            ticket_id,
            queue_id=new_queue_id,
            custom_fields=custom,
            manual_rank=None,
            manual_rank_updated_at=None,
            manual_rank_updated_by=None,
        )
        if add_events_fn:
            await add_events_fn(
                ticket_id,
                device_id,
                "routing_applied",
                {"from_queue_id": old_queue_id, "to_queue_id": new_queue_id},
            )
            await add_events_fn(
                ticket_id,
                device_id,
                "queue_changed",
                {"queue_id": new_queue_id, "previous_queue_id": old_queue_id},
            )
        logger.info(f"[Routing] Ticket {ticket_id} routed to queue_id={new_queue_id}")
        return new_queue_id
