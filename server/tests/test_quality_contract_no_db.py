from __future__ import annotations

import pytest

from quality.contracts import (
    ACTION_STATUSES,
    FEEDBACK_REASON_CODES,
    IMPROVEMENT_ACTION_TYPES,
    QUALITY_REVIEW_TYPES,
    REOPEN_REASON_CODES,
    requester_safe_quality_summary,
    validate_feedback_payload,
    validate_reopen_reason,
)


@pytest.mark.no_db
def test_quality_taxonomies_are_structured_and_stable() -> None:
    assert {"slow_response", "not_resolved", "knowledge_article_failed", "other"} <= FEEDBACK_REASON_CODES
    assert {"not_resolved", "problem_returned", "knowledge_article_failed", "other"} <= REOPEN_REASON_CODES
    assert {"low_csat", "reopened", "sla_breached", "negative_kb_feedback"} <= QUALITY_REVIEW_TYPES
    assert {"update_kb_article", "create_kb_article", "process_review", "other"} <= IMPROVEMENT_ACTION_TYPES
    assert {"open", "assigned", "in_progress", "blocked", "done", "dismissed"} <= ACTION_STATUSES


@pytest.mark.no_db
def test_feedback_payload_validation_requires_rating_and_known_reasons() -> None:
    valid = validate_feedback_payload(
        {
            "ticket_id": "ticket-1",
            "rating": 2,
            "problem_resolved": False,
            "reason_codes": ["not_resolved", "knowledge_article_failed"],
            "comment": "Problem returned after reboot",
            "source_surface": "requester_portal",
        }
    )

    assert valid["rating"] == 2
    assert valid["sentiment"] == "negative"
    assert valid["reason_codes"] == ["not_resolved", "knowledge_article_failed"]

    with pytest.raises(ValueError, match="rating"):
        validate_feedback_payload({"ticket_id": "ticket-1", "rating": 6})
    with pytest.raises(ValueError, match="reason_codes"):
        validate_feedback_payload({"ticket_id": "ticket-1", "rating": 4, "reason_codes": ["raw_internal"]})


@pytest.mark.no_db
def test_reopen_other_requires_comment() -> None:
    assert validate_reopen_reason("problem_returned", None) == "problem_returned"

    with pytest.raises(ValueError, match="reason_comment"):
        validate_reopen_reason("other", "")


@pytest.mark.no_db
def test_requester_safe_quality_summary_redacts_internal_fields() -> None:
    payload = requester_safe_quality_summary(
        {
            "latest_feedback": {"rating": 2, "comment": "not fixed", "requester_id": "user-secret"},
            "qa_reviews": [{"review_id": "qr-1", "review_notes": "internal root cause", "queue_id": 5}],
            "improvement_actions": [{"action_id": "ia-1", "owner_actor_id": "manager"}],
            "reopen_available": True,
        }
    )

    text = repr(payload)
    assert payload["latest_feedback"]["rating"] == 2
    assert payload["reopen_available"] is True
    assert "qa_reviews" not in payload
    assert "improvement_actions" not in payload
    assert "requester_id" not in text
    assert "internal root cause" not in text
    assert "queue_id" not in text
