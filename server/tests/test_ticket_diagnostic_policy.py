from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Operation, Playbook, PlaybookRun, PlaybookVersion, Ticket, TicketEvent, TicketQueue
from app.repos.ticket_events_repo import TicketEventsRepo
from playbooks.form_triggers import start_ticket_created_playbooks
from tickets.diagnostic_policy import apply_diagnostic_result_policy


async def _seed_published_playbook(session, *, key: str, manifest_json: dict | None = None) -> PlaybookVersion:
    playbook = Playbook(
        key=key,
        name=key,
        domain="diagnostics",
        owner="tests",
        archived=False,
    )
    session.add(playbook)
    await session.flush()
    version = PlaybookVersion(
        playbook_id=playbook.id,
        version="1.0.0",
        manifest_json=manifest_json or {},
        status="published",
        created_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
    )
    session.add(version)
    await session.flush()
    return version


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


@pytest.mark.asyncio
async def test_diagnostic_policy_auto_run_starts_suggested_playbook_when_safe(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    playbook_key = f"diagnose_website_{uuid.uuid4().hex[:8]}"
    custom_fields = {
        "priority_class": "P1",
        "diagnostic_consent": {
            "required": True,
            "granted": True,
            "scope": "requester_device",
            "source": "pc_agent_create",
        },
        "request_template": {
            "key": "website_unavailable",
            "diagnostic_policy": {
                "id": "website_diagnostics",
                "suggested_playbooks": [playbook_key],
                "auto_run": {
                    "enabled": True,
                    "only_if_agent_online": True,
                    "only_for_priorities": ["P0", "P1"],
                },
                "consent": {"required_for_requester_device": True},
            },
        },
    }

    async with session_maker() as session:
        await _seed_published_playbook(session, key=playbook_key)
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Website unavailable",
            description="DNS does not resolve",
            status="in_progress",
            priority="P1",
            requester_id="user-net",
            custom_fields=custom_fields,
        )
        session.add(ticket)
        await session.flush()

        started = await start_ticket_created_playbooks(
            session=session,
            state=SimpleNamespace(is_agent_online=lambda checked_device_id: checked_device_id == device_id),
            ticket=ticket,
            custom_fields=custom_fields,
        )
        await session.flush()

        run = (await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "playbook_started",
                )
            )
        ).scalar_one()

        assert started == [run.id]
        assert run.trigger_type == "diagnostic_policy_auto_run"
        assert run.context_json["scenario"]["source"] == "diagnostic_policy"
        assert run.context_json["diagnostic_policy"]["auto_run"]["enabled"] is True
        assert event.payload["trigger"] == "diagnostic_policy_auto_run"
        assert event.payload["source"] == "diagnostic_policy"


@pytest.mark.asyncio
async def test_diagnostic_policy_auto_run_skips_high_risk_playbook_without_explicit_consent(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    playbook_key = f"diagnose_high_risk_{uuid.uuid4().hex[:8]}"
    custom_fields = {
        "priority_class": "P1",
        "diagnostic_consent": {
            "required": True,
            "granted": True,
            "scope": "requester_device",
            "source": "pc_agent_create",
        },
        "request_template": {
            "key": "website_unavailable",
            "diagnostic_policy": {
                "id": "website_diagnostics",
                "suggested_playbooks": [playbook_key],
                "auto_run": {"enabled": True, "only_if_agent_online": True},
                "consent": {"required_for_high_risk_tools": True},
            },
        },
    }

    async with session_maker() as session:
        await _seed_published_playbook(
            session,
            key=playbook_key,
            manifest_json={
                "required_tools": [
                    {"tool": "diag.danger", "risk_level": "system_write"},
                ],
            },
        )
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Website unavailable",
            description="Needs diagnostics",
            status="in_progress",
            priority="P1",
            requester_id="user-net",
            custom_fields=custom_fields,
        )
        session.add(ticket)
        await session.flush()

        started = await start_ticket_created_playbooks(
            session=session,
            state=SimpleNamespace(is_agent_online=lambda checked_device_id: checked_device_id == device_id),
            ticket=ticket,
            custom_fields=custom_fields,
        )
        await session.flush()

        runs = (await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))).scalars().all()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "diagnostic_autorun_skipped",
                )
            )
        ).scalar_one()

        assert started == []
        assert runs == []
        assert event.payload["reason"] == "high_risk_consent_required"
        assert event.payload["playbook_key"] == playbook_key
        assert event.payload["high_risk_tools"] == ["diag.danger"]
        assert event.payload["high_risk_levels"] == ["system_write"]


