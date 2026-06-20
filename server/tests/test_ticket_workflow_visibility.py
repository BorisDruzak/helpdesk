from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.engine import async_sessionmaker
from app.db.models import Ticket, TicketEvidenceItem, TicketWait
from app.api.serializers import ticket_to_dict
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.visibility_policy import apply_ticket_visibility_payload
from tickets.statuses import (
    CANONICAL_STATUSES,
    next_action_owner_for_status,
    normalize_status,
    requester_status_for_internal,
)
from tickets.workflow_service import validate_transition, TicketWorkflowService


def test_ticket_status_catalog_exposes_product_lifecycle():
    assert CANONICAL_STATUSES == (
        "new",
        "queued",
        "assigned",
        "in_progress",
        "waiting_on_user",
        "waiting_on_internal_team",
        "waiting_on_vendor",
        "waiting_on_approval",
        "scheduled",
        "resolved",
        "closed",
        "canceled",
    )
    assert normalize_status("triaged") == ("queued", True)
    assert normalize_status("In Progress") == ("in_progress", True)
    assert normalize_status("in-progress") == ("in_progress", True)
    assert normalize_status("waiting_internal") == ("waiting_on_internal_team", True)
    assert normalize_status("cancelled") == ("canceled", True)

    assert requester_status_for_internal("new") == "accepted"
    assert requester_status_for_internal("assigned") == "accepted"
    assert requester_status_for_internal("waiting_on_internal_team") == "in_work"
    assert requester_status_for_internal("waiting_on_user") == "needs_requester"
    assert requester_status_for_internal("resolved") == "review_solution"
    assert requester_status_for_internal("closed") == "closed"
    assert requester_status_for_internal("canceled") == "canceled"

    assert next_action_owner_for_status("waiting_on_user") == "requester"
    assert next_action_owner_for_status("waiting_on_internal_team") == "internal_team"
    assert next_action_owner_for_status("waiting_on_vendor") == "vendor"
    assert next_action_owner_for_status("waiting_on_approval") == "approver"
    assert next_action_owner_for_status("resolved") == "requester"


def test_support_transition_matrix_allows_product_waits_and_scheduling():
    assert validate_transition("new", "queued", True)
    assert validate_transition("queued", "assigned", True)
    assert validate_transition("assigned", "in_progress", True)
    assert validate_transition("in_progress", "waiting_on_internal_team", True)
    assert validate_transition("in_progress", "waiting_on_approval", True)
    assert validate_transition("in_progress", "scheduled", True)
    assert validate_transition("scheduled", "in_progress", True)
    assert validate_transition("waiting_on_approval", "canceled", True)
    assert validate_transition("resolved", "closed", True)
    assert not validate_transition("closed", "waiting_on_user", True)


def test_ticket_serializer_exposes_work_visibility_fields():
    ticket = Ticket(
        ticket_id=str(uuid.uuid4()),
        device_id=str(uuid.uuid4()),
        title="Serialized visibility",
        description="Serializer should expose requester-safe state",
        status="waiting_on_user",
        requester_id="user-a",
        next_action_owner="requester",
        status_reason="need_screenshot",
        requester_status="needs_requester",
        resolution_summary="Restarted print service",
        requester_resolution_summary="Try printing again",
        evidence_required=True,
        evidence_ref="event:42",
        closure_feedback={"result": "partial"},
    )

    payload = ticket_to_dict(ticket)

    assert payload["status"] == "waiting_on_user"
    assert payload["status_label"] == "Ожидает пользователя"
    assert payload["requester_status"] == "needs_requester"
    assert payload["requester_status_label"] == "Нужен ваш ответ"
    assert payload["next_action_owner"] == "requester"
    assert payload["status_reason"] == "need_screenshot"
    assert payload["resolution_summary"] == "Restarted print service"
    assert payload["requester_resolution_summary"] == "Try printing again"
    assert payload["evidence_required"] is True
    assert payload["evidence_ref"] == "event:42"
    assert payload["closure_feedback"] == {"result": "partial"}


def test_ticket_serializer_applies_request_template_visibility_policy():
    ticket = Ticket(
        ticket_id=str(uuid.uuid4()),
        device_id=str(uuid.uuid4()),
        title="Policy visibility",
        description="Requester must see public process state",
        status="waiting_on_internal_team",
        requester_id="user-a",
        next_action_owner="internal_team",
        requester_status="in_work",
        root_cause="Internal DNS resolver failed",
        custom_fields={
            "request_template": {
                "key": "website_unavailable",
                "ticket_type": "incident",
                "visibility_policy": {
                    "public_status_mapping": {
                        "waiting_on_internal_team": "Обращение в работе у внутренней команды"
                    },
                    "hide_from_requester": ["root_cause", "ola", "latest_operations"],
                    "show_to_requester": ["public_status", "public_status_label", "expected_due_at"],
                },
            }
        },
    )

    support_payload = ticket_to_dict(ticket, visibility="support")
    requester_payload = ticket_to_dict(ticket, visibility="requester")

    assert support_payload["status"] == "waiting_on_internal_team"
    assert support_payload["public_status"] == "in_work"
    assert support_payload["public_status_label"] == "Обращение в работе у внутренней команды"
    assert support_payload["root_cause"] == "Internal DNS resolver failed"
    assert support_payload["visibility"]["source"] == "request_template.visibility_policy"
    assert "root_cause" in support_payload["visibility"]["hidden_from_requester"]

    assert requester_payload["status"] == "waiting_on_internal_team"
    assert requester_payload["public_status"] == "in_work"
    assert requester_payload["public_status_label"] == "Обращение в работе у внутренней команды"
    assert "root_cause" not in requester_payload
    assert requester_payload["requester_visible_fields"] == [
        "public_status",
        "public_status_label",
        "expected_due_at",
    ]

    requester_runtime_payload = apply_ticket_visibility_payload(
        ticket,
        {
            **support_payload,
            "ola": {"ola_queue_id": 10},
            "latest_operations": [{"operation_id": "op-1"}],
            "worklogs": [{"note": "internal"}],
        },
        visibility="requester",
    )
    assert "ola" not in requester_runtime_payload
    assert "latest_operations" not in requester_runtime_payload
    assert "worklogs" not in requester_runtime_payload


