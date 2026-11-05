"""Real persistence and HTTP authority for browser tickets without a device."""

import uuid
import importlib.util
from pathlib import Path

import pytest
from aiohttp import FormData
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.db.models import Artifact, Ticket, UiUser
from tests.conftest import TEST_UI_USER_PREFIX, TEST_UI_SUPPORT_TOKEN
from tests.test_requester_workspace_api import _person_for_login
from tests.test_ticket_queue_routing_contracts import _seed_queue
from uploads import handlers


pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.fixture
def test_client(test_client_light):
    return test_client_light


def headers(login):
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{login}"}


def form(ticket_id, *, content=b"browser proof", mime="image/png", operation_id=None):
    data = FormData()
    data.add_field("file", content, filename="proof.png", content_type=mime)
    data.add_field("ticket_id", ticket_id)
    if operation_id:
        data.add_field("operation_id", operation_id)
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize("uploader", ["requester", "support"])
async def test_no_device_ticket_upload_message_and_download(
    test_client, test_engine, monkeypatch, tmp_path, uploader,
):
    monkeypatch.setattr(handlers, "UPLOAD_DIR", tmp_path)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "attachment-owner@example.test"
    async with maker() as session:
        person = await _person_for_login(session, login=login)
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="attachment", name="Attachment queue", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()), device_id=None, title="Browser attachment",
            description="No selected device", status="in_progress", requester_id="neutral-owner",
            requester_external_ref=person.person_id,
            requester_snapshot_json={"person": {"external_id": person.person_id}, "display_name": person.display_name},
            queue_id=queue.id, assignee_id="support-test",
        )
        other = Ticket(ticket_id=str(uuid.uuid4()), device_id=None, title="Other ticket", description="Separate scope", status="in_progress", requester_id=login)
        session.add_all([ticket, other])
        await session.commit()
        ticket_id, other_id = ticket.ticket_id, other.ticket_id

    upload_headers = headers(login) if uploader == "requester" else {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}
    response = await test_client.post("/api/upload", headers=upload_headers, data=form(ticket_id))
    body = await response.json()
    assert response.status == 200, body
    assert body["mime_type"] == "image/png"
    assert body["kind"] == "screenshot"
    artifact_id = body["artifact_id"]
    async with maker() as session:
        artifact = await session.get(Artifact, artifact_id)
        assert artifact.device_id is None
        assert artifact.ticket_id == ticket_id
        assert (tmp_path / artifact.storage_path).read_bytes() == b"browser proof"

    sent = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message", headers=headers(login),
        json={"text": "", "attachment_refs": [artifact_id]},
    )
    assert sent.status == 200, await sent.text()
    downloaded = await test_client.get(body["url"], headers=headers(login))
    assert downloaded.status == 200, await downloaded.text()
    assert await downloaded.read() == b"browser proof"
    staff_download = await test_client.get(body["url"], headers=upload_headers)
    assert staff_download.status == 200
    foreign = await test_client.get(body["url"] + f"?ticket_id={other_id}", headers=headers("other@example.test"))
    assert foreign.status in {403, 404}
    foreign_upload = await test_client.post("/api/upload", headers=headers("other@example.test"), data=form(ticket_id))
    assert foreign_upload.status in {403, 404}
    wrong_ticket = await test_client.post(
        f"/api/web/requester/tickets/{other_id}/message", headers=headers(login),
        json={"text": "", "attachment_refs": [artifact_id]},
    )
    assert wrong_ticket.status == 400, await wrong_ticket.text()
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_artifact_requires_device_or_ticket(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(Artifact(
            artifact_id=str(uuid.uuid4()), storage_path="orphan.txt", original_name="orphan.txt",
            mime_type="text/plain", size_bytes=1, sha256="a" * 64, device_id=None, ticket_id=None,
        ))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_artifact_migration_preserves_legacy_rows_and_refuses_lossy_rollback(test_engine):
    path = Path(__file__).parents[1] / "app/db/migrations/versions/20261105_154_ticket_artifacts_optional_device.py"
    spec = importlib.util.spec_from_file_location("attachment_migration_154", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def apply(connection, direction):
        with Operations.context(MigrationContext.configure(connection)):
            getattr(migration, direction)()

    legacy_id, browser_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with test_engine.begin() as conn:
        await conn.run_sync(apply, "downgrade")
        await conn.execute(text("""
            INSERT INTO artifacts (artifact_id,storage_path,original_name,mime_type,size_bytes,sha256,device_id,created_at)
            VALUES (:id,'legacy.txt','legacy.txt','text/plain',1,:sha,'legacy-device',now())
        """), {"id": legacy_id, "sha": "a" * 64})
        await conn.run_sync(apply, "upgrade")
        assert (await conn.execute(text("SELECT device_id FROM artifacts WHERE artifact_id=:id"), {"id": legacy_id})).scalar_one() == "legacy-device"
        await conn.execute(text("""
            INSERT INTO artifacts (artifact_id,storage_path,original_name,mime_type,size_bytes,sha256,ticket_id,created_at)
            VALUES (:id,'browser.txt','browser.txt','text/plain',1,:sha,:ticket,now())
        """), {"id": browser_id, "sha": "b" * 64, "ticket": str(uuid.uuid4())})
    with pytest.raises(IntegrityError):
        async with test_engine.begin() as conn:
            await conn.run_sync(apply, "downgrade")
    async with test_engine.begin() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM artifacts WHERE artifact_id IN (:a,:b)"), {"a": legacy_id, "b": browser_id})).scalar_one() == 2
        assert (await conn.execute(text("SELECT is_nullable FROM information_schema.columns WHERE table_name='artifacts' AND column_name='device_id'"))).scalar_one() == "YES"


@pytest.mark.asyncio
async def test_no_device_storage_error_is_safe_and_removes_blob(test_client, test_engine, monkeypatch, tmp_path):
    monkeypatch.setattr(handlers, "UPLOAD_DIR", tmp_path)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "attachment-error@example.test"
    ticket_id = str(uuid.uuid4())
    async with maker() as session:
        session.add(Ticket(ticket_id=ticket_id, title="Storage failure", description="Exercise database rejection", status="in_progress", requester_id=login, device_id=None))
        await session.commit()
    # A database-backed varchar failure exercises rollback after writing the blob.
    response = await test_client.post("/api/upload", headers=headers(login), data=form(ticket_id, mime="x" * 101))
    payload = await response.json()
    assert response.status == 500
    assert payload["error_code"] == "UPLOAD_FAILED"
    assert "sql" not in str(payload).lower()
    assert list(tmp_path.iterdir()) == []
    async with maker() as session:
        assert (await session.execute(select(Artifact).where(Artifact.ticket_id == ticket_id))).scalars().all() == []
