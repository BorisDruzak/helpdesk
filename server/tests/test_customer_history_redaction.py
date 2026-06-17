from __future__ import annotations

import pytest

from customer_history.models import CustomerHistoryEvent
from customer_history.redaction import redact_for_llm, redact_for_requester


@pytest.mark.no_db
def test_customer_history_redaction_removes_sensitive_nested_values() -> None:
    event = CustomerHistoryEvent(
        event_id="evt-sensitive",
        source="ticket",
        group="chat",
        event_type="chat_message",
        title="Internal message",
        summary="Support checked the request",
        occurred_at="2026-06-17T09:00:00+00:00",
        ticket_id="ticket-secret",
        person_id="person-secret",
        device_id="device-secret",
        visibility={"requester": False, "support": True, "admin": True, "llm": True},
        payload={
            "text": "Safe summary",
            "password": "p@ssw0rd",
            "token": "raw-token",
            "cookie": "session-cookie",
            "authorization": "Bearer secret",
            "metadata_json": {"trace": "raw"},
            "headers": {"Authorization": "Bearer nested"},
            "trace_id": "trace-secret",
            "span_attrs": {"http.request.header.cookie": "raw"},
            "attachment": {"name": "large.bin", "content": "x" * 1000},
        },
    )

    llm = redact_for_llm(event, mode="preview")
    requester = redact_for_requester(event)

    serialized = str(llm)
    assert "p@ssw0rd" not in serialized
    assert "raw-token" not in serialized
    assert "session-cookie" not in serialized
    assert "Bearer" not in serialized
    assert "trace-secret" not in serialized
    assert "span_attrs" not in serialized
    assert "metadata_json" not in serialized
    assert requester is None
