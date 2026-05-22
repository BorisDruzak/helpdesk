import sys
import sqlite3
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.ui_gui.server_api import TicketApiClient


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

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.response

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_get_service_catalog_current_reads_safe_catalog(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            text_payload='{"catalog_version":"v1","services":[{"service_code":"workplace","offerings":[]}]}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_service_catalog_current()

    assert result["catalog_version"] == "v1"
    call = fake_session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "http://localhost:8666/api/service-catalog/current"
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_get_service_catalog_current_refreshes_rotated_db_token(monkeypatch, tmp_path):
    db_path = tmp_path / "storage.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE auth_tokens (
                token TEXT NOT NULL,
                device_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                is_active INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO auth_tokens (token, device_id, created_at, is_active) VALUES (?, ?, ?, 1)",
            ("fresh-token", "device-1", 2.0),
        )

    class FakeDbManager:
        _db_path = str(db_path)

    import pc_agent.core.database as database_module

    monkeypatch.setattr(database_module, "db_manager", FakeDbManager())
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="stale-token",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            text_payload='{"catalog_version":"v1","services":[]}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.get_service_catalog_current()

    call = fake_session.calls[0]
    assert call["headers"]["Authorization"] == "Bearer fresh-token"
    assert client.auth_token == "fresh-token"


@pytest.mark.asyncio
async def test_create_ticket_sends_service_catalog_selection(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={"status": "ok", "ticket": {"ticket_id": "ticket-1"}},
            text_payload='{"status":"ok","ticket":{"ticket_id":"ticket-1"}}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="Сломался ноутбук",
        request_template_key="laptop_incident",
        service_code="workplace",
        offering_code="laptop_broken",
        offering_full_code="workplace.laptop_broken",
    )

    payload = fake_session.calls[0]["json"]
    assert payload["service_code"] == "workplace"
    assert payload["offering_code"] == "laptop_broken"
    assert payload["offering_full_code"] == "workplace.laptop_broken"


@pytest.mark.asyncio
async def test_preview_ticket_create_sends_service_catalog_selection(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={"status": "ok", "preview": {}},
            text_payload='{"status":"ok","preview":{}}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.preview_ticket_create(
        request_template_key="laptop_incident",
        service_code="workplace",
        offering_code="laptop_broken",
    )

    payload = fake_session.calls[0]["json"]
    assert payload["service_code"] == "workplace"
    assert payload["offering_code"] == "laptop_broken"
