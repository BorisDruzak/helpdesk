from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketApproval, TicketEvidenceItem
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.workflow_service import TicketWorkflowService, validate_transition_for_ticket

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


@pytest.mark.asyncio
async def test_workflow_profile_accepts_structured_transition_gates(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        profiles = await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident gated",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "in_progress": [
                                {
                                    "to": "resolved",
                                    "allowed_roles": ["admin"],
                                    "required_fields": ["resolution_code"],
                                },
                                "canceled",
                            ],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )

        incident = {profile.ticket_type: profile for profile in profiles}["incident"]
        assert incident.transitions["in_progress"] == ("resolved", "canceled")
        assert incident.transition_gates["in_progress"]["resolved"].allowed_roles == ("admin",)
        assert incident.transition_gates["in_progress"]["resolved"].required_fields == ("resolution_code",)


@pytest.mark.asyncio
async def test_workflow_profile_accepts_advanced_transition_guards_and_actions(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        profiles = await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident guarded actions",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "in_progress": [
                                {
                                    "to": "resolved",
                                    "required_comment": "public",
                                    "require_approval": True,
                                    "require_evidence": True,
                                    "actions": {
                                        "notify": ["assignee", "queue_lead"],
                                        "sla": "pause",
                                    },
                                }
                            ],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )

        incident = {profile.ticket_type: profile for profile in profiles}["incident"]
        gate = incident.transition_gates["in_progress"]["resolved"]

        assert gate.required_comment == "public"
        assert gate.require_approval is True
        assert gate.require_evidence is True
        assert gate.notify == ("assignee", "queue_lead")
        assert gate.sla_action == "pause"
        assert gate.to_dict() == {
            "to": "resolved",
            "required_comment": "public",
            "require_approval": True,
            "require_evidence": True,
            "actions": {
                "notify": ["assignee", "queue_lead"],
                "sla": "pause",
            },
        }


async def _seed_gated_workflow_ticket(test_engine) -> str:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf02"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident gated",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "in_progress": [
                                {
                                    "to": "resolved",
                                    "allowed_roles": ["admin"],
                                    "required_fields": ["resolution_code"],
                                },
                                "canceled",
                            ],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-gates",
                title="Workflow gates",
                description="Configured transition gate check",
                status="in_progress",
                requester_id="requester",
                assignee_id="support-test",
                ticket_type="incident",
            )
        )
        await session.commit()
    return ticket_id


async def _seed_advanced_gated_workflow_ticket(test_engine) -> str:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf03"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident guarded actions",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "in_progress": [
                                {
                                    "to": "resolved",
                                    "required_fields": ["resolution_code"],
                                    "required_comment": "public",
                                    "require_approval": True,
                                    "require_evidence": True,
                                    "actions": {
                                        "notify": ["assignee", "queue_lead"],
                                        "sla": "pause",
                                    },
                                }
                            ],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-advanced-gates",
                title="Workflow advanced gates",
                description="Configured transition guard and action check",
                status="in_progress",
                requester_id="requester",
                assignee_id="support-test",
                ticket_type="incident",
            )
        )
        await session.commit()
    return ticket_id


async def _resolve_gated_ticket(
    test_engine,
    ticket_id: str,
    *,
    actor_id: str = "support-test",
    actor_role: str = "support",
    resolution_code: str | None = None,
) -> dict:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="resolved",
            actor_id=actor_id,
            actor_role=actor_role,
            reason="workflow_gate_check",
            resolution_code=resolution_code,
            source="test",
        )
        await session.commit()
        return result


async def _resolve_advanced_gated_ticket(
    test_engine,
    ticket_id: str,
    *,
    public_comment: str | None = None,
) -> dict:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="resolved",
            actor_id="support-test",
            actor_role="support",
            reason="workflow_gate_check",
            resolution_code="fixed_remote",
            public_comment=public_comment,
            source="test",
        )
        await session.commit()
        return result


async def _attach_advanced_gate_evidence_and_approval(test_engine, ticket_id: str) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="manual",
                title="Resolution proof",
                summary="Operator attached proof before transition",
                visibility="internal",
                created_by="support-test",
            )
        )
        session.add(
            TicketApproval(
                ticket_id=ticket_id,
                approval_type="workflow_transition",
                approver_id="lead-test",
                status="approved",
                requested_by="support-test",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_workflow_transition_gate_requires_configured_fields(test_engine) -> None:
    ticket_id = await _seed_gated_workflow_ticket(test_engine)

    with pytest.raises(ValueError, match="required_fields.*resolution_code"):
        await _resolve_gated_ticket(test_engine, ticket_id, actor_id="admin-test", actor_role="admin")


@pytest.mark.asyncio
async def test_workflow_transition_gate_blocks_roles_not_allowed_by_profile(test_engine) -> None:
    ticket_id = await _seed_gated_workflow_ticket(test_engine)

    with pytest.raises(ValueError, match="allowed_roles"):
        await _resolve_gated_ticket(
            test_engine,
            ticket_id,
            actor_id="support-test",
            actor_role="support",
            resolution_code="fixed_remote",
        )


@pytest.mark.asyncio
async def test_workflow_transition_gate_allows_matching_role_with_required_fields(test_engine) -> None:
    ticket_id = await _seed_gated_workflow_ticket(test_engine)

    result = await _resolve_gated_ticket(
        test_engine,
        ticket_id,
        actor_id="admin-test",
        actor_role="admin",
        resolution_code="fixed_remote",
    )

    assert result["applied"] is True
    assert result["updates"]["status"] == "resolved"
    assert result["updates"]["resolution_code"] == "fixed_remote"
    assert result["event_payload"]["workflow_transition_gate"]["allowed_roles"] == ["admin"]


@pytest.mark.asyncio
async def test_workflow_transition_gate_requires_public_comment(test_engine) -> None:
    ticket_id = await _seed_advanced_gated_workflow_ticket(test_engine)

    with pytest.raises(ValueError, match="required_comment.*public"):
        await _resolve_advanced_gated_ticket(test_engine, ticket_id)


@pytest.mark.asyncio
async def test_workflow_transition_gate_requires_evidence_and_approval(test_engine) -> None:
    ticket_id = await _seed_advanced_gated_workflow_ticket(test_engine)

    with pytest.raises(ValueError, match="require_evidence"):
        await _resolve_advanced_gated_ticket(
            test_engine,
            ticket_id,
            public_comment="Пользователю отправлено описание решения.",
        )

    await _attach_advanced_gate_evidence_and_approval(test_engine, ticket_id)
    result = await _resolve_advanced_gated_ticket(
        test_engine,
        ticket_id,
        public_comment="Пользователю отправлено описание решения.",
    )

    assert result["event_payload"]["workflow_transition_gate"]["require_approval"] is True
    assert result["event_payload"]["workflow_transition_gate"]["require_evidence"] is True
    assert result["event_payload"]["workflow_transition_actions"] == {
        "notify": ["assignee", "queue_lead"],
        "sla": "pause",
    }