@pytest.mark.asyncio
async def test_diagnostic_policy_auto_run_starts_high_risk_playbook_with_explicit_consent(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    playbook_key = f"diagnose_high_risk_allowed_{uuid.uuid4().hex[:8]}"
    custom_fields = {
        "priority_class": "P1",
        "diagnostic_consent": {
            "required": True,
            "granted": True,
            "scope": "requester_device",
            "source": "pc_agent_create",
            "high_risk_tools_granted": True,
        },
        "request_template": {
            "key": "website_unavailable",
            "diagnostic_policy": {
                "id": "website_diagnostics",
                "suggested_playbooks": [playbook_key],
                "auto_run": {"enabled": True, "only_if_agent_online": True},
                "consent": {"required_for_high_risk_tools": True},
            },
        },
    }

    async with session_maker() as session:
        await _seed_published_playbook(
            session,
            key=playbook_key,
            manifest_json={
                "required_tools": [
                    {"tool": "diag.danger", "risk_level": "dangerous"},
                ],
            },
        )
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Website unavailable",
            description="Needs diagnostics",
            status="in_progress",
            priority="P1",
            requester_id="user-net",
            custom_fields=custom_fields,
        )
        session.add(ticket)
        await session.flush()

        started = await start_ticket_created_playbooks(
            session=session,
            state=SimpleNamespace(is_agent_online=lambda checked_device_id: checked_device_id == device_id),
            ticket=ticket,
            custom_fields=custom_fields,
        )
        await session.flush()

        run = (await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))).scalar_one()
        skipped = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "diagnostic_autorun_skipped",
                )
            )
        ).scalars().all()

        assert started == [run.id]
        assert run.trigger_type == "diagnostic_policy_auto_run"
        assert skipped == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("custom_overrides", "state_online", "expected_reason"),
    [
        ({"diagnostic_consent": {"required": True, "granted": False, "scope": "requester_device"}}, True, "consent_required"),
        ({"priority_class": "P3"}, True, "priority_not_allowed"),
        ({}, False, "agent_offline"),
    ],
)
async def test_diagnostic_policy_auto_run_skips_when_safety_gate_blocks(
    test_engine,
    custom_overrides,
    state_online,
    expected_reason,
):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    playbook_key = f"diagnose_safe_gate_{uuid.uuid4().hex[:8]}"
    custom_fields = {
        "priority_class": "P1",
        "diagnostic_consent": {
            "required": True,
            "granted": True,
            "scope": "requester_device",
            "source": "pc_agent_create",
        },
        "request_template": {
            "key": "website_unavailable",
            "diagnostic_policy": {
                "id": "website_diagnostics",
                "suggested_playbooks": [playbook_key],
                "auto_run": {
                    "enabled": True,
                    "only_if_agent_online": True,
                    "only_for_priorities": ["P0", "P1"],
                },
                "consent": {"required_for_requester_device": True},
            },
        },
    }
    custom_fields.update(custom_overrides)

    async with session_maker() as session:
        await _seed_published_playbook(session, key=playbook_key)
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Website unavailable",
            description="DNS does not resolve",
            status="in_progress",
            priority=str(custom_fields.get("priority_class") or "P1"),
            requester_id="user-net",
            custom_fields=custom_fields,
        )
        session.add(ticket)
        await session.flush()

        started = await start_ticket_created_playbooks(
            session=session,
            state=SimpleNamespace(is_agent_online=lambda _device_id: state_online),
            ticket=ticket,
            custom_fields=custom_fields,
        )
        await session.flush()

        runs = (await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))).scalars().all()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "diagnostic_autorun_skipped",
                )
            )
        ).scalar_one()

        assert started == []
        assert runs == []
        assert event.payload["reason"] == expected_reason
        assert event.payload["playbook_key"] == playbook_key
