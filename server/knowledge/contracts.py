from __future__ import annotations

import re
from typing import Any


KNOWLEDGE_ITEM_TYPES: tuple[str, ...] = (
    "article",
    "faq",
    "runbook",
    "policy",
    "document",
    "known_error",
    "workaround",
    "troubleshooting_tree",
    "glossary_term",
    "service_description",
    "external_source",
    "resolution_draft",
)

KNOWLEDGE_ITEM_STATUSES: tuple[str, ...] = ("draft", "in_review", "published", "needs_review", "archived")

KNOWLEDGE_SPACE_STATUSES: tuple[str, ...] = ("draft", "active", "archived")

KNOWLEDGE_VISIBILITIES: tuple[str, ...] = (
    "public",
    "requester",
    "agent_requester_safe",
    "support_internal",
    "admin_internal",
    "security_restricted",
    "auditor_read",
)

KNOWLEDGE_BODY_FORMATS: tuple[str, ...] = ("markdown", "html", "plain_text", "json", "structured_steps")

KNOWLEDGE_SOURCE_KINDS: tuple[str, ...] = (
    "manual",
    "ticket_passport",
    "imported_document",
    "ticket_resolution",
    "external_url",
    "agent_diagnostic",
)

KNOWLEDGE_FEEDBACK_EVENT_TYPES: tuple[str, ...] = (
    "suggested",
    "viewed",
    "helpful",
    "not_helpful",
    "deflected",
    "ticket_created_after_view",
    "support_linked",
    "support_used",
    "draft_created",
    "published",
    "archived",
)

KNOWLEDGE_INGESTION_STATUSES: tuple[str, ...] = (
    "queued",
    "parsing",
    "chunking",
    "indexing",
    "review_required",
    "completed",
    "failed",
    "canceled",
)

KNOWLEDGE_INGESTION_SOURCE_KINDS: tuple[str, ...] = (
    "manual_upload",
    "text",
    "markdown",
    "html",
    "pdf",
    "docx",
    "external_url",
    "ticket_passport",
    "git_repo",
    "api",
)

KNOWLEDGE_NODE_TYPES: tuple[str, ...] = (
    "knowledge_item",
    "article",
    "known_error",
    "workaround",
    "glossary_term",
    "service",
    "offering",
    "ticket",
    "asset",
    "registry_service",
    "diagnostic_playbook",
    "external_entity",
    "concept",
    "document",
)

KNOWLEDGE_GRAPH_STATUSES: tuple[str, ...] = ("proposed", "confirmed", "rejected", "archived")

KNOWLEDGE_RELATION_TYPES: tuple[str, ...] = (
    "explains",
    "causes",
    "caused_by",
    "depends_on",
    "affects",
    "affected_by",
    "has_workaround",
    "has_permanent_fix",
    "requires",
    "replaces",
    "duplicates",
    "similar_to",
    "belongs_to_service",
    "belongs_to_offering",
    "suggested_for",
    "tried_in_ticket",
    "resolved_by",
    "source_of",
    "mentions",
    "synonym_of",
    "contradicts",
    "supersedes",
)

REQUESTER_SAFE_VISIBILITIES: tuple[str, ...] = ("public", "requester", "agent_requester_safe")

SUPPORT_VISIBLE_VISIBILITIES: tuple[str, ...] = REQUESTER_SAFE_VISIBILITIES + ("support_internal",)

AUDITOR_VISIBLE_VISIBILITIES: tuple[str, ...] = SUPPORT_VISIBLE_VISIBILITIES + ("auditor_read",)

ADMIN_VISIBLE_VISIBILITIES: tuple[str, ...] = KNOWLEDGE_VISIBILITIES

KNOWLEDGE_ACTOR_ROLES: tuple[str, ...] = (
    "public",
    "requester",
    "user",
    "agent",
    "support",
    "admin",
    "auditor",
    "security",
)

KNOWLEDGE_SAFE_PROJECTION_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "internal_body",
        "support_internal",
        "admin_internal",
        "security_restricted",
        "raw_source_refs",
        "source_refs",
        "source_ticket_id",
        "source_passport_id",
        "requester_id",
        "device_id",
        "custom_fields",
        "raw_custom_fields",
        "internal_graph_edges",
        "queue_id",
        "policy_id",
        "policy_refs",
        "trace_id",
        "operation_id",
        "confidence_score",
        "extraction_metadata",
        "metadata_json",
        "raw_chunks",
        "chunk_text",
        "internal_rule_id",
        "route_rule_id",
    }
)

SAFE_REQUESTER_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "item_id",
        "slug",
        "type",
        "item_type",
        "title",
        "summary",
        "snippet",
        "visibility",
        "version_id",
        "actions",
        "reason",
    }
)


class KnowledgeValidationError(ValueError):
    """Raised when knowledge platform input violates the public contract."""


class KnowledgePublicationBlockedError(KnowledgeValidationError):
    """Raised when a knowledge item fails publish governance gates."""

    def __init__(self, blockers: list[dict[str, str]]):
        details = "; ".join(str(blocker.get("message") or blocker.get("code") or "blocked") for blocker in blockers)
        super().__init__(details or "knowledge publish blocked")
        self.blockers = blockers


def normalize_knowledge_slug(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    text = re.sub(r"-+", "-", text)
    if not text or not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,118}[a-z0-9])?", text):
        raise KnowledgeValidationError("knowledge slug must be lowercase ascii, dash/underscore safe")
    if ".." in text or "/" in text or "\\" in text:
        raise KnowledgeValidationError("knowledge slug must not contain path separators")
    return text


def can_transition_item_status(current_status: str, target_status: str) -> bool:
    transitions: dict[str, set[str]] = {
        "draft": {"in_review", "archived"},
        "in_review": {"draft", "published", "archived"},
        "published": {"needs_review", "archived"},
        "needs_review": {"in_review", "archived"},
        "archived": set(),
    }
    return target_status in transitions.get(str(current_status or ""), set())


def actor_visible_visibilities(actor_role: str | None) -> tuple[str, ...]:
    role = str(actor_role or "requester").lower()
    if role in {"admin", "security"}:
        return ADMIN_VISIBLE_VISIBILITIES
    if role == "auditor":
        return AUDITOR_VISIBLE_VISIBILITIES
    if role == "support":
        return SUPPORT_VISIBLE_VISIBILITIES
    return REQUESTER_SAFE_VISIBILITIES


def can_read_knowledge_visibility(actor_role: str | None, visibility: str | None) -> bool:
    return str(visibility or "") in set(actor_visible_visibilities(actor_role))


def can_mutate_knowledge_visibility(actor_role: str | None, visibility: str | None) -> bool:
    role = str(actor_role or "").lower()
    if role in {"admin", "security"}:
        return str(visibility or "") in set(ADMIN_VISIBLE_VISIBILITIES)
    if role == "support":
        return str(visibility or "") in set(SUPPORT_VISIBLE_VISIBILITIES)
    return False


def sanitize_requester_knowledge_projection(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, child in value.items():
            if key in KNOWLEDGE_SAFE_PROJECTION_FORBIDDEN_KEYS:
                continue
            if key not in SAFE_REQUESTER_ITEM_KEYS:
                continue
            target_key = "type" if key == "item_type" else key
            safe[target_key] = sanitize_requester_knowledge_projection(child)
        return safe
    if isinstance(value, list):
        return [sanitize_requester_knowledge_projection(item) for item in value]
    return value
