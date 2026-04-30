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
from tickets.statuses import (
    PRIORITY_CLASS_TO_LEGACY_PRIORITY,
    extract_priority_class,
    get_requester_display_name,
    get_requester_profile,
)

FALLBACK_QUEUE_CODE = "servicedesk_l1"
ROUTING_LOCK_KEY = "routing_lock"
ROUTING_LOCK_REASON_KEY = "routing_lock_reason"
ROUTING_LOCK_AT_KEY = "routing_lock_at"
ROUTING_DECISION_KEY = "routing_decision"
PROCESS_PRIORITIES = ("P0", "P1", "P2", "P3")


def _build_context(
    *,
    ticket_id: str | None,
    device_id: str | None,
    title: str | None,
    description: str | None,
    status: str | None,
    priority: str | None,
    priority_class: str | None,
    impact: Any,
    urgency: Any,
    importance: Any,
    queue_id: Any,
    category_id: Any,
    service_id: Any,
    subcategory_id: Any,
    assignee_id: str | None,
    requester_id: str | None,
    requester_display_name: str | None,
    requester_profile: Optional[dict],
    is_public_ticket: bool,
    public_ticket_unbound: bool,
    custom_fields: Optional[dict],
    ticket_type: str | None,
    device_metadata: Optional[dict],
) -> Dict[str, Any]:
    normalized_custom_fields = custom_fields if isinstance(custom_fields, dict) else {}
    request_form_data = normalized_custom_fields.get("request_form_data")
    request_form_summary = normalized_custom_fields.get("request_form_summary")
    ctx = {
        "ticket_id": ticket_id,
        "device_id": device_id,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "priority_class": priority_class,
        "impact": impact,
        "urgency": urgency,
        "importance": importance,
        "queue_id": queue_id,
        "category_id": category_id,
        "service_id": service_id,
        "subcategory_id": subcategory_id,
        "assignee_id": assignee_id,
        "requester_id": requester_id,
        "requester_display_name": requester_display_name,
        "requester_profile": requester_profile or {},
        "is_public_ticket": is_public_ticket,
        "public_ticket_unbound": public_ticket_unbound,
        "custom_fields": normalized_custom_fields,
        "ticket_type": ticket_type,
        "request_kind": normalized_custom_fields.get("request_kind") or ticket_type,
        "request_form_key": normalized_custom_fields.get("request_form_key"),
        "request_form_title": normalized_custom_fields.get("request_form_title"),
        "request_form_data": request_form_data if isinstance(request_form_data, dict) else {},
        "request_form_summary": request_form_summary if isinstance(request_form_summary, list) else [],
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


def _get_ticket_context(ticket: Ticket, device_metadata: Optional[dict]) -> Dict[str, Any]:
    """Контекст тикета для правил: поля тикета + devices.metadata (location, device_type и т.д.)."""
    requester_profile = get_requester_profile(ticket)
    requester_display_name = get_requester_display_name(ticket)
    is_public_ticket = str(getattr(ticket, "requester_id", "") or "").startswith("public:")
    return _build_context(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        priority_class=extract_priority_class(ticket),
        impact=ticket.impact,
        urgency=ticket.urgency,
        importance=ticket.importance,
        queue_id=ticket.queue_id,
        category_id=ticket.category_id,
        service_id=ticket.service_id,
        subcategory_id=ticket.subcategory_id,
        assignee_id=ticket.assignee_id,
        requester_id=ticket.requester_id,
        requester_display_name=requester_display_name,
        requester_profile=requester_profile,
        is_public_ticket=is_public_ticket,
        public_ticket_unbound=is_public_unbound_ticket(ticket),
        custom_fields=getattr(ticket, "custom_fields", None),
        ticket_type=getattr(ticket, "ticket_type", None),
        device_metadata=device_metadata,
    )


def build_form_routing_context(
    *,
    ticket_type: str | None,
    custom_fields: Optional[dict],
) -> Dict[str, Any]:
    return _build_context(
        ticket_id="preview",
        device_id=None,
        title=None,
        description=None,
        status="new",
        priority=None,
        priority_class=None,
        impact=None,
        urgency=None,
        importance=None,
        queue_id=None,
        category_id=None,
        service_id=None,
        subcategory_id=None,
        assignee_id=None,
        requester_id=None,
        requester_display_name=None,
        requester_profile=None,
        is_public_ticket=False,
        public_ticket_unbound=False,
        custom_fields=custom_fields,
        ticket_type=ticket_type,
        device_metadata=None,
    )


def _lookup_context_value(context: Dict[str, Any], field_path: str) -> Any:
    actual: Any = context
    for part in field_path.split("."):
        if isinstance(actual, dict):
            actual = actual.get(part)
        else:
            actual = getattr(actual, part, None)
        if actual is None:
            break
    return actual


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
        return False
    actual = _lookup_context_value(context, str(field))
    if op == "eq":
        return actual == value
    if op == "ne":
        return actual != value
    if op == "in":
        return isinstance(value, list) and actual in value
    if op == "nin":
        return isinstance(value, list) and actual not in value
    if op == "contains":
        return isinstance(actual, str) and value is not None and value in actual
    if op == "is_null":
        return (value is True and actual is None) or (value is False and actual is not None)
    return False


def find_matching_routing_rule(rules: List[Any], context: Dict[str, Any]) -> Any | None:
    for rule in rules:
        if _evaluate_condition(getattr(rule, "condition_json", None), context):
            return rule
    return None


def _get_request_template(custom_fields: Optional[dict]) -> dict:
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    return request_template if isinstance(request_template, dict) else {}


def _get_template_routing_policy(ticket: Ticket) -> dict:
    request_template = _get_request_template(getattr(ticket, "custom_fields", None))
    routing_policy = request_template.get("routing_policy") or {}
    return routing_policy if isinstance(routing_policy, dict) else {}


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_template_rules(policy: dict) -> list[tuple[int, int, dict]]:
    rules = policy.get("rules") or []
    if not isinstance(rules, list):
        return []
    normalized: list[tuple[int, int, dict]] = []
    for index, raw_rule in enumerate(rules):
        if not isinstance(raw_rule, dict):
            continue
        priority_order = _as_int(raw_rule.get("priority_order"))
        normalized.append((priority_order if priority_order is not None else index, index, raw_rule))
    return sorted(normalized, key=lambda item: (item[0], item[1]))


def _rule_condition(rule: dict) -> Optional[dict]:
    condition = rule.get("when")
    if condition is None:
        condition = rule.get("condition")
    if condition is None:
        condition = rule.get("condition_json")
    return condition if isinstance(condition, dict) else None


def _rule_actions(rule: dict) -> dict:
    actions = rule.get("then")
    if isinstance(actions, dict):
        return dict(actions)
    inline = {}
    for key in (
        "queue_id",
        "target_queue_id",
        "queue",
        "queue_code",
        "assignee_id",
        "priority_boost",
        "increase_priority_by",
        "minimum_priority",
        "sla_policy_id",
        "ola_policy_id",
        "approval_policy",
        "suggested_playbook",
        "suggested_playbook_id",
        "tags",
        "watchers",
        "visibility",
    ):
        if key in rule:
            inline[key] = rule[key]
    return inline


def _routing_count(custom_fields: Optional[dict]) -> int:
    if not isinstance(custom_fields, dict):
        return 0
    decision = custom_fields.get(ROUTING_DECISION_KEY) or {}
    if not isinstance(decision, dict):
        return 0
    count = _as_int(decision.get("auto_reroute_count"))
    return count if count is not None else 0


def _boost_priority(priority_class: str, boost: int) -> str:
    if priority_class not in PROCESS_PRIORITIES:
        priority_class = "P3"
    rank = PROCESS_PRIORITIES.index(priority_class)
    boosted_rank = max(rank - max(boost, 0), 0)
    return PROCESS_PRIORITIES[boosted_rank]


def _minimum_priority(priority_class: str, minimum: Any) -> str:
    minimum_str = str(minimum or "").strip()
    if priority_class not in PROCESS_PRIORITIES:
        priority_class = "P3"
    if minimum_str not in PROCESS_PRIORITIES:
        return priority_class
    return PROCESS_PRIORITIES[min(PROCESS_PRIORITIES.index(priority_class), PROCESS_PRIORITIES.index(minimum_str))]


def _merge_tags(current: Any, action_tags: Any) -> list[str] | None:
    if action_tags is None:
        return None
    current_items = current if isinstance(current, list) else []
    raw_items = action_tags if isinstance(action_tags, list) else [action_tags]
    merged: list[str] = []
    for item in [*current_items, *raw_items]:
        value = str(item or "").strip()
        if value and value not in merged:
            merged.append(value)
    return merged


def _public_matched_rule(rule: Optional[dict], priority_order: Optional[int] = None, index: Optional[int] = None) -> dict | None:
    if not isinstance(rule, dict):
        return None
    result: dict[str, Any] = {}
    if priority_order is not None:
        result["priority_order"] = priority_order
    if index is not None:
        result["index"] = index
    condition = _rule_condition(rule)
    if condition:
        result["when"] = condition
    return result


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

    async def _queue_id_from_actions(self, actions: dict) -> Optional[int]:
        queue_id = _as_int(actions.get("queue_id"))
        if queue_id is None:
            queue_id = _as_int(actions.get("target_queue_id"))
        if queue_id is not None:
            return queue_id
        queue_code = str(actions.get("queue_code") or actions.get("queue") or "").strip()
        if queue_code:
            queue = await self.ticket_repo.get_queue_by_code(queue_code)
            if queue:
                return queue.id
        return None

    async def _resolve_template_policy_decision(
        self,
        *,
        ticket: Ticket,
        context: Dict[str, Any],
        policy: dict,
    ) -> Optional[dict]:
        for priority_order, index, rule in _normalize_template_rules(policy):
            if not _evaluate_condition(_rule_condition(rule), context):
                continue
            actions = _rule_actions(rule)
            queue_id = await self._queue_id_from_actions(actions)
            return {
                "source": "request_template.routing_policy",
                "queue_id": queue_id,
                "actions": actions,
                "matched_rule": _public_matched_rule(rule, priority_order, index),
            }

        fallback = policy.get("fallback")
        if isinstance(fallback, dict):
            queue_id = await self._queue_id_from_actions(fallback)
            if queue_id is not None:
                return {
                    "source": "request_template.routing_policy.fallback",
                    "queue_id": queue_id,
                    "actions": dict(fallback),
                    "matched_rule": None,
                }

        default_queue_id = _as_int(policy.get("default_queue_id"))
        if default_queue_id is not None:
            return {
                "source": "request_template.routing_policy.default_queue",
                "queue_id": default_queue_id,
                "actions": {"queue_id": default_queue_id},
                "matched_rule": None,
            }
        return None

    async def resolve_routing_decision(
        self,
        ticket: Ticket,
        device_metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        if device_metadata is None and ticket.device_id:
            device_metadata = await self.get_device_metadata(ticket.device_id)
        context = _get_ticket_context(ticket, device_metadata)

        template_policy = _get_template_routing_policy(ticket)
        if template_policy:
            decision = await self._resolve_template_policy_decision(
                ticket=ticket,
                context=context,
                policy=template_policy,
            )
            if decision is not None:
                return decision

        rules = await self.ticket_repo.get_routing_rules_ordered()
        matched_rule = find_matching_routing_rule(rules, context)
        if matched_rule is not None:
            logger.debug(
                f"[Routing] Rule id={matched_rule.id} matched ticket_id={ticket.ticket_id} "
                f"-> queue_id={matched_rule.target_queue_id}"
            )
            return {
                "source": "ticket_routing_rule",
                "queue_id": matched_rule.target_queue_id,
                "actions": {"queue_id": matched_rule.target_queue_id},
                "matched_rule": {
                    "id": matched_rule.id,
                    "priority_order": matched_rule.priority_order,
                    "when": getattr(matched_rule, "condition_json", None),
                },
            }

        request_template = _get_request_template(getattr(ticket, "custom_fields", None))
        default_queue_id = _as_int(request_template.get("default_queue_id"))
        if default_queue_id is not None:
            logger.debug(
                f"[Routing] Template default_queue_id matched ticket_id={ticket.ticket_id} "
                f"-> queue_id={default_queue_id}"
            )
            return {
                "source": "request_template.default_queue",
                "queue_id": default_queue_id,
                "actions": {"queue_id": default_queue_id},
                "matched_rule": None,
            }

        queue = await self.ticket_repo.get_queue_by_code(FALLBACK_QUEUE_CODE)
        if queue:
            logger.debug(f"[Routing] Fallback to {FALLBACK_QUEUE_CODE} queue_id={queue.id}")
            return {
                "source": "fallback_queue",
                "queue_id": queue.id,
                "actions": {"queue_id": queue.id},
                "matched_rule": None,
            }
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
        decision = await self.resolve_routing_decision(ticket, device_metadata)
        if decision is None:
            return None
        return decision.get("queue_id")

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
        template_policy = _get_template_routing_policy(ticket)
        if not force_clear_lock and has_routing_lock(ticket.custom_fields):
            logger.debug(f"[Routing] Ticket {ticket_id} has routing lock, skip auto-routing")
            return ticket.queue_id
        if (
            not force_clear_lock
            and template_policy.get("do_not_reroute_if_assignee_locked")
            and getattr(ticket, "assignee_id", None)
        ):
            logger.debug(f"[Routing] Ticket {ticket_id} has assignee and policy guard, skip auto-routing")
            return ticket.queue_id
        max_auto_reroutes = _as_int(template_policy.get("max_auto_reroutes"))
        if not force_clear_lock and max_auto_reroutes is not None and _routing_count(ticket.custom_fields) >= max_auto_reroutes:
            logger.debug(f"[Routing] Ticket {ticket_id} reached max_auto_reroutes={max_auto_reroutes}")
            return ticket.queue_id
        decision = await self.resolve_routing_decision(ticket)
        if decision is None:
            return ticket.queue_id
        new_queue_id = decision.get("queue_id")
        if new_queue_id is None:
            return ticket.queue_id
        old_queue_id = ticket.queue_id
        actions = decision.get("actions") or {}
        custom = clear_routing_lock(ticket.custom_fields) if force_clear_lock else dict(ticket.custom_fields or {})
        request_template = _get_request_template(custom)
        if actions.get("approval_policy") and isinstance(actions.get("approval_policy"), dict):
            request_template["approval_policy"] = dict(actions["approval_policy"])
            custom["request_template"] = request_template

        priority_class = extract_priority_class(ticket)
        priority_boost = _as_int(actions.get("priority_boost"))
        if priority_boost is None:
            priority_boost = _as_int(actions.get("increase_priority_by")) or 0
        new_priority_class = _boost_priority(priority_class, priority_boost)
        new_priority_class = _minimum_priority(new_priority_class, actions.get("minimum_priority"))
        priority_update: dict[str, Any] = {}
        if new_priority_class != priority_class:
            custom["priority_class"] = new_priority_class
            priority_decision = custom.get("priority_decision")
            if isinstance(priority_decision, dict):
                priority_decision = dict(priority_decision)
                priority_decision["effective_priority"] = new_priority_class
                priority_decision["priority_class"] = new_priority_class
                priority_decision["legacy_priority"] = PRIORITY_CLASS_TO_LEGACY_PRIORITY[new_priority_class]
                priority_decision["priority_source"] = "routing_policy"
                priority_decision["priority_reason"] = (
                    str(priority_decision.get("priority_reason") or "").strip()
                    + f"; routing_policy priority_boost={priority_boost}"
                ).strip("; ")
                priority_decision["routing_priority_boost"] = priority_boost
                custom["priority_decision"] = priority_decision
            priority_update["priority"] = PRIORITY_CLASS_TO_LEGACY_PRIORITY[new_priority_class]

        suggested_playbook_id = str(
            actions.get("suggested_playbook_id") or actions.get("suggested_playbook") or ""
        ).strip() or None
        current_count = _routing_count(custom)
        auto_reroute_count = current_count + (0 if force_clear_lock else 1)
        routing_decision = {
            "source": decision.get("source"),
            "matched_rule": decision.get("matched_rule"),
            "actions": actions,
            "from_queue_id": old_queue_id,
            "to_queue_id": new_queue_id,
            "auto_reroute_count": auto_reroute_count,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
        if suggested_playbook_id:
            routing_decision["suggested_playbook_id"] = suggested_playbook_id
        for key in ("ola_policy_id", "watchers", "visibility"):
            if key in actions:
                routing_decision[key] = actions[key]
        custom[ROUTING_DECISION_KEY] = routing_decision

        updates: dict[str, Any] = {
            "queue_id": new_queue_id,
            "custom_fields": custom,
            "manual_rank": None,
            "manual_rank_updated_at": None,
            "manual_rank_updated_by": None,
            **priority_update,
        }
        assignee_id = actions.get("assignee_id")
        if assignee_id is not None:
            updates["assignee_id"] = str(assignee_id).strip() or None
        sla_policy_id = _as_int(actions.get("sla_policy_id"))
        if sla_policy_id is not None:
            updates["sla_policy_id"] = sla_policy_id
        merged_tags = _merge_tags(getattr(ticket, "tags", None), actions.get("tags"))
        if merged_tags is not None:
            updates["tags"] = merged_tags

        if new_queue_id == old_queue_id and not any(
            key in updates for key in ("priority", "sla_policy_id", "assignee_id", "tags")
        ):
            return new_queue_id
        await self.ticket_repo.update_ticket(ticket_id, **updates)
        if add_events_fn:
            await add_events_fn(
                ticket_id,
                device_id,
                "routing_applied",
                {
                    "from_queue_id": old_queue_id,
                    "to_queue_id": new_queue_id,
                    "routing_source": decision.get("source"),
                    "matched_rule": decision.get("matched_rule"),
                    "actions": actions,
                },
            )
            if new_queue_id != old_queue_id:
                await add_events_fn(
                    ticket_id,
                    device_id,
                    "queue_changed",
                    {"queue_id": new_queue_id, "previous_queue_id": old_queue_id},
                )
        logger.info(f"[Routing] Ticket {ticket_id} routed to queue_id={new_queue_id}")
        return new_queue_id
