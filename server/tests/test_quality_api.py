from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, UiUser
from registry.account_session_service import AccountSessionService
from tests.test_ticket_account_access import _approved_binding, _device, _agent_headers

pytestmark = pytest.mark.db_cleanup("full")


def _user_headers(user_login: str) -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{user_login}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _account_headers(device_id: str, created: dict) -> dict[str, str]:
    return {
        **_agent_headers(device_id),
        "X-Account-Session-Id": created["session"]["session_id"],
        "X-Account-Session-Token": created["session_token"],
    }


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
async def test_agent_feedback_api_requires_matching_account_session(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_a = str(uuid.uuid4())
    device_b = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([_device(device_a), _device(device_b)])
        binding_a = await _approved_binding(session, device_a)
        binding_b = await _approved_binding(session, device_b)
        account_service = AccountSessionService(session)
        account_a = await account_service.create_confirmed_binding_session(
            device_id=device_a,
            binding_id=binding_a["binding"]["binding_id"],
        )
        account_b = await account_service.create_confirmed_binding_session(
            device_id=device_b,
            binding_id=binding_b["binding"]["binding_id"],
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_a,
                title="Quality feedback account boundary",
                description="Quality feedback account boundary",
                status="resolved",
                requester_id=device_a,
                requester_person_id=account_a["session"]["person_id"],
                requester_binding_id=account_a["session"]["binding_id"],
                requester_account_session_id=account_a["session"]["session_id"],
                requester_account_mode="confirmed_binding",
                resolved_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    payload = {"rating": 5, "problem_resolved": True, "reason_codes": []}
    missing = await test_client.post(
        f"/api/tickets/{ticket_id}/feedback",
        headers=_agent_headers(device_a),
        json=payload,
    )
    wrong = await test_client.post(
        f"/api/tickets/{ticket_id}/feedback",
        headers=_account_headers(device_b, account_b),
        json=payload,
    )
    valid = await test_client.post(
        f"/api/tickets/{ticket_id}/feedback",
        headers=_account_headers(device_a, account_a),
        json={**payload, "comment": "valid requester feedback"},
    )

    assert missing.status == 403
    assert (await missing.json())["error_code"] == "ACCOUNT_SESSION_REQUIRED"
    assert wrong.status == 403
    assert (await wrong.json())["error_code"] == "ACCOUNT_ACCESS_DENIED"
    assert valid.status == 200, await valid.text()
    body = await valid.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_reopen_api_requires_matching_account_session(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_a = str(uuid.uuid4())
    device_b = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([_device(device_a), _device(device_b)])
        binding_a = await _approved_binding(session, device_a)
        binding_b = await _approved_binding(session, device_b)
        account_service = AccountSessionService(session)
        account_a = await account_service.create_confirmed_binding_session(
            device_id=device_a,
            binding_id=binding_a["binding"]["binding_id"],
        )
        account_b = await account_service.create_confirmed_binding_session(
            device_id=device_b,
            binding_id=binding_b["binding"]["binding_id"],
        )
        ticket_missing = str(uuid.uuid4())
        ticket_wrong = str(uuid.uuid4())
        ticket_valid = str(uuid.uuid4())
        for ticket_id in (ticket_missing, ticket_wrong, ticket_valid):
            session.add(
                Ticket(
                    ticket_id=ticket_id,
                    device_id=device_a,
                    title="Quality reopen account boundary",
                    description="Quality reopen account boundary",
                    status="resolved",
                    requester_id=device_a,
                    requester_person_id=account_a["session"]["person_id"],
                    requester_binding_id=account_a["session"]["binding_id"],
                    requester_account_session_id=account_a["session"]["session_id"],
                    requester_account_mode="confirmed_binding",
                    resolved_at=datetime.now(timezone.utc),
                )
            )
        await session.commit()

    payload = {"reason_code": "not_resolved", "reason_comment": "still broken"}
    missing = await test_client.post(
        f"/api/tickets/{ticket_missing}/reopen",
        headers=_agent_headers(device_a),
        json=payload,
    )
    wrong = await test_client.post(
        f"/api/tickets/{ticket_wrong}/reopen",
        headers=_account_headers(device_b, account_b),
        json=payload,
    )
    valid = await test_client.post(
        f"/api/tickets/{ticket_valid}/reopen",
        headers=_account_headers(device_a, account_a),
        json=payload,
    )

    assert missing.status == 403
    assert (await missing.json())["error_code"] == "ACCOUNT_SESSION_REQUIRED"
    assert wrong.status == 403
    assert (await wrong.json())["error_code"] == "ACCOUNT_ACCESS_DENIED"
    assert valid.status == 200, await valid.text()
    body = await valid.json()
    assert body["status"] == "ok"
    assert body["ticket_status"] == "in_progress"


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
