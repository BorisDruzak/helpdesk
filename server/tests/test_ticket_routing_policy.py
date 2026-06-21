from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, TicketSlaPolicy
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.test_ticket_form_packs import _clear_request_form_packs
from tests.test_ticket_queue_routing_contracts import _seed_queue
from tickets.routing_service import TicketRoutingService, set_routing_lock


pytestmark = pytest.mark.db_cleanup("tickets")

async def _seed_ticket(
    test_engine,
    *,
    routing_policy: dict,
    queue_id: int | None = None,
    assignee_id: str | None = None,
    extra_custom_fields: dict | None = None,
) -> str:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    custom_fields = {
        "priority_class": "P3",
        "request_kind": "website_unavailable",
        "request_form_data": {
            "affected_scope": "department",
            "url": "https://reports.example.local",
        },
        "request_template": {
            "key": "website_unavailable",
            "ticket_type": "incident",
            "routing_policy": routing_policy,
        },
    }
    if extra_custom_fields:
        custom_fields.update(extra_custom_fields)
    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Website unavailable",
            description="Reports site does not open",
            status="new",
            requester_id="requester-routing",
            ticket_type="incident",
            priority="P4",
            queue_id=queue_id,
            assignee_id=assignee_id,
            custom_fields=custom_fields,
        )
        session.add(ticket)
        await session.commit()
    return ticket_id


