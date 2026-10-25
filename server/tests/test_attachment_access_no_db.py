"""Attachment authorization and blob lifecycle without a PostgreSQL connection."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from aiohttp import FormData, web
from aiohttp.test_utils import TestClient, TestServer

import app.db
from app.repos.artifacts_repo import ArtifactsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.services.artifact_service import ArtifactService, FORBIDDEN
from auth.context import AuthContext, AuthType
from requester.identity_service import RequesterIdentityResolver
from uploads import handlers


pytestmark = pytest.mark.no_db


@pytest.fixture
def attachment_store(monkeypatch, tmp_path):
    ticket = SimpleNamespace(
        ticket_id="ticket-a", device_id="device-a", requester_id="requester-a",
        queue_id=7, assignee_id="assigned-support",
    )
    artifact = SimpleNamespace(
        artifact_id="artifact-a", ticket_id="ticket-a", device_id="device-a",
        expires_at=None, storage_path="existing.txt", original_name="existing.txt",
        size_bytes=8, sha256="existing-sha", mime_type="text/plain", kind="file",
    )
    store = SimpleNamespace(
        ticket=ticket, artifact=artifact, artifacts=[], failure=None, duplicate=None,
        queue_members={"queue-support"}, contains_artifact=True,
    )
    (tmp_path / artifact.storage_path).write_bytes(b"existing")
    monkeypatch.setattr(handlers, "UPLOAD_DIR", tmp_path)

    @asynccontextmanager
    async def session():
        pending = []

        async def commit():
            if store.failure == "commit":
                raise RuntimeError("commit failed")
            if store.failure == "cancel":
                raise asyncio.CancelledError()
            store.artifacts.extend(pending)
            pending.clear()
            if store.failure == "committed-error":
                raise RuntimeError("commit acknowledgement lost")
            if store.failure == "committed-cancel":
                raise asyncio.CancelledError()

        yield SimpleNamespace(pending=pending, commit=commit)
        await commit()
        if store.failure == "close":
            raise RuntimeError("session close failed")
        if store.failure == "cancel-close":
            raise asyncio.CancelledError()

    async def get_ticket(self, ticket_id):
        return store.ticket if ticket_id == "ticket-a" else None

    async def is_actor_in_queue(self, queue_id, actor_id):
        return queue_id == 7 and actor_id in store.queue_members

    async def contains_artifact(self, ticket_id, artifact_id):
        return ticket_id == "ticket-a" and artifact_id == "artifact-a" and store.contains_artifact

    async def get_artifact(self, artifact_id):
        return store.artifact if artifact_id == "artifact-a" else None

    async def create(self, **fields):
        if store.failure == "create":
            raise RuntimeError("insert failed")
        if store.failure == "cancel-create":
            raise asyncio.CancelledError()
        artifact = SimpleNamespace(**fields)
        self.session.pending.append(artifact)
        return artifact

    async def duplicate(self, sha256, operation_id):
        return store.duplicate

    async def requester_ticket(self, *, actor_id, ticket_id):
        if actor_id == "requester-a" and ticket_id == "ticket-a":
            return store.ticket
        return None

    monkeypatch.setattr(app.db, "get_session", session)
    monkeypatch.setattr(TicketEventsRepo, "get_ticket", get_ticket)
    monkeypatch.setattr(TicketEventsRepo, "is_actor_in_queue", is_actor_in_queue)
    monkeypatch.setattr(TicketEventsRepo, "ticket_contains_artifact", contains_artifact)
    monkeypatch.setattr(ArtifactsRepo, "get_by_id", get_artifact)
    monkeypatch.setattr(ArtifactsRepo, "create", create)
    monkeypatch.setattr(ArtifactsRepo, "get_by_sha256_and_operation_id", duplicate)
    monkeypatch.setattr(RequesterIdentityResolver, "get_ticket", requester_ticket)
    return store


def ui_actor(actor_id="outside-support", role="support"):
    return AuthContext(actor_id=actor_id, actor_role=role, auth_type=AuthType.UI_TOKEN)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_id,role,allowed",
    [
        ("outside-support", "support", False),
        ("queue-support", "support", True),
        ("assigned-support", "support", True),
        ("administrator", "admin", True),
        ("auditor", "auditor", True),
        ("requester-a", "user", True),
        ("requester-b", "user", False),
    ],
)
async def test_download_obeys_ticket_queue_and_owner_scope(attachment_store, actor_id, role, allowed):
    artifact, reason = await ArtifactService(None).get_artifact_for_download(
        "artifact-a", ui_actor(actor_id, role),
    )

    assert (artifact is attachment_store.artifact) is allowed
    assert reason == (None if allowed else FORBIDDEN)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope,allowed", [("ticket-a", True), ("ticket-b", False)])
async def test_download_public_session_keeps_ticket_scope(attachment_store, scope, allowed):
    actor = AuthContext("public:ticket-a", "user", AuthType.PUBLIC_TICKET_TOKEN, ticket_scope=scope)
    artifact, reason = await ArtifactService(None).get_artifact_for_download("artifact-a", actor)

    assert (artifact is attachment_store.artifact) is allowed
    assert reason == (None if allowed else FORBIDDEN)


@pytest.mark.asyncio
async def test_download_legacy_event_binding_still_checks_support_queue(attachment_store):
    attachment_store.artifact.ticket_id = None
    artifact, reason = await ArtifactService(None).get_artifact_for_download(
        "artifact-a", ui_actor(), ticket_id_from_request="ticket-a",
    )

    assert artifact is None
    assert reason == FORBIDDEN


@asynccontextmanager
async def upload_client(actor):
    @web.middleware
    async def authenticated(request, handler):
        request["auth_context"] = actor
        return await handler(request)

    async def upload(request):
        try:
            return await handlers.handle_upload(request)
        except asyncio.CancelledError:
            # Give the HTTP test driver a deterministic cancellation result.
            return web.Response(status=499)

    app = web.Application(middlewares=[authenticated])
    app.router.add_post("/api/upload", upload)
    app.router.add_get("/api/artifacts/{artifact_id}/download", handlers.handle_artifact_download)
    async with TestClient(TestServer(app)) as client:
        yield client


def upload_form(ticket_id="ticket-a", operation_id=None):
    form = FormData()
    # Metadata intentionally follows the blob, as a real browser may send it.
    form.add_field("file", b"new attachment", filename="proof.txt", content_type="text/plain")
    if ticket_id is not None:
        form.add_field("ticket_id", ticket_id)
    if operation_id:
        form.add_field("operation_id", operation_id)
    return form


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_id,role,status",
    [
        ("outside-support", "support", 403),
        ("queue-support", "support", 200),
        ("assigned-support", "support", 200),
        ("administrator", "admin", 200),
        ("auditor", "auditor", 403),
    ],
)
async def test_upload_obeys_ticket_queue_and_write_scope(attachment_store, tmp_path, actor_id, role, status):
    async with upload_client(ui_actor(actor_id, role)) as client:
        response = await client.post("/api/upload", data=upload_form())
        payload = await response.json()

    assert response.status == status
    assert len(attachment_store.artifacts) == (1 if status == 200 else 0)
    if status == 200:
        assert (tmp_path / payload["filename"]).read_bytes() == b"new attachment"
    else:
        assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ticket_id,status", [(None, 400), ("missing-ticket", 404)])
async def test_rejected_upload_removes_uncommitted_blob(attachment_store, tmp_path, ticket_id, status):
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form(ticket_id))

    assert response.status == status
    assert attachment_store.artifacts == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("create", 500), ("cancel-create", 499)])
async def test_uncommitted_upload_failure_removes_blob(attachment_store, tmp_path, failure, status):
    attachment_store.failure = failure
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == status
    assert attachment_store.artifacts == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]


@pytest.mark.asyncio
async def test_duplicate_upload_removes_candidate_and_retains_existing_blob(attachment_store, tmp_path):
    attachment_store.duplicate = attachment_store.artifact
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form(operation_id="operation-a"))
        payload = await response.json()

    assert response.status == 200
    assert payload["artifact_id"] == "artifact-a"
    assert attachment_store.artifacts == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]
    assert (tmp_path / "existing.txt").read_bytes() == b"existing"


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id,status", [("requester-a", 200), ("requester-b", 403)])
async def test_requester_upload_keeps_identity_scope(attachment_store, tmp_path, actor_id, status):
    async with upload_client(ui_actor(actor_id, "user")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == status
    assert len(attachment_store.artifacts) == (1 if status == 200 else 0)
    assert len(list(tmp_path.iterdir())) == (2 if status == 200 else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope,status", [("ticket-a", 200), ("ticket-b", 403)])
async def test_public_upload_keeps_session_ticket_scope(attachment_store, tmp_path, scope, status):
    actor = AuthContext("public:ticket-a", "user", AuthType.PUBLIC_TICKET_TOKEN, ticket_scope=scope)
    async with upload_client(actor) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == status
    assert len(attachment_store.artifacts) == (1 if status == 200 else 0)
    assert len(list(tmp_path.iterdir())) == (2 if status == 200 else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id,status", [("outside-support", 403), ("queue-support", 200)])
async def test_download_http_enforces_support_queue(attachment_store, actor_id, status):
    async with upload_client(ui_actor(actor_id)) as client:
        response = await client.get("/api/artifacts/artifact-a/download")
        body = await response.read()

    assert response.status == status
    if status == 200:
        assert body == b"existing"
    else:
        assert body != b"existing"


@pytest.mark.asyncio
async def test_oversized_upload_removes_candidate(attachment_store, tmp_path, monkeypatch):
    monkeypatch.setattr(handlers, "ARTIFACT_MAX_BYTES", 4)
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == 413
    assert attachment_store.artifacts == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]


@pytest.mark.asyncio
async def test_agent_operation_rejection_removes_candidate(attachment_store, tmp_path, monkeypatch):
    from app.repos import OperationsRepo

    async def missing_operation(self, operation_id):
        return None

    monkeypatch.setattr(OperationsRepo, "get_by_operation_id", missing_operation)
    actor = AuthContext("device-a", "agent", AuthType.AGENT_TOKEN)
    async with upload_client(actor) as client:
        response = await client.post("/api/upload", data=upload_form(operation_id="missing-operation"))

    assert response.status == 404
    assert attachment_store.artifacts == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing.txt"]


@pytest.mark.asyncio
async def test_committed_upload_survives_response_failure(attachment_store, tmp_path, monkeypatch):
    json_response = web.json_response

    def fail_success_response(data, **kwargs):
        if data.get("status") == "success":
            raise RuntimeError("response serialization failed")
        return json_response(data, **kwargs)

    monkeypatch.setattr(handlers.web, "json_response", fail_success_response)
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == 500
    assert len(attachment_store.artifacts) == 1
    artifact = attachment_store.artifacts[0]
    assert (tmp_path / artifact.storage_path).read_bytes() == b"new attachment"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("close", 500), ("cancel-close", 499)])
async def test_committed_upload_survives_session_close_failure(attachment_store, tmp_path, failure, status):
    attachment_store.failure = failure
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == status
    assert len(attachment_store.artifacts) == 1
    artifact = attachment_store.artifacts[0]
    assert (tmp_path / artifact.storage_path).read_bytes() == b"new attachment"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,status,persisted_count",
    [("commit", 500, 0), ("cancel", 499, 0), ("committed-error", 500, 1), ("committed-cancel", 499, 1)],
)
async def test_uncertain_commit_retains_candidate_for_reconciliation(
    attachment_store, tmp_path, failure, status, persisted_count,
):
    attachment_store.failure = failure
    async with upload_client(ui_actor("administrator", "admin")) as client:
        response = await client.post("/api/upload", data=upload_form())

    assert response.status == status
    assert len(attachment_store.artifacts) == persisted_count
    candidates = [path for path in tmp_path.iterdir() if path.name != "existing.txt"]
    assert len(candidates) == 1
    assert candidates[0].read_bytes() == b"new attachment"
    if attachment_store.artifacts:
        assert candidates[0].name == attachment_store.artifacts[0].storage_path
