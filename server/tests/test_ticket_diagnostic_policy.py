from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Operation, Ticket, TicketEvent, TicketQueue
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.diagnostic_policy import apply_diagnostic_result_policy


@pytest.mark.asyncio
async def test_diagnostic_policy_reroutes_by_result_without_status_change(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        l1_queue = TicketQueue(code="servicedesk_l1", name="ServiceDesk L1", is_triage=True, is_active=True)
        networks_queue = TicketQueue(code="networks", name="Networks", is_triage=False, is_active=True)
        session.add_all([l1_queue, networks_queue])
        await session.flush()

        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="DNS does not resolve",
                status="in_progress",
                requester_id="user-net",
                queue_id=l1_queue.id,
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "reroute_by_result": {"DNS_FAIL": "networks"},
                        },
                    },
                },
            )
        )
        operation = Operation(
            operation_id=operation_id,
            device_id=device_id,
            ticket_id=ticket_id,
            kind="tool_call",
            tool_name="diagnose.website",
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            status="failed",
            queued_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            error_code="DNS_FAIL",
            error_message="DNS lookup failed",
        )
        session.add(operation)
        await session.flush()

        result = await apply_diagnostic_result_policy(
            session,
            ticket_repo=TicketEventsRepo(session),
            operation=operation,
            result_payload={
                "status": "error",
                "summary": "DNS lookup failed",
                "error": {"code": "DNS_FAIL", "message": "NXDOMAIN"},
            },
        )
        await session.flush()

        updated_ticket = await session.get(Ticket, ticket_id)
        events = (
            await session.execute(
                select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.id)
            )
        ).scalars().all()

        assert result["applied"] is True
        assert result["diagnostic_result"] == "DNS_FAIL"
        assert result["rerouted"] is True
        assert updated_ticket.status == "in_progress"
        assert updated_ticket.queue_id == networks_queue.id
        assert updated_ticket.custom_fields["diagnostic_result"] == "DNS_FAIL"
        assert updated_ticket.custom_fields["diagnostics"]["last_result_class"] == "DNS_FAIL"
        assert updated_ticket.custom_fields["diagnostics"]["last_operation_id"] == operation_id
        assert updated_ticket.custom_fields["routing_decision"]["source"] == "diagnostic_policy.reroute_by_result"
        assert updated_ticket.custom_fields["routing_decision"]["diagnostic_result"] == "DNS_FAIL"
        assert [event.event_type for event in events] == [
            "diagnostic_result_classified",
            "routing_applied",
            "queue_changed",
        ]
        assert events[0].operation_id == operation_id
        assert events[1].payload["routing_source"] == "diagnostic_policy.reroute_by_result"
        assert events[2].payload["queue_id"] == networks_queue.id


@pytest.mark.asyncio
async def test_diagnostic_policy_reroute_is_idempotent_per_operation(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        l1_queue = TicketQueue(code="servicedesk_l1", name="ServiceDesk L1", is_triage=True, is_active=True)
        networks_queue = TicketQueue(code="networks", name="Networks", is_triage=False, is_active=True)
        session.add_all([l1_queue, networks_queue])
        await session.flush()

        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="DNS does not resolve",
                status="in_progress",
                requester_id="user-net",
                queue_id=l1_queue.id,
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "diagnostic_policy": {
                            "reroute_by_result": {"DNS_FAIL": {"queue": "networks"}},
                        },
                    },
                },
            )
        )
        operation = Operation(
            operation_id=operation_id,
            device_id=device_id,
            ticket_id=ticket_id,
            kind="tool_call",
            tool_name="diagnose.dns.basic",
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            status="failed",
            queued_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            error_code="DNS_FAIL",
            error_message="DNS lookup failed",
        )
        session.add(operation)
        await session.flush()
        ticket_repo = TicketEventsRepo(session)

        first = await apply_diagnostic_result_policy(
            session,
            ticket_repo=ticket_repo,
            operation=operation,
            result_payload={"error": {"code": "DNS_FAIL"}},
        )
        second = await apply_diagnostic_result_policy(
            session,
            ticket_repo=ticket_repo,
            operation=operation,
            result_payload={"error": {"code": "DNS_FAIL"}},
        )
        await session.flush()

        updated_ticket = await session.get(Ticket, ticket_id)
        event_count = await session.scalar(
            select(func.count(TicketEvent.id)).where(TicketEvent.ticket_id == ticket_id)
        )

        assert first["applied"] is True
        assert second["applied"] is False
        assert second["reason"] == "already_applied"
        assert updated_ticket.queue_id == networks_queue.id
        assert updated_ticket.custom_fields["routing_decision"]["auto_reroute_count"] == 1
        assert updated_ticket.custom_fields["diagnostics"]["applied_operation_ids"] == [operation_id]
        assert event_count == 3
