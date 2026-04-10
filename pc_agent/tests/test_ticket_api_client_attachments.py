import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_gui.server_api as server_api_module
from ui_gui.server_api import TicketApiClient


class FakeResponse:
    def __init__(self, status=200, payload=None, text_payload=""):
        self.status = status
        self._payload = payload or {}
        self._text_payload = text_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text_payload

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


class FakeFormData:
    def __init__(self):
        self.fields = []

    def add_field(self, name, value, **kwargs):
        self.fields.append((name, value, kwargs))


@pytest.mark.asyncio
async def test_send_message_includes_attachment_refs(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )

    fake_session = FakeSession(FakeResponse(status=200, payload={"status": "ok"}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.send_message(
        ticket_id="ticket-1",
        text="hello",
        from_role="user",
        message_id="msg-1",
        attachment_refs=["art-1", "art-2"],
    )

    assert result["status"] == "ok"
    assert len(fake_session.calls) == 1
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/tickets/ticket-1/message"
    assert call["json"]["message_id"] == "msg-1"
    assert call["json"]["attachment_refs"] == ["art-1", "art-2"]
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_send_message_includes_reply_to(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )

    fake_session = FakeSession(FakeResponse(status=200, payload={"status": "ok"}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.send_message(
        ticket_id="ticket-1",
        text="reply",
        from_role="user",
        message_id="msg-2",
        reply_to={
            "parent_message_id": "msg-1",
            "preview": "Original message",
            "sender_role": "support",
        },
    )

    assert result["status"] == "ok"
    call = fake_session.calls[0]
    assert call["json"]["reply_to"] == {
        "parent_message_id": "msg-1",
        "preview": "Original message",
        "sender_role": "support",
    }


@pytest.mark.asyncio
async def test_mark_ticket_read_posts_last_read_event_id(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )

    fake_session = FakeSession(FakeResponse(status=200, payload={"status": "ok", "no_op": False}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.mark_ticket_read(ticket_id="ticket-1", last_read_event_id=42)

    assert result["status"] == "ok"
    assert len(fake_session.calls) == 1
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/tickets/ticket-1/read"
    assert call["json"]["last_read_event_id"] == 42
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_get_ticket_passes_since_event_id(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )

    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={"status": "ok", "ticket": {}, "messages": [], "events": [], "last_event_id": 7},
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_ticket("ticket-1", since_event_id=42)

    assert result["status"] == "ok"
    assert len(fake_session.calls) == 1
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/tickets/ticket-1"
    assert call["params"] == {"since_event_id": 42}
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_upload_attachment_sends_expected_multipart(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )

    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={
                "status": "success",
                "artifact_id": "art-123",
                "url": "/api/artifacts/art-123/download",
                "mime_type": "text/plain",
                "size": 3,
                "kind": "file",
            },
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)
    monkeypatch.setattr(server_api_module.aiohttp, "FormData", FakeFormData)

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(b"abc")
    tmp.close()

    try:
        result = await client.upload_attachment(
            ticket_id="ticket-1",
            file_path=tmp.name,
            kind="file",
        )
    finally:
        os.unlink(tmp.name)

    assert result["artifact_id"] == "art-123"
    assert len(fake_session.calls) == 1

    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/upload"
    assert call["headers"]["Authorization"] == "Bearer token-123"

    form = call["data"]
    assert isinstance(form, FakeFormData)

    fields = {name: (value, kwargs) for name, value, kwargs in form.fields}
    assert "file" in fields
    assert "ticket_id" in fields
    assert "kind" in fields
    assert fields["ticket_id"][0] == "ticket-1"
    assert fields["kind"][0] == "file"
    assert fields["file"][1]["filename"] == Path(tmp.name).name
