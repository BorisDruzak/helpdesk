import uuid

import pytest
from sqlalchemy import select

from app.db.engine import async_sessionmaker
from app.db.models import Artifact, TicketEvent
from tests.conftest import *  # noqa: F401,F403
from tests.test_helpers import create_test_ticket
from tickets.evidence_service import TicketEvidenceService


async def _create_artifact(
    test_engine,
    *,
    device_id: str,
    ticket_id: str | None,
    original_name: str,
    mime_type: str = "application/octet-stream",
    size_bytes: int = 128,
    kind: str = "file",
) -> str:
    artifact_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path=f"{artifact_id}.bin",
                original_name=original_name,
                mime_type=mime_type,
                size_bytes=size_bytes,
                sha256="a" * 64,
                kind=kind,
                device_id=device_id,
                ticket_id=ticket_id,
                operation_id=None,
                expires_at=None,
            )
        )
        await session.commit()
    return artifact_id


async def _get_message_payload(test_engine, ticket_id: str, message_id: str):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "chat_message",
            TicketEvent.payload["message_id"].astext == message_id,
        )
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        return event.payload if event else None


@pytest.mark.asyncio
async def test_send_message_with_attachment_refs_and_empty_text(test_client, test_engine):
    device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    artifact_id = await _create_artifact(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        original_name="report.txt",
        mime_type="text/plain",
    )
    message_id = str(uuid.uuid4())

    resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": message_id,
            "from_role": "user",
            "text": "",
            "attachment_refs": [artifact_id],
        },
    )
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    assert data["status"] == "ok"
    assert data["attachments_count"] == 1

    payload = await _get_message_payload(test_engine, ticket_id, message_id)
    assert payload is not None
    assert payload["text"] == ""
    assert payload["attachment_refs"] == [artifact_id]
    assert len(payload["attachments"]) == 1
    assert payload["attachments"][0]["artifact_id"] == artifact_id


@pytest.mark.asyncio
async def test_send_message_with_multiple_attachment_refs_preserves_order(test_client, test_engine):
    device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    artifact_1 = await _create_artifact(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        original_name="a.txt",
    )
    artifact_2 = await _create_artifact(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        original_name="b.txt",
    )
    ordered_refs = [artifact_2, artifact_1]
    message_id = str(uuid.uuid4())

    resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": message_id,
            "from_role": "user",
            "text": "",
            "attachment_refs": ordered_refs,
        },
    )
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    assert data["attachments_count"] == 2

    payload = await _get_message_payload(test_engine, ticket_id, message_id)
    assert payload is not None
    assert payload["attachment_refs"] == ordered_refs
    assert [a["artifact_id"] for a in payload["attachments"]] == ordered_refs


@pytest.mark.asyncio
async def test_send_message_with_invalid_attachment_ref_returns_400(test_client):
    device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": str(uuid.uuid4()),
            "from_role": "user",
            "text": "",
            "attachment_refs": [str(uuid.uuid4())],
        },
    )
    assert resp.status == 400, await resp.text()
    data = await resp.json()
    assert data["error"] == "validation_error"
    assert "attachment_refs" in data["details"]


@pytest.mark.asyncio
async def test_send_message_rejects_attachment_from_other_device(test_client, test_engine):
    ticket_device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=ticket_device_id)
    foreign_device_id = str(uuid.uuid4())
    artifact_id = await _create_artifact(
        test_engine,
        device_id=foreign_device_id,
        ticket_id=ticket_id,
        original_name="foreign.txt",
    )

    resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": str(uuid.uuid4()),
            "from_role": "user",
            "text": "",
            "attachment_refs": [artifact_id],
        },
    )
    assert resp.status == 400, await resp.text()
    data = await resp.json()
    assert data["error"] == "validation_error"
    assert any("device mismatch" in item for item in data["details"]["attachment_refs"])


@pytest.mark.asyncio
async def test_get_ticket_and_messages_include_attachments(test_client, test_engine):
    device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    artifact_id = await _create_artifact(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        original_name="photo.png",
        mime_type="image/png",
    )
    message_id = str(uuid.uuid4())

    send_resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": message_id,
            "from_role": "user",
            "text": "",
            "attachment_refs": [artifact_id],
        },
    )
    assert send_resp.status == 200, await send_resp.text()

    ticket_resp = await test_client.get(f"/api/tickets/{ticket_id}")
    assert ticket_resp.status == 200, await ticket_resp.text()
    ticket_data = await ticket_resp.json()
    ticket_message = next((m for m in ticket_data["messages"] if m.get("message_id") == message_id), None)
    assert ticket_message is not None
    assert len(ticket_message.get("attachments", [])) == 1
    assert ticket_message["attachments"][0]["artifact_id"] == artifact_id

    messages_resp = await test_client.get(
        f"/api/tickets/{ticket_id}/messages",
        headers={"X-Device-Id": device_id},
    )
    assert messages_resp.status == 200, await messages_resp.text()
    messages_data = await messages_resp.json()
    api_message = next((m for m in messages_data["messages"] if m.get("message_id") == message_id), None)
    assert api_message is not None
    assert len(api_message.get("attachments", [])) == 1
    assert api_message["attachments"][0]["artifact_id"] == artifact_id


@pytest.mark.asyncio
async def test_send_message_claims_unbound_attachment_as_evidence_candidate(test_client, test_engine):
    device_id = str(uuid.uuid4())
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    artifact_id = await _create_artifact(
        test_engine,
        device_id=device_id,
        ticket_id=None,
        original_name="requester-screen.png",
        mime_type="image/png",
        kind="screenshot",
    )
    message_id = str(uuid.uuid4())

    resp = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": message_id,
            "from_role": "user",
            "text": "Скриншот ошибки",
            "attachment_refs": [artifact_id],
        },
    )

    assert resp.status == 200, await resp.text()
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        artifact = await session.get(Artifact, artifact_id)
        candidates = await TicketEvidenceService(session).collect_candidates(ticket_id)

    assert artifact.ticket_id == ticket_id
    assert any(
        candidate["candidate_id"] == f"artifact:{artifact_id}" and candidate["evidence_type"] == "screenshot"
        for candidate in candidates
    )