@pytest.mark.asyncio
async def test_runtime_visibility_policy_resolves_from_registry(test_engine):
    import uuid

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import HelpdeskPolicyAudit, VisibilityPolicy
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    from tickets.visibility_policy import apply_ticket_visibility_payload_async

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "visibility_policies"))
        await session.execute(delete(VisibilityPolicy))
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="visibility",
            code="website_visibility_runtime",
            title="Website visibility runtime",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={
                "public_status_mapping": {
                    "waiting_on_internal_team": "Work continues without user action"
                },
                "hide_from_requester": ["root_cause"],
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            title="Registry visibility",
            description="Registry visibility check",
            status="waiting_on_internal_team",
            requester_id="requester-1",
            requester_status="in_work",
            ticket_type="incident",
            custom_fields={
                "request_template": {
                    "key": "website_unavailable",
                    "ticket_type": "incident",
                }
            },
        )
        payload = await apply_ticket_visibility_payload_async(
            session,
            ticket,
            {"root_cause": "Internal resolver failed"},
            visibility="requester",
        )

    assert payload["public_status_label"] == "Work continues without user action"
    assert "root_cause" not in payload
    assert payload["visibility"]["source"] == "effective.visibility_policy"


@pytest.mark.asyncio
async def test_workflow_updates_next_owner_requester_status_and_wait_ledger(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=str(uuid.uuid4()),
            title="Internal team wait",
            description="Need network team",
            status="in_progress",
            requester_id="user-a",
            next_action_owner="support",
            requester_status="in_work",
        )
        session.add(ticket)
        await session.flush()

        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)

        wait_transition = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="waiting_on_internal_team",
            actor_id="support-test",
            actor_role="support",
            reason="network_team",
        )
        assert wait_transition["updates"]["next_action_owner"] == "internal_team"
        assert wait_transition["updates"]["requester_status"] == "in_work"
        assert wait_transition["updates"]["status_reason"] == "network_team"

        await session.flush()
        active_wait = (
            await session.execute(
                select(TicketWait).where(
                    TicketWait.ticket_id == ticket_id,
                    TicketWait.ended_at.is_(None),
                )
            )
        ).scalar_one()
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "waiting_on_internal_team"
        assert ticket.next_action_owner == "internal_team"
        assert ticket.requester_status == "in_work"
        assert ticket.status_reason == "network_team"
        assert active_wait.wait_type == "internal_team"
        assert active_wait.reason == "network_team"
        assert active_wait.created_by == "support-test"

        resume_transition = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="waiting_on_internal_team",
            to_status="in_progress",
            actor_id="network-op",
            actor_role="support",
            reason="network_answered",
        )
        assert resume_transition["updates"]["next_action_owner"] == "support"
        assert resume_transition["updates"]["requester_status"] == "in_work"
        assert resume_transition["updates"]["status_reason"] is None

        await session.flush()
        ticket = await session.get(Ticket, ticket_id)
        closed_wait = (
            await session.execute(
                select(TicketWait).where(TicketWait.ticket_id == ticket_id)
            )
        ).scalar_one()
        assert ticket.status == "in_progress"
        assert ticket.next_action_owner == "support"
        assert ticket.status_reason is None
        assert closed_wait.ended_at is not None
        assert closed_wait.closed_by == "network-op"


@pytest.mark.asyncio
async def test_resolved_requires_evidence_when_ticket_requires_it(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=str(uuid.uuid4()),
            title="Evidence governed ticket",
            description="Resolution must be backed by proof",
            status="in_progress",
            requester_id="user-a",
            next_action_owner="support",
            requester_status="in_work",
            evidence_required=True,
        )
        session.add(ticket)
        await session.flush()

        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)

        with pytest.raises(ValueError, match="требуется подтверждение"):
            await workflow.apply_status_transition(
                ticket_id=ticket_id,
                from_status="in_progress",
                to_status="resolved",
                actor_id="support-test",
                actor_role="support",
                reason="done",
            )

        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="operation",
                source_ref="operation-1",
                title="Диагностика",
                summary="Проверка завершена успешно",
                visibility="internal",
                created_by="support-test",
            )
        )
        await session.flush()

        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="resolved",
            actor_id="support-test",
            actor_role="support",
            reason="done",
        )

        assert result["updates"]["status"] == "resolved"
