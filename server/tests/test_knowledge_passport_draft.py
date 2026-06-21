from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketResolutionPassport
from knowledge.passport_draft_service import KnowledgePassportDraftService


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_passport_draft_creates_knowledge_item_version_and_bindings(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = Ticket(
            ticket_id="ticket-passport-knowledge",
            device_id="device-passport-knowledge",
            title="VPN не подключается",
            description="Ошибка VPN",
            status="resolved",
            requester_id="requester-passport",
            service_code="network",
            offering_code="network.vpn_issue",
            request_type="incident",
            reporting_category="network",
        )
        session.add(ticket)
        passport = TicketResolutionPassport(
            ticket_id=ticket.ticket_id,
            version=1,
            status="draft",
            problem_summary="VPN не подключается",
            operator_checks_summary="Проверена сеть",
            changes_made_summary="Переустановлен профиль VPN",
            user_result_summary="VPN подключился",
            repeat_guidance="Повторить переподключение профиля",
            source_payload={"stale": True, "stale_reasons": ["ticket changed"]},
        )
        session.add(passport)
        await session.flush()
        result = await KnowledgePassportDraftService(session).create_draft_from_ticket(
            ticket.ticket_id,
            item_type="known_error",
            actor_id="support",
        )
        await session.commit()

    assert result["item"]["item_type"] == "known_error"
    assert result["item"]["status"] == "draft"
    assert result["item"]["source_kind"] == "ticket_passport"
    assert result["item"]["source_ticket_id"] == "ticket-passport-knowledge"
    assert result["warnings"]
    assert "VPN не подключается" in result["version"]["body"]
    assert result["bindings"][0]["service_code"] == "network"
    assert result["bindings"][0]["offering_code"] == "network.vpn_issue"