@pytest.mark.asyncio
async def test_template_routing_policy_first_match_applies_actions_and_events(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        l1_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        network_queue = await _seed_queue(session, code=f"net_{uuid.uuid4().hex[:8]}", name="Networks")
        access_queue = await _seed_queue(session, code=f"access_{uuid.uuid4().hex[:8]}", name="Access")
        sla_policy = TicketSlaPolicy(
            name=f"Routing SLA {uuid.uuid4().hex[:8]}",
            timezone="UTC",
            is_default=False,
            is_active=True,
        )
        session.add(sla_policy)
        await session.flush()
        sla_policy_id = sla_policy.id
        await session.commit()
        ticket_id = await _seed_ticket(
            test_engine,
            queue_id=l1_queue.id,
            routing_policy={
                "rules": [
                    {
                        "priority_order": 20,
                        "when": {"field": "request_form_data.affected_scope", "op": "eq", "value": "department"},
                            "then": {
                                "queue_id": network_queue.id,
                                "priority_boost": 1,
                                "sla_policy_id": sla_policy_id,
                            "suggested_playbook_id": "diagnose.network.basic",
                            "approval_policy": {"required": True, "approval_mode": "any_one"},
                            "tags": ["mass-impact"],
                        },
                    },
                    {
                        "priority_order": 30,
                        "when": {"field": "request_kind", "op": "eq", "value": "access"},
                        "then": {"queue_id": access_queue.id},
                    },
                ],
                "fallback": {"queue_id": l1_queue.id},
                "max_auto_reroutes": 3,
            },
        )

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketRoutingService(session, repo)

        async def add_event(ticket_id: str, device_id: str, event_type: str, payload: dict) -> None:
            await repo.add_event(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type=event_type,
                payload=payload,
                trace_id=str(uuid.uuid4()),
            )

        routed_queue_id = await service.apply_routing(
            ticket_id,
            f"device-{ticket_id[:8]}",
            add_events_fn=add_event,
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert routed_queue_id == network_queue.id
        assert ticket.queue_id == network_queue.id
        assert ticket.priority == "P3"
        assert ticket.sla_policy_id == sla_policy_id
        assert ticket.tags == ["mass-impact"]
        assert ticket.custom_fields["priority_class"] == "P2"
        assert ticket.custom_fields["request_template"]["approval_policy"]["required"] is True
        routing_decision = ticket.custom_fields["routing_decision"]
        assert routing_decision["source"] == "request_template.routing_policy"
        assert routing_decision["matched_rule"]["priority_order"] == 20
        assert routing_decision["suggested_playbook_id"] == "diagnose.network.basic"
        assert routing_decision["auto_reroute_count"] == 1

        events = (
            await session.execute(
                select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at.asc())
            )
        ).scalars().all()
        assert [event.event_type for event in events] == ["routing_applied", "queue_changed"]
        assert events[0].payload["routing_source"] == "request_template.routing_policy"
        assert events[0].payload["matched_rule"]["priority_order"] == 20


@pytest.mark.asyncio
async def test_template_routing_policy_uses_fallback_when_no_rule_matches(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        l1_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        fallback_queue = await _seed_queue(session, code=f"fallback_{uuid.uuid4().hex[:8]}", name="Fallback")
        await session.commit()
        ticket_id = await _seed_ticket(
            test_engine,
            queue_id=l1_queue.id,
            routing_policy={
                "rules": [
                    {
                        "priority_order": 10,
                        "when": {"field": "request_kind", "op": "eq", "value": "access"},
                        "then": {"queue_id": 123456},
                    }
                ],
                "fallback": {"queue_id": fallback_queue.id},
            },
        )

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketRoutingService(session, repo)
        assert await service.apply_routing(ticket_id, f"device-{ticket_id[:8]}") == fallback_queue.id
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.queue_id == fallback_queue.id
        assert ticket.custom_fields["routing_decision"]["source"] == "request_template.routing_policy.fallback"


@pytest.mark.asyncio
async def test_template_routing_policy_respects_manual_lock_and_assignee_guard(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        l1_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        network_queue = await _seed_queue(session, code=f"net_{uuid.uuid4().hex[:8]}", name="Networks")
        await session.commit()
        routing_policy = {
            "rules": [
                {
                    "priority_order": 10,
                    "when": {"field": "request_kind", "op": "eq", "value": "website_unavailable"},
                    "then": {"queue_id": network_queue.id},
                }
            ],
            "do_not_reroute_if_assignee_locked": True,
        }
        locked_ticket_id = await _seed_ticket(
            test_engine,
            queue_id=l1_queue.id,
            routing_policy=routing_policy,
            extra_custom_fields=set_routing_lock({}, "manual queue"),
        )
        assigned_ticket_id = await _seed_ticket(
            test_engine,
            queue_id=l1_queue.id,
            assignee_id="operator-a",
            routing_policy=routing_policy,
        )

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketRoutingService(session, repo)
        assert await service.apply_routing(locked_ticket_id, f"device-{locked_ticket_id[:8]}") == l1_queue.id
        assert await service.apply_routing(assigned_ticket_id, f"device-{assigned_ticket_id[:8]}") == l1_queue.id
        await session.commit()

    async with session_maker() as session:
        locked_ticket = await session.get(Ticket, locked_ticket_id)
        assigned_ticket = await session.get(Ticket, assigned_ticket_id)
        assert locked_ticket.queue_id == l1_queue.id
        assert assigned_ticket.queue_id == l1_queue.id


@pytest.mark.asyncio
async def test_template_routing_policy_respects_max_auto_reroutes(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        l1_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        network_queue = await _seed_queue(session, code=f"net_{uuid.uuid4().hex[:8]}", name="Networks")
        await session.commit()
        ticket_id = await _seed_ticket(
            test_engine,
            queue_id=l1_queue.id,
            routing_policy={
                "max_auto_reroutes": 1,
                "rules": [
                    {
                        "priority_order": 10,
                        "when": {"field": "request_kind", "op": "eq", "value": "website_unavailable"},
                        "then": {"queue_id": network_queue.id},
                    }
                ],
            },
            extra_custom_fields={
                "routing_decision": {
                    "source": "request_template.routing_policy",
                    "auto_reroute_count": 1,
                }
            },
        )

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketRoutingService(session, repo)
        assert await service.apply_routing(ticket_id, f"device-{ticket_id[:8]}") == l1_queue.id
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.queue_id == l1_queue.id
        assert ticket.custom_fields["routing_decision"]["auto_reroute_count"] == 1


@pytest.mark.asyncio
async def test_create_ticket_applies_request_template_routing_policy(test_client, test_engine) -> None:
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", auto_assign_enabled=False)
        network_queue = await _seed_queue(
            session,
            code=f"network_{uuid.uuid4().hex[:8]}",
            name="Network routing",
            auto_assign_enabled=False,
        )
        await session.commit()
        network_queue_id = network_queue.id

    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Request catalog",
                "forms": [
                    {
                        "key": "website_unavailable",
                        "request_kind": "website_unavailable",
                        "ticket_type": "incident",
                        "title": "Website unavailable",
                        "routing_policy": {
                            "rules": [
                                {
                                    "priority_order": 10,
                                    "when": {
                                        "field": "request_form_data.affected_scope",
                                        "op": "eq",
                                        "value": "whole_building",
                                    },
                                    "then": {"queue_id": network_queue_id},
                                }
                            ]
                        },
                        "fields": [
                            {"key": "url", "label": "URL", "type": "text", "required": True},
                            {"key": "affected_scope", "label": "Affected scope", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={"Authorization": "Bearer test-ui-admin-token", "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    create_response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Website issue",
            "description": "The local portal is unavailable",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "website_unavailable",
            "form_pack_key": "request_forms",
            "form_payload": {
                "url": "https://portal.example.local",
                "affected_scope": "whole_building",
                "impact_scope": "department",
                "work_continuity": "work_stopped_no_workaround",
                "business_importance": "normal",
            },
            "ticket_type": "consultation",
        },
        headers={"Authorization": "Bearer test-ui-user:alice", "Content-Type": "application/json"},
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.ticket_type == "incident"
        assert ticket.queue_id == network_queue_id
        assert ticket.custom_fields["routing_decision"]["source"] == "request_template.routing_policy"
        assert ticket.custom_fields["routing_decision"]["matched_rule"]["priority_order"] == 10
