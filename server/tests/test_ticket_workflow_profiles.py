from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketApproval, TicketEvent, TicketEvidenceItem, TicketQueue
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets import ola_service
from tickets.workflow_service import TicketWorkflowService, validate_transition_for_ticket

from tickets.workflow_profiles import (
    DEFAULT_WORKFLOW_PROFILE,
    get_workflow_profile,
    list_workflow_profiles,
    save_workflow_profiles,
)


pytestmark = pytest.mark.db_cleanup("tickets")

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
async def test_workflow_blocks_assigned_status_without_assignee(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf04"
    async with session_maker() as session:
        queue = TicketQueue(code="stage18_assigned_invariant", name="Stage 18 assigned invariant")
        session.add(queue)
        await session.flush()
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-assigned-invariant",
                title="Assigned invariant",
                description="Assigned status must not be set without assignee.",
                status="queued",
                requester_id="requester",
                queue_id=queue.id,
                assignee_id=None,
                ticket_type="incident",
            )
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        with pytest.raises(ValueError, match="assignee_id"):
            await workflow.apply_status_transition(
                ticket_id=ticket_id,
                from_status="queued",
                to_status="assigned",
                actor_id="support-test",
                actor_role="support",
                reason="assigned_without_assignee",
                source="test",
            )


@pytest.mark.asyncio
async def test_workflow_passes_target_status_to_sla_pause(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf06"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident SLA pause target status",
                        "purpose": "restore_service",
                        "suggested_path": ["in_progress", "waiting_on_user"],
                        "allowed_statuses": ["in_progress", "waiting_on_user", "canceled"],
                        "transitions": {
                            "in_progress": [
                                {
                                    "to": "waiting_on_user",
                                    "actions": {"sla": "pause"},
                                }
                            ],
                            "waiting_on_user": ["canceled"],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-sla-pause",
                title="Workflow SLA pause",
                description="Workflow target status should satisfy SLA pause condition.",
                status="in_progress",
                requester_id="requester",
                ticket_type="incident",
                custom_fields={
                    "priority_class": "P3",
                    "request_template": {
                        "sla_policy": {
                            "code": "workflow_pause_sla",
                            "pause_conditions": ["waiting_user"],
                            "targets": {
                                "first_response": {"P3": "30m"},
                                "resolution": {"P3": "2h"},
                            },
                        }
                    },
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="waiting_on_user",
            actor_id="support-test",
            actor_role="support",
            reason="needs_requester",
            source="test",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "sla_paused")
            )
        ).scalar_one_or_none()

    assert result["event_payload"]["workflow_transition_action_results"]["sla"]["status"] == "executed"
    assert ticket.sla_paused_at is not None
    assert event is not None


@pytest.mark.asyncio
async def test_workflow_passes_transition_trigger_to_sla_resume(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf05"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident SLA resume trigger",
                        "purpose": "restore_service",
                        "suggested_path": ["waiting_on_user", "in_progress"],
                        "allowed_statuses": ["waiting_on_user", "in_progress", "canceled"],
                        "transitions": {
                            "waiting_on_user": [
                                {
                                    "to": "in_progress",
                                    "trigger": "requester_replied",
                                    "actions": {"sla": "resume"},
                                }
                            ],
                            "in_progress": ["canceled"],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-sla-resume",
                title="Workflow SLA resume",
                description="Workflow trigger should satisfy SLA resume condition.",
                status="waiting_on_user",
                requester_id="requester",
                ticket_type="incident",
                sla_paused_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
                custom_fields={
                    "priority_class": "P3",
                    "request_template": {
                        "sla_policy": {
                            "code": "workflow_resume_sla",
                            "resume_conditions": ["requester_replied"],
                            "targets": {
                                "first_response": {"P3": "30m"},
                                "resolution": {"P3": "2h"},
                            },
                        }
                    },
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="waiting_on_user",
            to_status="in_progress",
            actor_id="support-test",
            actor_role="support",
            reason="requester_replied",
            source="test",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "sla_resumed")
            )
        ).scalar_one_or_none()

    assert result["event_payload"]["workflow_transition_action_results"]["sla"]["status"] == "executed"
    assert ticket.sla_paused_at is None
    assert ticket.sla_paused_seconds is not None
    assert event is not None
    assert event.payload["trigger"] == "requester_replied"


@pytest.mark.asyncio
async def test_workflow_passes_target_status_to_ola_pause(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf21"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident OLA pause target status",
                        "purpose": "restore_service",
                        "suggested_path": ["in_progress", "waiting_on_vendor"],
                        "allowed_statuses": ["in_progress", "waiting_on_vendor", "canceled"],
                        "transitions": {
                            "in_progress": ["waiting_on_vendor"],
                            "waiting_on_vendor": ["canceled"],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-ola-pause",
                title="Workflow OLA pause",
                description="Workflow target status should satisfy OLA pause condition.",
                status="in_progress",
                requester_id="requester",
                ticket_type="incident",
                custom_fields={
                    "priority_class": "P3",
                    "request_template": {
                        "ola_policy": {
                            "code": "workflow_pause_ola",
                            "pause_conditions": [{"status": "waiting_on_vendor"}],
                            "targets": {
                                "ack": {"P3": "30m"},
                                "processing": {"P3": "2h"},
                            },
                        }
                    },
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="waiting_on_vendor",
            actor_id="support-test",
            actor_role="support",
            reason="needs_vendor",
            source="test",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "ola_paused")
            )
        ).scalar_one_or_none()

    assert ticket.ola_paused_at is not None
    assert event is not None


