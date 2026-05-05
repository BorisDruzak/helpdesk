from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Operation, Ticket, UiUser
from tests.conftest import TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX
from tests.test_ticket_queue_routing_contracts import _seed_queue


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _requester_headers(user_login: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{user_login}"}


async def _seed_visible_ticket(test_engine, *, requester_id: str = "user-passport") -> str:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login=requester_id, password_hash="test", actor_role="user", is_active=True),
        ])
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket_id = str(uuid.uuid4())
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=str(uuid.uuid4()),
            title="Паспорт тест",
            description="Нужно собрать паспорт решения",
            status="in_progress",
            requester_id=requester_id,
            queue_id=queue.id,
            requester_status="in_work",
            next_action_owner="support",
        )
        session.add(ticket)
        await session.commit()
        return ticket_id


@pytest.mark.asyncio
async def test_get_passport_returns_missing_state_for_new_ticket(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/passport",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["status"] == "missing"
    assert payload["data"]["passport"] is None


@pytest.mark.asyncio
async def test_generate_passport_returns_sections_and_version(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_support_headers(),
        json={"mode": "create", "include_internal_notes": True},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    passport = payload["data"]["passport"]
    assert passport["version"] == 1
    assert passport["sections"]["problem"].startswith("Паспорт тест")
    assert passport["summary_source"] == "deterministic"


@pytest.mark.asyncio
async def test_add_evidence_updates_passport_payload(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)
    await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_support_headers(),
        json={"mode": "create"},
    )

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence",
        headers=_support_headers(),
        json={
            "evidence_type": "operation",
            "source_ref": "operation-123",
            "title": "Диагностика устройства",
            "summary": "Команда завершилась успешно",
            "visibility": "internal",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["evidence"][0]["title"] == "Диагностика устройства"
    assert payload["data"]["evidence"][0]["source_ref"] == "operation-123"


@pytest.mark.asyncio
async def test_evidence_candidates_and_link_endpoint(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)
    session_maker = async_sessionmaker(test_engine)
    operation_id = str(uuid.uuid4())
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=ticket.device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="system.collect",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="System facts collected",
            )
        )
        await session.commit()

    candidates_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence-candidates",
        headers=_support_headers(),
    )
    assert candidates_response.status == 200, await candidates_response.text()
    candidates_payload = await candidates_response.json()
    candidates = candidates_payload["data"]["candidates"]
    assert any(item["source_kind"] == "operation" and item["source_id"] == operation_id for item in candidates)

    link_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence/link",
        headers=_support_headers(),
        json={
            "source_kind": "operation",
            "source_id": operation_id,
            "required_fact": "automated_checks",
        },
    )
    assert link_response.status == 200, await link_response.text()
    link_payload = await link_response.json()
    evidence = link_payload["data"]["evidence"][0]
    assert evidence["source_kind"] == "operation"
    assert evidence["source_id"] == operation_id
    assert evidence["required_fact"] == "automated_checks"


@pytest.mark.asyncio
async def test_patch_passport_keeps_internal_sections_visible_to_support(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)
    await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_support_headers(),
        json={"mode": "create"},
    )

    response = await test_client.patch(
        f"/api/web/support/tickets/{ticket_id}/passport",
        headers=_support_headers(),
        json={
            "user_result_summary": "User-facing result from support",
            "internal_result_summary": "Internal root cause from support",
            "operator_check_summary": "Operator checked queue and logs",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    sections = payload["data"]["passport"]["sections"]
    assert sections["user_result"] == "User-facing result from support"
    assert sections["internal_result"] == "Internal root cause from support"
    assert sections["operator_checks"] == "Operator checked queue and logs"


@pytest.mark.asyncio
async def test_update_evidence_status_endpoint(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)
    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence",
        headers=_support_headers(),
        json={
            "evidence_type": "manual_note",
            "source_ref": "manual:status",
            "source_kind": "manual",
            "source_id": "status",
            "required_fact": "evidence",
            "section_key": "evidence",
            "title": "Manual evidence",
            "summary": "Needs verification",
            "visibility": "internal",
            "verification_status": "accepted",
        },
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    evidence_id = payload["data"]["evidence"][0]["id"]

    update_response = await test_client.patch(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence/{evidence_id}",
        headers=_support_headers(),
        json={
            "verification_status": "rejected",
            "reason": "Not enough detail",
            "export_visibility": "hidden",
        },
    )

    assert update_response.status == 200, await update_response.text()
    updated_payload = await update_response.json()
    evidence = updated_payload["data"]["evidence"][0]
    assert evidence["verification_status"] == "rejected"
    assert evidence["verified_by"] == "support-test"
    assert evidence["metadata_json"]["verification_reason"] == "Not enough detail"
    assert evidence["export_visibility"] == "hidden"


@pytest.mark.asyncio
async def test_requester_cannot_generate_passport(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine, requester_id="user-passport")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_requester_headers("user-passport"),
        json={"mode": "create"},
    )

    assert response.status in {401, 403}
