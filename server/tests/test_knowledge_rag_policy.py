from __future__ import annotations

import pytest

from knowledge.rag_policy import evaluate_rag_eligibility, safe_rag_trace_item

pytestmark = pytest.mark.no_db


def test_rag_policy_staff_only_denies_requester_and_redacts_excluded_trace() -> None:
    item = {
        "item_id": "item-staff-only",
        "slug": "staff-secret",
        "title": "Staff secret article",
        "visibility": "requester",
        "metadata": {"ai_rag_policy": "staff_only"},
    }

    decision = evaluate_rag_eligibility(item, {"allow_rag": True}, actor_role="requester")

    assert decision.allowed is False
    assert decision.reason_code == "article_rag_staff_only"
    trace = safe_rag_trace_item(item, decision, included=False)
    assert trace == {
        "item_id": "item-staff-only",
        "included": False,
        "reason_code": "article_rag_staff_only",
        "policy": "staff_only",
        "section_allow_rag": True,
        "requester_safe": True,
    }
    assert "slug" not in trace
    assert "title" not in trace


def test_rag_policy_requester_safe_only_denies_support_internal_and_redacts_trace() -> None:
    item = {
        "item_id": "item-support-internal",
        "slug": "support-internal-runbook",
        "title": "Support internal runbook",
        "visibility": "support_internal",
        "metadata_json": {"ai_rag_policy": "requester_safe_only"},
    }

    decision = evaluate_rag_eligibility(item, {"allow_rag": True}, actor_role="support")

    assert decision.allowed is False
    assert decision.reason_code == "article_rag_requester_safe_only"
    trace = safe_rag_trace_item(item, decision, included=False)
    assert trace["item_id"] == "item-support-internal"
    assert trace["included"] is False
    assert trace["requester_safe"] is False
    assert "slug" not in trace
    assert "title" not in trace


def test_rag_policy_allowed_privileged_trace_can_include_safe_identifier_fields() -> None:
    item = {
        "item_id": "item-allowed",
        "slug": "allowed-rag",
        "title": "Allowed RAG article",
        "visibility": "support_internal",
        "metadata": {"ai_rag_policy": "staff_only"},
    }

    decision = evaluate_rag_eligibility(item, {"allow_rag": True}, actor_role="support")

    assert decision.allowed is True
    assert decision.reason_code == "rag_allowed"
    trace = safe_rag_trace_item(item, decision, included=True)
    assert trace["included"] is True
    assert trace["slug"] == "allowed-rag"
    assert trace["title"] == "Allowed RAG article"
