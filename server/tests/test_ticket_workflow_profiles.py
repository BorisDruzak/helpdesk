from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket
from tickets.workflow_service import validate_transition_for_ticket

from tickets.workflow_profiles import (
    DEFAULT_WORKFLOW_PROFILE,
    get_workflow_profile,
    list_workflow_profiles,
    save_workflow_profiles,
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


@pytest.mark.asyncio
async def test_configured_workflow_profile_controls_ticket_transitions(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident custom",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "waiting_on_approval", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "waiting_on_approval", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["waiting_on_approval", "canceled"],
                            "waiting_on_approval": ["in_progress", "canceled"],
                            "in_progress": ["resolved", "canceled"],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        ticket = Ticket(
            ticket_id="00000000-0000-0000-0000-00000000wf01",
            device_id="device-workflow",
            title="Workflow transition",
            description="Configured transition check",
            status="new",
            requester_id="requester",
            ticket_type="incident",
        )
        session.add(ticket)
        await session.commit()

        assert await validate_transition_for_ticket(session, ticket, "waiting_on_approval", True)
        assert not await validate_transition_for_ticket(session, ticket, "queued", True)
