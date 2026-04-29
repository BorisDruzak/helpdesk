from __future__ import annotations

import pytest

from tickets.workflow_profiles import (
    DEFAULT_WORKFLOW_PROFILE,
    get_workflow_profile,
    list_workflow_profiles,
)


def test_workflow_profile_registry_exposes_required_ticket_types() -> None:
    profiles = {profile.ticket_type: profile for profile in list_workflow_profiles()}

    assert set(profiles) >= {
        "incident",
        "service_request",
        "access_request",
        "change_request",
        "consultation",
    }
    assert profiles["incident"].purpose == "restore_service"
    assert profiles["access_request"].requires_approval is True
    assert "waiting_on_approval" in profiles["access_request"].suggested_path
    assert profiles["change_request"].requires_change_plan is True
    assert profiles["consultation"].required_resolve_fields == ("public_summary",)


@pytest.mark.parametrize(
    ("ticket_type", "expected"),
    [
        ("incident", "incident"),
        ("access_request", "access_request"),
        ("", DEFAULT_WORKFLOW_PROFILE),
        ("unknown_legacy_kind", DEFAULT_WORKFLOW_PROFILE),
    ],
)
def test_get_workflow_profile_normalizes_unknown_ticket_type(ticket_type: str, expected: str) -> None:
    assert get_workflow_profile(ticket_type).ticket_type == expected
