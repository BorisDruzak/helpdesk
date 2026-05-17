from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, UiUser


def _user_headers(user_login: str) -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{user_login}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_requester_feedback_api_accepts_resolved_ticket_and_low_csat_reopen_available(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id="device-quality-api", title="VPN", description="VPN", status="resolved", requester_id="alice", resolved_at=datetime.now(timezone.utc)))
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/feedback",
        headers=_user_headers("alice"),
        json={"rating": 2, "problem_resolved": False, "reason_codes": ["not_resolved"], "source_surface": "requester_portal"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["reopen_available"] is True
    assert payload["feedback_id"]


@pytest.mark.asyncio
async def test_quality_internal_api_denies_requester_and_allows_support(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        await session.commit()

    denied = await test_client.get("/api/web/quality/reviews", headers=_user_headers("alice"))
    allowed = await test_client.get("/api/web/quality/reviews", headers=_support_headers())

    assert denied.status == 403
    assert allowed.status == 200, await allowed.text()
    payload = await allowed.json()
    assert payload["status"] == "ok"
    assert "reviews" in payload
