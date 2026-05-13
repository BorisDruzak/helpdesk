from __future__ import annotations

import pytest

from tickets.policy_health_service import PolicyHealthService


pytestmark = pytest.mark.no_db


def _template(**overrides):
    data = {
        "template_code": "printer_repair",
        "version": "1",
        "public_title": "Printer repair",
        "ticket_type": "incident",
        "routing_policy_code": "printer_route",
        "sla_policy_code": "standard_sla",
        "ola_policy_code": "queue_ola",
        "approval_policy_code": None,
        "closure_policy_code": "default_closure",
        "visibility_policy_code": "safe_visibility",
        "notification_policy_code": None,
        "diagnostic_policy_code": None,
        "reporting_policy_code": None,
        "config": {"default_queue_code": "support"},
        "is_active": True,
        "published_at": "2026-05-13T00:00:00Z",
    }
    data.update(overrides)
    return data


def _policy(code: str, config: dict | None = None):
    return {"code": code, "title": code, "config": config or {}, "is_active": True}


def test_policy_health_reports_healthy_template() -> None:
    service = PolicyHealthService()

    dashboard = service.evaluate(
        templates=[_template()],
        policies={
            "routing": [_policy("printer_route", {"rules": [{"when": {"category": "printer"}, "then": {"queue_code": "support"}}]})],
            "sla": [_policy("standard_sla", {"pause_statuses": ["waiting_on_user"]})],
            "ola": [_policy("queue_ola", {"pause_statuses": ["waiting_on_vendor"]})],
            "closure": [_policy("default_closure")],
            "visibility": [_policy("safe_visibility", {"public_fields": ["ticket_code", "public_status"]})],
        },
        queues=[{"id": 1, "code": "support"}],
    )

    item = dashboard["templates"][0]
    assert item["health_status"] == "ok"
    assert item["conflict_count"] == 0
    assert item["issues_by_severity"]["critical"] == 0


def test_policy_health_detects_invalid_queue_approval_conflict_and_visibility_leak() -> None:
    service = PolicyHealthService()

    dashboard = service.evaluate(
        templates=[
            _template(
                approval_policy_code="approval_required",
                visibility_policy_code="leaky_visibility",
            )
        ],
        policies={
            "routing": [
                _policy(
                    "printer_route",
                    {
                        "rules": [
                            {"when": {}, "then": {"queue_code": "missing"}},
                            {"when": {"floor": 2}, "then": {"queue_code": "support"}},
                            {"when": {"floor": 2}, "then": {"queue_code": "other"}},
                        ]
                    },
                )
            ],
            "sla": [_policy("standard_sla", {"pause_statuses": ["not_waiting"]})],
            "ola": [_policy("queue_ola")],
            "approval": [_policy("approval_required", {"required": True, "approvers": []})],
            "closure": [_policy("default_closure")],
            "visibility": [_policy("leaky_visibility", {"public_fields": ["ticket_code", "requester_id"]})],
        },
        queues=[{"id": 1, "code": "support"}],
    )

    item = dashboard["templates"][0]
    assert item["health_status"] == "error"
    assert item["issues_by_severity"]["critical"] == 1
    assert item["conflict_count"] >= 2
    issue_kinds = {(issue["policy_kind"], issue["kind"]) for issue in item["issues"]}
    assert ("routing", "invalid_reference") in issue_kinds
    assert ("routing", "conflict") in issue_kinds
    assert ("approval", "invalid_reference") in issue_kinds
    assert ("visibility", "privacy_risk") in issue_kinds
    assert ("sla", "schema_error") in issue_kinds


def test_missing_sla_without_explicit_no_sla_marker_is_warning() -> None:
    service = PolicyHealthService()

    dashboard = service.evaluate(
        templates=[_template(sla_policy_code=None, config={"default_queue_code": "support"})],
        policies={
            "routing": [_policy("printer_route")],
            "ola": [_policy("queue_ola")],
            "closure": [_policy("default_closure")],
            "visibility": [_policy("safe_visibility")],
        },
        queues=[{"id": 1, "code": "support"}],
    )

    item = dashboard["templates"][0]
    assert item["health_status"] == "warning"
    assert ("sla", "missing_policy") in {
        (issue["policy_kind"], issue["kind"]) for issue in item["issues"]
    }
