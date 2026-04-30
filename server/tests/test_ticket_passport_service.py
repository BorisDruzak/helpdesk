from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Operation, Ticket, TicketEvent, TicketEvidenceItem, TicketResolutionPassport
from tickets.passport_service import TicketPassportService


@pytest.mark.asyncio
async def test_passport_service_builds_requester_problem_and_object_sections(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Не печатает принтер",
            description="В кабинете 214 не печатаются документы",
            status="in_progress",
            requester_id="user-214",
            requester_status="in_work",
            next_action_owner="support",
            custom_fields={
                "user_display_name": "Иванов Иван",
                "requester_profile": {"department": "Бухгалтерия", "building": "A", "room": "214"},
            },
        )
        session.add(ticket)
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="chat_message",
                payload={"text": "Принтер HP не печатает", "sender_role": "user", "visibility": "public"},
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        assert payload["passport"]["version"] == 1
        sections = payload["passport"]["sections"]
        assert "Иванов Иван" in sections["requester"]
        assert "Не печатает принтер" in sections["problem"]
        assert "кабинете 214" in sections["problem"]
        assert device_id in sections["affected_object"]


@pytest.mark.asyncio
async def test_passport_service_collects_tool_events_as_automated_checks(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Диагностика сети",
                description="Проверить доступность сайта",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_result",
                operation_id=operation_id,
                payload={"tool_name": "network.ping", "result_summary": "Пинг успешен"},
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="network.ping",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="Средняя задержка 3 мс",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        assert "network.ping" in payload["passport"]["sections"]["automated_checks"]
        assert "Средняя задержка 3 мс" in payload["passport"]["sections"]["automated_checks"]
        assert operation_id in payload["passport"]["source_operation_ids"]
        assert payload["actions"][0]["operation_id"] == operation_id


@pytest.mark.asyncio
async def test_passport_service_materializes_diagnostic_operation_evidence_from_policy(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Check website availability",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {
                                "to_passport": True,
                                "as_evidence": True,
                            },
                        },
                    },
                },
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK, DNS resolved",
            )
        )
        await session.flush()

        first_payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        second_payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="refresh")

        evidence_rows = (
            await session.execute(
                select(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id == ticket_id)
            )
        ).scalars().all()

        assert len(evidence_rows) == 1
        evidence = evidence_rows[0]
        assert evidence.evidence_type == "diagnostic_result"
        assert evidence.source_ref == f"operation:{operation_id}"
        assert evidence.title == "diagnose.website"
        assert evidence.summary == "HTTP 200 OK, DNS resolved"
        assert evidence.created_by == "op1"
        assert first_payload["evidence"][0]["source_ref"] == f"operation:{operation_id}"
        assert "HTTP 200 OK" in first_payload["passport"]["sections"]["evidence"]
        assert len(second_payload["evidence"]) == 1


@pytest.mark.asyncio
async def test_passport_service_does_not_materialize_diagnostic_evidence_when_policy_disables_it(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Check website availability",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {"to_passport": True, "as_evidence": False},
                        },
                    },
                },
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        evidence_count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )
        assert evidence_count == 0
        assert payload["evidence"] == []


@pytest.mark.asyncio
async def test_passport_service_does_not_materialize_foreign_ticket_device_operation(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    other_ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Current ticket has no own operations",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {"to_passport": True, "as_evidence": True},
                        },
                    },
                },
            )
        )
        session.add(
            Ticket(
                ticket_id=other_ticket_id,
                device_id=device_id,
                title="Previous website check",
                description="Owns the operation",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=other_ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK for another ticket",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        evidence_count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )
        assert evidence_count == 0
        assert payload["evidence"] == []


@pytest.mark.asyncio
async def test_passport_refresh_creates_new_version_without_overwriting_previous(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Первый заголовок",
            description="Первое описание",
            status="in_progress",
            requester_id="user-refresh",
            requester_status="in_work",
            next_action_owner="support",
        )
        session.add(ticket)
        await session.flush()

        first = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        ticket.description = "Описание после уточнения"
        second = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="refresh")
        await session.flush()

        passports = (
            await session.execute(
                select(TicketResolutionPassport)
                .where(TicketResolutionPassport.ticket_id == ticket_id)
                .order_by(TicketResolutionPassport.version)
            )
        ).scalars().all()

        assert first["passport"]["version"] == 1
        assert second["passport"]["version"] == 2
        assert len(passports) == 2
        assert "Первое описание" in passports[0].problem_summary
        assert "Описание после уточнения" in passports[1].problem_summary
@pytest.mark.asyncio
async def test_passport_service_applies_reporting_policy_sections_and_evidence_package(test_engine):
    from sqlalchemy import delete

    from app.db.models import HelpdeskPolicyAudit, ReportingPolicy
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo

    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        await HelpdeskPolicyRepo(session).publish_policy(
            kind="reporting",
            code="website_passport_reporting",
            title="Website passport reporting",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={
                "required_sections": ["problem", "evidence", "user_result"],
                "evidence_package": {
                    "include_action_log": False,
                    "include_related_objects": False,
                },
                "export_visibility": {
                    "hide_sections": ["internal_result", "operator_checks"],
                },
                "report_tags": ["critical_service", "diagnostics"],
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Cannot open reporting site",
                status="resolved",
                requester_id="user-net",
                requester_status="resolved",
                next_action_owner="support",
                resolution_code="fixed_remote",
                resolution_summary="DNS cache cleared",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                    },
                },
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="status_changed",
                payload={"status": "resolved", "actor_id": "support-1"},
            )
        )
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="HTTP check",
                summary="HTTP 200 OK",
                visibility="internal",
                created_by="support-1",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    passport = payload["passport"]
    assert set(passport["sections"]) == {"problem", "evidence", "user_result"}
    assert "HTTP 200 OK" in passport["sections"]["evidence"]
    assert passport["source_payload"]["report_tags"] == ["critical_service", "diagnostics"]
    assert passport["source_payload"]["reporting_policy"]["required_sections"] == ["problem", "evidence", "user_result"]
    assert payload["actions"] == []
    assert payload["related_objects"] == []
