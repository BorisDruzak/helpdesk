from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select

from app.db.engine import async_sessionmaker
from app.db.models import Operation, Ticket, TicketEvent, TicketResolutionPassport
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
