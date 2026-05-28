from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_db


def test_requester_visibility_redacts_nested_fields_and_keeps_support_preview_metadata():
    from tickets.visibility_policy import apply_ticket_visibility_payload

    ticket = SimpleNamespace(
        status="waiting_on_approval",
        requester_status="in_work",
        custom_fields={
            "request_template": {
                "visibility_policy": {
                    "public_status_mapping": {
                        "waiting_on_approval": {"status": "in_work", "label": "Заявка в работе"}
                    },
                    "hide_from_requester": [
                        "custom_fields.internal_cost",
                        "passport.sections.internal_result",
                        "raw_diagnostics",
                        "ola_details",
                    ],
                    "show_to_requester": ["public_status", "expected_due_at", "custom_fields.public_scope"],
                    "show_to_support": ["internal_notes", "ola_details", "raw_diagnostics"],
                }
            }
        },
    )
    payload = {
        "custom_fields": {"internal_cost": "100", "public_scope": "department"},
        "passport": {
            "sections": {
                "internal_result": "operator only",
                "user_result": "available",
            }
        },
        "raw_diagnostics": {"trace": "internal"},
        "ola_details": {"ack_due_at": "2026-05-03T10:00:00"},
        "expected_due_at": "2026-05-04T10:00:00",
    }

    requester_payload = apply_ticket_visibility_payload(ticket, payload, visibility="requester")
    support_payload = apply_ticket_visibility_payload(ticket, payload, visibility="support")

    assert requester_payload["public_status"] == "in_work"
    assert requester_payload["public_status_label"] == "Заявка в работе"
    assert requester_payload["custom_fields"] == {"public_scope": "department"}
    assert requester_payload["passport"]["sections"] == {"user_result": "available"}
    assert "raw_diagnostics" not in requester_payload
    assert "ola_details" not in requester_payload
    assert requester_payload["requester_visible_fields"] == [
        "public_status",
        "expected_due_at",
        "custom_fields.public_scope",
    ]
    assert requester_payload["support_visible_fields"] == ["internal_notes", "ola_details", "raw_diagnostics"]

    assert support_payload["custom_fields"]["internal_cost"] == "100"
    assert support_payload["passport"]["sections"]["internal_result"] == "operator only"
    assert support_payload["raw_diagnostics"] == {"trace": "internal"}
    assert support_payload["visibility"]["hidden_from_requester"]


def test_public_visibility_redacts_passport_export_sections_from_policy_shape():
    from tickets.visibility_policy import apply_ticket_visibility_payload

    ticket = SimpleNamespace(
        status="resolved",
        requester_status="review_solution",
        custom_fields={
            "request_template": {
                "visibility_policy": {
                    "hide_from_requester": ["passport.sections.operator_checks", "passport.sections.internal_result"],
                    "show_to_requester": ["passport.sections.user_result"],
                }
            }
        },
    )

    payload = {
        "passport": {
            "sections": {
                "problem": "Website unavailable",
                "operator_checks": "curl from L2 host",
                "internal_result": "changed DNS route",
                "user_result": "Site opens",
            }
        }
    }

    requester_payload = apply_ticket_visibility_payload(ticket, payload, visibility="public")

    assert requester_payload["passport"]["sections"] == {
        "problem": "Website unavailable",
        "user_result": "Site opens",
    }


def test_requester_visibility_uses_ticket_payload_allowlist():
    from tickets.visibility_policy import apply_ticket_visibility_payload

    ticket = SimpleNamespace(status="queued", requester_status="accepted", custom_fields={})
    payload = {
        "ticket_id": "ticket-1",
        "ticket_code": "T-1",
        "title": "Printer issue",
        "description": "Cannot print",
        "status": "queued",
        "requester_status": "accepted",
        "requester_status_label": "Accepted",
        "public_status": "accepted",
        "public_status_label": "Accepted",
        "queue_code": "servicedesk_l1",
        "queue_id": 1,
        "device_id": "device-1",
        "assignee_id": "support-1",
        "requester_id": "requester-1",
        "priority": "P1",
        "priority_decision": {"routing": "internal"},
        "custom_fields": {
            "public_access": {"code_hash": "secret-hash"},
            "routing_decision": {"to_queue_id": 1},
        },
        "visibility": {"source": "default", "hidden_from_requester": ["custom_fields"]},
    }

    requester_payload = apply_ticket_visibility_payload(ticket, payload, visibility="requester")

    assert requester_payload["ticket_id"] == "ticket-1"
    assert requester_payload["queue_code"] == "servicedesk_l1"
    assert requester_payload["visibility"] == {"source": "default", "requester_safe": True}
    for forbidden in (
        "queue_id",
        "device_id",
        "assignee_id",
        "requester_id",
        "priority",
        "priority_decision",
        "custom_fields",
    ):
        assert forbidden not in requester_payload