@pytest.mark.asyncio
async def test_workflow_passes_transition_trigger_to_ola_resume(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf22"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident OLA resume trigger",
                        "purpose": "restore_service",
                        "suggested_path": ["waiting_on_vendor", "in_progress"],
                        "allowed_statuses": ["waiting_on_vendor", "in_progress", "canceled"],
                        "transitions": {
                            "waiting_on_vendor": [
                                {
                                    "to": "in_progress",
                                    "trigger": "vendor_replied",
                                }
                            ],
                            "in_progress": ["canceled"],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-workflow-ola-resume",
                title="Workflow OLA resume",
                description="Workflow trigger should satisfy OLA resume condition.",
                status="waiting_on_vendor",
                requester_id="requester",
                ticket_type="incident",
                ola_paused_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
                custom_fields={
                    "priority_class": "P3",
                    "request_template": {
                        "ola_policy": {
                            "code": "workflow_resume_ola",
                            "resume_conditions": ["vendor_replied"],
                            "targets": {
                                "ack": {"P3": "30m"},
                                "processing": {"P3": "2h"},
                            },
                        }
                    },
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="waiting_on_vendor",
            to_status="in_progress",
            actor_id="support-test",
            actor_role="support",
            reason="vendor_replied",
            source="test",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "ola_resumed")
            )
        ).scalar_one_or_none()

    assert ticket.ola_paused_at is None
    assert ticket.ola_paused_seconds is not None
    assert event is not None
    assert event.payload["trigger"] == "vendor_replied"


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
                                    "required_comment_type": "public",
                                    "require_approval": True,
                                    "require_evidence": True,
                                    "log_fields": ["resolution_code", "custom_fields.routing_decision.queue"],
                                    "actions": {
                                        "notify": ["assignee", "queue_lead"],
                                        "sla": "pause",
                                        "approval": "create_request",
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
        assert gate.log_fields == ("resolution_code", "custom_fields.routing_decision.queue")
        assert gate.notify == ("assignee", "queue_lead")
        assert gate.sla_action == "pause"
        assert gate.approval_action == "create_request"
        assert gate.to_dict() == {
            "to": "resolved",
            "required_comment": "public",
            "require_approval": True,
            "require_evidence": True,
            "log_fields": ["resolution_code", "custom_fields.routing_decision.queue"],
            "actions": {
                "notify": ["assignee", "queue_lead"],
                "sla": "pause",
                "approval": "create_request",
            },
        }


@pytest.mark.asyncio
async def test_workflow_profile_accepts_auto_triggered_transition(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        profiles = await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident triggered",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "waiting_on_user", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "waiting_on_user", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "waiting_on_user": [
                                {
                                    "to": "in_progress",
                                    "trigger": "requester_replied",
                                    "auto": True,
                                    "allowed_roles": ["system"],
                                }
                            ],
                            "in_progress": ["waiting_on_user", "resolved", "canceled"],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )

        incident = {profile.ticket_type: profile for profile in profiles}["incident"]
        gate = incident.transition_gates["waiting_on_user"]["in_progress"]

        assert gate.trigger == "requester_replied"
        assert gate.auto is True
        assert gate.allowed_roles == ("system",)
        assert gate.to_dict()["trigger"] == "requester_replied"
        assert gate.to_dict()["auto"] is True


@pytest.mark.asyncio
async def test_workflow_triggered_transition_uses_configured_target_for_requester_reply(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "00000000-0000-0000-0000-00000000wf04"
    async with session_maker() as session:
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident triggered runtime",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "waiting_on_user", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "waiting_on_user", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "waiting_on_user": [
                                {
                                    "to": "in_progress",
                                    "trigger": "requester_replied",
                                    "auto": True,
                                    "allowed_roles": ["system"],
                                }
                            ],
                            "in_progress": ["waiting_on_user", "resolved", "canceled"],
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
                device_id="device-workflow-trigger",
                title="Workflow trigger",
                description="Requester reply should use configured workflow transition.",
                status="waiting_on_user",
                requester_id="requester",
                ticket_type="incident",
            )
        )
        await session.commit()

        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_triggered_transition(
            ticket_id=ticket_id,
            trigger="requester_replied",
            actor_id="system",
            actor_role="system",
            reason="requester_reply",
            source="requester_reply",
            trigger_actor_id="requester",
            trigger_actor_role="user",
            fallback_status="assigned",
        )
        await session.commit()

        ticket = await repo.get_ticket(ticket_id)

    assert result["applied"] is True
    assert result["updates"]["status"] == "in_progress"
    assert ticket.status == "in_progress"
    assert result["event_payload"]["workflow_trigger"] == {
        "trigger": "requester_replied",
        "trigger_actor_id": "requester",
        "trigger_actor_role": "user",
        "auto": True,
        "matched": True,
        "fallback": False,
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
                                    "log_fields": ["resolution_code", "custom_fields.routing_decision.queue"],
                                    "actions": {
                                        "notify": ["assignee", "queue_lead"],
                                        "sla": "pause",
                                        "approval": "create_request",
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
                custom_fields={"routing_decision": {"queue": "servicedesk_l1"}},
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
        "approval": "create_request",
    }
    assert result["event_payload"]["workflow_transition_log_fields"] == [
        {"field": "resolution_code", "value": "fixed_remote", "present": True},
        {"field": "custom_fields.routing_decision.queue", "value": "servicedesk_l1", "present": True},
    ]
    assert result["event_payload"]["workflow_transition_action_results"] == {
        "notify": {"status": "recorded_marker", "recipients": ["assignee", "queue_lead"]},
        "sla": {"status": "no_op", "action": "pause"},
        "approval": {"status": "skipped_no_active_policy", "action": "create_request"},
    }
