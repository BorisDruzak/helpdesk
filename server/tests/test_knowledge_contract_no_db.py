from __future__ import annotations

from typing import Any

import pytest

from knowledge.contracts import (
    KNOWLEDGE_BODY_FORMATS,
    KNOWLEDGE_FEEDBACK_EVENT_TYPES,
    KNOWLEDGE_ITEM_STATUSES,
    KNOWLEDGE_ITEM_TYPES,
    KNOWLEDGE_RELATION_TYPES,
    KNOWLEDGE_SAFE_PROJECTION_FORBIDDEN_KEYS,
    KNOWLEDGE_VISIBILITIES,
    KnowledgeValidationError,
    can_transition_item_status,
    normalize_knowledge_slug,
    sanitize_requester_knowledge_projection,
)


pytestmark = pytest.mark.no_db


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in KNOWLEDGE_SAFE_PROJECTION_FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def test_knowledge_contract_enums_are_universal_not_article_only() -> None:
    assert KNOWLEDGE_ITEM_TYPES == (
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
    assert KNOWLEDGE_ITEM_STATUSES == ("draft", "in_review", "published", "needs_review", "archived")
    assert KNOWLEDGE_VISIBILITIES == (
        "public",
        "requester",
        "agent_requester_safe",
        "support_internal",
        "admin_internal",
        "security_restricted",
        "auditor_read",
    )
    assert KNOWLEDGE_BODY_FORMATS == ("markdown", "html", "plain_text", "json", "structured_steps")
    assert "deflected" in KNOWLEDGE_FEEDBACK_EVENT_TYPES
    assert "has_workaround" in KNOWLEDGE_RELATION_TYPES


def test_normalize_knowledge_slug_is_stable_and_rejects_unsafe_values() -> None:
    assert normalize_knowledge_slug(" VPN Reconnect ") == "vpn-reconnect"
    assert normalize_knowledge_slug("known_error_502") == "known_error_502"

    with pytest.raises(KnowledgeValidationError):
        normalize_knowledge_slug("")
    with pytest.raises(KnowledgeValidationError):
        normalize_knowledge_slug("../secret")


def test_item_lifecycle_requires_review_before_publish() -> None:
    assert can_transition_item_status("draft", "in_review")
    assert can_transition_item_status("in_review", "published")
    assert can_transition_item_status("published", "needs_review")
    assert can_transition_item_status("needs_review", "in_review")
    assert can_transition_item_status("published", "archived")
    assert not can_transition_item_status("draft", "published")
    assert not can_transition_item_status("archived", "published")


def test_requester_safe_projection_strips_internal_knowledge_fields_recursively() -> None:
    raw = {
        "item_id": "item-1",
        "slug": "vpn-reconnect",
        "type": "article",
        "title": "Как переподключить VPN",
        "summary": "Пошаговая инструкция",
        "snippet": "Отключите и снова включите VPN.",
        "visibility": "requester",
        "version_id": "version-1",
        "source_ticket_id": "ticket-secret",
        "source_passport_id": 10,
        "device_id": "device-secret",
        "requester_id": "requester-secret",
        "custom_fields": {"token": "secret"},
        "raw_chunks": [{"chunk_id": "chunk-1", "text": "internal chunk"}],
        "graph": {"internal_rule_id": "edge-secret"},
        "metadata_json": {"trace_id": "trace-secret"},
    }

    safe = sanitize_requester_knowledge_projection(raw)

    assert _forbidden_paths(safe) == []
    assert safe == {
        "item_id": "item-1",
        "slug": "vpn-reconnect",
        "type": "article",
        "title": "Как переподключить VPN",
        "summary": "Пошаговая инструкция",
        "snippet": "Отключите и снова включите VPN.",
        "visibility": "requester",
        "version_id": "version-1",
    }
