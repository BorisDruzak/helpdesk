"""
Stage 9: Сервис валидации и оркестрации admin-config.
"""
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.db.models import TicketQueue, TicketRoutingRule, TicketSlaPolicy
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo


VALID_PRIORITIES = ("P1", "P2", "P3", "P4")
VALID_IMPACT_URGENCY = (1, 2, 3)


def validate_condition_json(condition: Optional[dict]) -> Tuple[bool, Optional[str]]:
    """
    Валидация condition_json для routing rule.
    Формат: {"field":"priority_class","op":"eq","value":"P1"} или {"and":[cond1,cond2]}.
    """
    if condition is None:
        return True, None
    if not isinstance(condition, dict):
        return False, "condition_json must be object or null"
    if "and" in condition:
        items = condition["and"]
        if not isinstance(items, list):
            return False, "condition_json.and must be array"
        for i, c in enumerate(items):
            ok, err = validate_condition_json(c)
            if not ok:
                return False, f"condition_json.and[{i}]: {err}"
        return True, None
    if "or" in condition:
        items = condition["or"]
        if not isinstance(items, list):
            return False, "condition_json.or must be array"
        for i, c in enumerate(items):
            ok, err = validate_condition_json(c)
            if not ok:
                return False, f"condition_json.or[{i}]: {err}"
        return True, None
    field = condition.get("field")
    op = condition.get("op")
    if field is None and op is None and "value" not in condition:
        return True, None
    valid_ops = ("eq", "ne", "in", "nin", "contains", "is_null")
    if op not in valid_ops:
        return False, f"condition_json.op must be one of {valid_ops}"
    if not isinstance(field, str) or not field.strip():
        return False, "condition_json.field must be non-empty string"
    return True, None


def validate_sla_targets(targets: List[dict]) -> Tuple[bool, Optional[str]]:
    """Валидация SLA targets: [{"priority":"P1","first_response_min":15,"resolution_min":240}]."""
    if not isinstance(targets, list) or len(targets) == 0:
        return False, "targets must be non-empty array"
    seen = set()
    for i, t in enumerate(targets):
        if not isinstance(t, dict):
            return False, f"targets[{i}] must be object"
        p = t.get("priority")
        if p not in VALID_PRIORITIES:
            return False, f"targets[{i}].priority must be one of {VALID_PRIORITIES}"
        if p in seen:
            return False, f"targets: duplicate priority {p}"
        seen.add(p)
        fr = t.get("first_response_min")
        res = t.get("resolution_min")
        if not isinstance(fr, int) or fr < 0:
            return False, f"targets[{i}].first_response_min must be non-negative integer"
        if not isinstance(res, int) or res < 0:
            return False, f"targets[{i}].resolution_min must be non-negative integer"
    return True, None


def validate_priority_matrix(matrix: List[dict]) -> Tuple[bool, Optional[str]]:
    """Валидация matrix: [{"impact":1,"urgency":1,"priority":"P4"}]."""
    if not isinstance(matrix, list) or len(matrix) == 0:
        return False, "matrix must be non-empty array"
    seen = set()
    for i, m in enumerate(matrix):
        if not isinstance(m, dict):
            return False, f"matrix[{i}] must be object"
        imp = m.get("impact")
        urg = m.get("urgency")
        p = m.get("priority")
        if imp not in VALID_IMPACT_URGENCY:
            return False, f"matrix[{i}].impact must be 1, 2, or 3"
        if urg not in VALID_IMPACT_URGENCY:
            return False, f"matrix[{i}].urgency must be 1, 2, or 3"
        if p not in VALID_PRIORITIES:
            return False, f"matrix[{i}].priority must be one of {VALID_PRIORITIES}"
        key = (imp, urg)
        if key in seen:
            return False, f"matrix: duplicate (impact,urgency) ({imp},{urg})"
        seen.add(key)
    return True, None


class AdminConfigService:
    """Оркестрация admin-config с валидацией и soft-deactivate guard rules."""

    def __init__(
        self,
        config_repo: TicketAdminConfigRepo,
        audit_repo: TicketAdminAuditRepo,
    ):
        self.config_repo = config_repo
        self.audit_repo = audit_repo

    def _serialize_queue(self, q: TicketQueue) -> dict:
        return {
            "id": q.id,
            "code": q.code,
            "name": q.name,
            "is_triage": q.is_triage,
            "is_active": q.is_active,
            "auto_assign_enabled": getattr(q, "auto_assign_enabled", True),
        }

    def _serialize_rule(self, r: TicketRoutingRule) -> dict:
        return {
            "id": r.id,
            "enabled": r.enabled,
            "priority_order": r.priority_order,
            "condition_json": r.condition_json,
            "target_queue_id": r.target_queue_id,
        }

    def _serialize_policy(self, p: TicketSlaPolicy) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "timezone": p.timezone,
            "business_hours_json": p.business_hours_json,
            "calendar_id": getattr(p, "calendar_id", None),
            "is_default": p.is_default,
            "is_active": getattr(p, "is_active", True),
        }

    async def can_deactivate_queue(self, queue_id: int) -> Tuple[bool, Optional[str]]:
        """Инвариант: нельзя деактивировать queue если есть open tickets или enabled routing rule."""
        open_count = await self.config_repo.count_open_tickets_in_queue(queue_id)
        if open_count > 0:
            return False, "Cannot deactivate queue: has open tickets"
        rules_count = await self.config_repo.count_enabled_rules_targeting_queue(queue_id)
        if rules_count > 0:
            return False, "Cannot deactivate queue: has enabled routing rules targeting it"
        return True, None

    async def can_deactivate_sla_policy(self, policy_id: int) -> Tuple[bool, Optional[str]]:
        """Инвариант: нельзя деактивировать default; нельзя если назначена open tickets."""
        p = await self.config_repo.get_sla_policy(policy_id)
        if not p:
            return False, "Policy not found"
        if getattr(p, "is_default", False):
            return False, "Cannot deactivate default SLA policy"
        open_count = await self.config_repo.count_open_tickets_with_policy(policy_id)
        if open_count > 0:
            return False, "Cannot deactivate SLA policy: assigned to open tickets"
        return True, None
