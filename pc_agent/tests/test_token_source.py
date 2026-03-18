import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.auth.token_source import load_auth_token


class _FakeDb:
    def __init__(self, token=None):
        self._token = token
        self.saved = []

    async def get_auth_token(self, _device_id):
        return self._token

    async def save_auth_token(self, token, device_id):
        self.saved.append((token, device_id))


class _FakeIdentity:
    def __init__(self, uid="dev-1"):
        self.uuid = uid
        self.token = None


@pytest.mark.asyncio
async def test_load_auth_token_prefers_env(monkeypatch):
    identity = _FakeIdentity("dev-env")
    db = _FakeDb(token="db-token")
    monkeypatch.setenv("AUTH_TOKEN", "env-token")

    called = {"gui": 0}

    async def _gui_wait():
        called["gui"] += 1
        return "gui-token"

    token = await load_auth_token(db, identity, _gui_wait)

    assert token == "env-token"
    assert identity.token == "env-token"
    assert db.saved == [("env-token", "dev-env")]
    assert called["gui"] == 0


@pytest.mark.asyncio
async def test_load_auth_token_falls_back_to_db(monkeypatch):
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    identity = _FakeIdentity("dev-db")
    db = _FakeDb(token="db-token")

    token = await load_auth_token(db, identity)

    assert token == "db-token"
    assert identity.token == "db-token"
    assert db.saved == []


@pytest.mark.asyncio
async def test_load_auth_token_uses_gui_callback_when_no_env_db(monkeypatch):
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    identity = _FakeIdentity("dev-gui")
    db = _FakeDb(token=None)

    async def _gui_wait():
        return "gui-token"

    token = await load_auth_token(db, identity, _gui_wait)

    assert token == "gui-token"
    assert identity.token == "gui-token"
    assert db.saved == []


@pytest.mark.asyncio
async def test_load_auth_token_returns_none_when_missing_everywhere(monkeypatch):
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    identity = _FakeIdentity("dev-none")
    db = _FakeDb(token=None)

    token = await load_auth_token(db, identity)

    assert token is None
    assert identity.token is None

