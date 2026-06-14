from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.contracts import can_read_knowledge_visibility


REQUESTER_LIKE_ROLES = {"public", "requester", "user", "agent"}
PRIVILEGED_ROLES = {"support", "admin", "security", "auditor"}
RULE_TARGET_TYPES = {
    "person",
    "department",
    "department_tree",
    "location",
    "access_group",
    "audience_group",
    "role",
    "service",
}


@dataclass(frozen=True, slots=True)
class KnowledgeAccessDecision:
    allowed: bool
    reason_code: str
    matched_rule_ids: list[str] = field(default_factory=list)

    def safe_denial_payload(self) -> dict[str, Any]:
        if self.allowed:
            return {"allowed": True, "reason_code": self.reason_code}
        return {"allowed": False, "reason_code": self.reason_code}


class KnowledgeAccessService:
    @staticmethod
    def evaluate_item_access(
        *,
        item: dict[str, Any],
        space: dict[str, Any] | None,
        audience: Any,
        rules: list[dict[str, Any]],
        service_context: dict[str, Any] | None = None,
    ) -> KnowledgeAccessDecision:
        role = _audience_role(audience)
        if space is not None and str(space.get("lifecycle_status") or "active") != "active":
            return KnowledgeAccessDecision(allowed=False, reason_code="space_not_active")
        if str(item.get("status") or "") != "published":
            return KnowledgeAccessDecision(allowed=False, reason_code="item_not_published")
        if not item.get("current_version_id"):
            return KnowledgeAccessDecision(allowed=False, reason_code="current_version_missing")
        if not can_read_knowledge_visibility(role, item.get("visibility")):
            return KnowledgeAccessDecision(allowed=False, reason_code="coarse_visibility_denied")
        if space is not None and not can_read_knowledge_visibility(role, space.get("visibility")):
            return KnowledgeAccessDecision(allowed=False, reason_code="space_visibility_denied")

        active_rules = _subject_rules(item=item, space=space, rules=rules)
        if not active_rules:
            return KnowledgeAccessDecision(allowed=True, reason_code="no_audience_rules")
        if role in PRIVILEGED_ROLES:
            return KnowledgeAccessDecision(allowed=True, reason_code="privileged_actor_override")

        matched_rule_ids = [
            str(rule.get("rule_id") or "")
            for rule in active_rules
            if _rule_matches(rule, audience=audience, service_context=service_context)
        ]
        matched_rule_ids = [rule_id for rule_id in matched_rule_ids if rule_id]
        if matched_rule_ids:
            return KnowledgeAccessDecision(
                allowed=True,
                reason_code="audience_rule_matched",
                matched_rule_ids=matched_rule_ids,
            )
        return KnowledgeAccessDecision(allowed=False, reason_code="audience_rule_not_matched")

    @staticmethod
    def filter_authorized_items(
        *,
        items: list[dict[str, Any]],
        spaces_by_id: dict[str, dict[str, Any]],
        audience: Any,
        rules: list[dict[str, Any]],
        service_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for item in items:
            decision = KnowledgeAccessService.evaluate_item_access(
                item=item,
                space=spaces_by_id.get(str(item.get("space_id") or "")),
                audience=audience,
                rules=rules,
                service_context=service_context,
            )
            if decision.allowed:
                filtered.append(item)
        return filtered


def _audience_role(audience: Any) -> str:
    if isinstance(audience, dict):
        return str(audience.get("actor_role") or "requester").lower()
    return str(getattr(audience, "actor_role", None) or "requester").lower()


def _audience_person_id(audience: Any) -> str | None:
    if isinstance(audience, dict):
        value = audience.get("person_id")
    else:
        value = getattr(audience, "person_id", None)
    text = str(value or "").strip()
    return text or None


def _audience_department_values(audience: Any) -> set[str]:
    path = audience.get("department_path") if isinstance(audience, dict) else getattr(audience, "department_path", [])
    values: set[str] = set()
    for item in path or []:
        if isinstance(item, dict):
            candidates = (
                item.get("department_id"),
                item.get("id"),
                item.get("code"),
                item.get("department_code"),
            )
        else:
            candidates = (item,)
        values.update(_normalize_token(value) for value in candidates if _normalize_token(value))
    return values


def _audience_location_values(audience: Any) -> set[str]:
    location = audience.get("location") if isinstance(audience, dict) else getattr(audience, "location", None)
    values: set[str] = set()
    if isinstance(location, dict):
        candidates = (
            location.get("location_id"),
            location.get("id"),
            location.get("code"),
            location.get("location_code"),
        )
    else:
        candidates = (location,)
    values.update(_normalize_token(value) for value in candidates if _normalize_token(value))
    return values


def _audience_list_values(audience: Any, field_name: str) -> set[str]:
    values = audience.get(field_name) if isinstance(audience, dict) else getattr(audience, field_name, [])
    return {_normalize_token(value) for value in values or [] if _normalize_token(value)}


def _subject_rules(
    *,
    item: dict[str, Any],
    space: dict[str, Any] | None,
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    item_id = str(item.get("item_id") or "")
    space_id = str((space or {}).get("space_id") or item.get("space_id") or "")
    active: list[dict[str, Any]] = []
    for rule in rules:
        if str(rule.get("status") or "active") != "active":
            continue
        if str(rule.get("effect") or "allow") != "allow":
            continue
        target_type = str(rule.get("target_type") or "")
        if target_type not in RULE_TARGET_TYPES:
            continue
        subject_type = str(rule.get("subject_type") or "")
        subject_id = str(rule.get("subject_id") or "")
        if (subject_type == "item" and subject_id == item_id) or (subject_type == "space" and subject_id == space_id):
            active.append(rule)
    return active


def _rule_matches(
    rule: dict[str, Any],
    *,
    audience: Any,
    service_context: dict[str, Any] | None,
) -> bool:
    target_type = str(rule.get("target_type") or "")
    target_id = _normalize_token(rule.get("target_id"))
    if not target_id:
        return False
    if target_type == "role":
        return target_id == _normalize_token(_audience_role(audience))
    if target_type == "person":
        return target_id == _normalize_token(_audience_person_id(audience))
    if target_type in {"department", "department_tree"}:
        return target_id in _audience_department_values(audience)
    if target_type == "location":
        return target_id in _audience_location_values(audience)
    if target_type == "access_group":
        return target_id in _audience_list_values(audience, "access_groups")
    if target_type == "audience_group":
        return target_id in _audience_list_values(audience, "audience_groups")
    if target_type == "service":
        return target_id in _service_context_values(service_context)
    return False


def _service_context_values(service_context: dict[str, Any] | None) -> set[str]:
    if not isinstance(service_context, dict):
        return set()
    keys = ("service_code", "offering_code", "request_template_key")
    return {_normalize_token(service_context.get(key)) for key in keys if _normalize_token(service_context.get(key))}


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()
