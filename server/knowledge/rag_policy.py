from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUESTER_SAFE_VISIBILITIES = {"public", "requester", "agent_requester_safe"}
EXPLAIN_RAG_POLICY_ROLES = {"admin", "support", "auditor", "security"}
STAFF_RAG_POLICY_ROLES = {"admin", "support"}


@dataclass(frozen=True)
class RagEligibilityDecision:
    allowed: bool
    policy: str
    reason_code: str
    section_allow_rag: bool
    requester_safe: bool


def _mapping_or_attrs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key in ("item_id", "slug", "title", "metadata_json", "metadata", "allow_rag", "visibility"):
        if hasattr(value, key):
            result[key] = getattr(value, key)
    return result


def _metadata(value: Any) -> dict[str, Any]:
    payload = _mapping_or_attrs(value)
    metadata = payload.get("metadata_json")
    if not isinstance(metadata, dict):
        metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _normalize_policy(value: Any) -> str:
    policy = str(value or "inherit").strip().lower()
    aliases = {
        "": "inherit",
        "default": "inherit",
        "section_default": "inherit",
        "section": "inherit",
        "enabled": "allowed",
        "allow": "allowed",
        "true": "allowed",
        "deny": "disabled",
        "false": "disabled",
        "off": "disabled",
        "admin_support_only": "staff_only",
        "support_only": "staff_only",
        "requester_safe": "requester_safe_only",
    }
    policy = aliases.get(policy, policy)
    if policy not in {"inherit", "allowed", "disabled", "staff_only", "requester_safe_only"}:
        return "inherit"
    return policy


def article_rag_policy(item: Any) -> str:
    metadata = _metadata(item)
    return _normalize_policy(metadata.get("ai_rag_policy", metadata.get("rag_policy")))


def evaluate_rag_eligibility(item: Any, space: Any | None, *, actor_role: str) -> RagEligibilityDecision:
    item_payload = _mapping_or_attrs(item)
    space_payload = _mapping_or_attrs(space or {})
    visibility = str(item_payload.get("visibility") or "")
    requester_safe = visibility in REQUESTER_SAFE_VISIBILITIES
    section_allow_rag = bool(space_payload.get("allow_rag"))
    policy = article_rag_policy(item)
    role = str(actor_role or "").lower()

    if policy == "disabled":
        return RagEligibilityDecision(False, policy, "article_rag_disabled", section_allow_rag, requester_safe)
    if policy == "staff_only" and role not in STAFF_RAG_POLICY_ROLES:
        return RagEligibilityDecision(False, policy, "article_rag_staff_only", section_allow_rag, requester_safe)
    if policy == "requester_safe_only" and not requester_safe:
        return RagEligibilityDecision(False, policy, "article_rag_requester_safe_only", section_allow_rag, requester_safe)
    if policy == "inherit" and not section_allow_rag:
        return RagEligibilityDecision(False, policy, "section_rag_disabled", section_allow_rag, requester_safe)
    return RagEligibilityDecision(True, policy, "rag_allowed", section_allow_rag, requester_safe)


def safe_rag_trace_item(
    item: Any,
    decision: RagEligibilityDecision,
    *,
    included: bool,
) -> dict[str, Any]:
    payload = _mapping_or_attrs(item)
    trace = {
        "item_id": payload.get("item_id"),
        "included": included,
        "reason_code": decision.reason_code,
        "policy": decision.policy,
        "section_allow_rag": decision.section_allow_rag,
        "requester_safe": decision.requester_safe,
    }
    if included:
        trace["slug"] = payload.get("slug")
        trace["title"] = payload.get("title")
    return trace
