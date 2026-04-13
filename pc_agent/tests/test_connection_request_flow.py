import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.auth import connection_request as flow_mod


class _FakeDb:
    def __init__(self):
        self.saved = []

    async def save_auth_token(self, token, device_id):
        self.saved.append((token, device_id))


class _FakeEventBus:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)


class _FakeIdentity:
    def __init__(self):
        self.token = None
        self.last_connection_request_error_code = None


class _FakeResponse:
    def __init__(self, status, payload=None, content_type="application/json"):
        self.status = status
        self._payload = payload or {}
        self.content_type = content_type

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, post_responses, get_responses):
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        if not self._post_responses:
            raise RuntimeError("no more post responses")
        item = self._post_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        if not self._get_responses:
            raise RuntimeError("no more get responses")
        item = self._get_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_connection_request_approved_immediately(monkeypatch):
    db = _FakeDb()
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession([_FakeResponse(200, {"status": "approved", "token": "tok-1"})], []),
    )

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-1",
        hostname="host-1",
        db_manager=db,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (True, False)
    assert identity.token == "tok-1"
    assert db.saved == [("tok-1", "dev-1")]
    assert any(e["event_type"] == "connection_approved" for e in bus.events)


@pytest.mark.asyncio
async def test_connection_request_pending_then_approved(monkeypatch):
    db = _FakeDb()
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession(
            [
                _FakeResponse(200, {"status": "pending"}),
                _FakeResponse(200, {"status": "pending"}),  # heartbeat
            ],
            [_FakeResponse(200, {"status": "approved", "token": "tok-2"})],
        ),
    )

    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(flow_mod.asyncio, "sleep", _fast_sleep)

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-2",
        hostname="host-2",
        db_manager=db,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (True, False)
    assert identity.token == "tok-2"
    assert db.saved == [("tok-2", "dev-2")]
    assert any(e["event_type"] == "connection_request_pending" for e in bus.events)
    assert any(e["event_type"] == "connection_approved" for e in bus.events)


@pytest.mark.asyncio
async def test_connection_request_rejected_403(monkeypatch):
    db = _FakeDb()
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession([_FakeResponse(403, {"message": "rejected"})], []),
    )

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-3",
        hostname="host-3",
        db_manager=db,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (False, True)
    assert identity.token is None
    assert db.saved == []
    assert any(e["event_type"] == "connection_rejected" for e in bus.events)


@pytest.mark.asyncio
async def test_connection_request_pending_then_rejected(monkeypatch):
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession(
            [
                _FakeResponse(200, {"status": "pending"}),
                _FakeResponse(200, {"status": "pending"}),  # heartbeat
            ],
            [_FakeResponse(200, {"status": "rejected"})],
        ),
    )

    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(flow_mod.asyncio, "sleep", _fast_sleep)

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-4",
        hostname="host-4",
        db_manager=None,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (False, True)
    assert any(e["event_type"] == "connection_rejected" for e in bus.events)
    assert identity.last_connection_request_error_code == "CONNECTION_REJECTED"


@pytest.mark.asyncio
async def test_connection_request_pending_then_archived(monkeypatch):
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession(
            [
                _FakeResponse(200, {"status": "pending"}),
                _FakeResponse(200, {"status": "pending"}),
            ],
            [_FakeResponse(200, {"status": "rejected", "error_code": "DEVICE_ARCHIVED", "message": "Device archived"})],
        ),
    )

    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(flow_mod.asyncio, "sleep", _fast_sleep)

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-archived",
        hostname="host-archived",
        db_manager=None,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (False, True)
    assert identity.last_connection_request_error_code == "DEVICE_ARCHIVED"


@pytest.mark.asyncio
async def test_connection_request_archived_409(monkeypatch):
    bus = _FakeEventBus()
    identity = _FakeIdentity()

    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession([_FakeResponse(409, {"status": "rejected", "error_code": "DEVICE_ARCHIVED", "message": "Device archived"})], []),
    )

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-archived-409",
        hostname="host-archived-409",
        db_manager=None,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (False, True)
    assert identity.last_connection_request_error_code == "DEVICE_ARCHIVED"


@pytest.mark.asyncio
async def test_connection_request_post_error_returns_false(monkeypatch):
    identity = _FakeIdentity()
    monkeypatch.setattr(
        flow_mod,
        "ClientSession",
        lambda: _FakeSession([RuntimeError("network down")], []),
    )

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-5",
        hostname="host-5",
        db_manager=None,
        identity_manager=identity,
        event_bus=None,
        wait_seconds=30,
    )

    assert (ok, rejected) == (False, False)


@pytest.mark.asyncio
async def test_connection_request_sends_identity_metadata(monkeypatch):
    db = _FakeDb()
    bus = _FakeEventBus()
    identity = _FakeIdentity()
    session = _FakeSession([_FakeResponse(200, {"status": "approved", "token": "tok-6"})], [])

    monkeypatch.setattr(flow_mod, "ClientSession", lambda: session)

    ok, rejected = await flow_mod.run_connection_request_flow(
        api_url="http://example/api",
        device_id="dev-6",
        hostname="host-6",
        metadata={"machine_id": "dev-6", "install_id": "install-6", "identity_scheme": "machine_id_v1"},
        db_manager=db,
        identity_manager=identity,
        event_bus=bus,
        wait_seconds=30,
    )

    assert (ok, rejected) == (True, False)
    first_post = session.post_calls[0][1]["json"]
    assert first_post["metadata"]["machine_id"] == "dev-6"
    assert first_post["metadata"]["install_id"] == "install-6"

