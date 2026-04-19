import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.auth.token_source import (
    import_missing_auth_token_from_data_roots,
    load_auth_token,
)


class _FakeDb:
    def __init__(self, token=None, tokens=None):
        self._token = token
        self._tokens = dict(tokens or {})
        self.saved = []

    async def get_auth_token(self, device_id):
        if self._tokens:
            return self._tokens.get(device_id)
        return self._token

    async def save_auth_token(self, token, device_id):
        self.saved.append((token, device_id))
        if self._tokens is not None:
            self._tokens[device_id] = token


class _FakeIdentity:
    def __init__(self, uid="dev-1", install_id=None):
        self.uuid = uid
        self.machine_id = uid
        self.install_id = install_id
        self.device_id = uid
        self.token = None

    def auth_lookup_ids(self):
        result = [self.device_id]
        if self.install_id:
            result.append(self.install_id)
        return result


def _write_identity(data_dir: Path, *, machine_id: str, install_id: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "identity.json").write_text(
        json.dumps(
            {
                "version": 2,
                "uuid": machine_id,
                "machine_id": machine_id,
                "install_id": install_id,
                "machine_id_source": "windows_machine_guid",
                "token": None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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


@pytest.mark.asyncio
async def test_load_auth_token_falls_back_to_legacy_install_id_and_migrates(monkeypatch):
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    identity = _FakeIdentity("machine-dev", install_id="legacy-install")
    db = _FakeDb(tokens={"legacy-install": "legacy-token"})

    token = await load_auth_token(db, identity)

    assert token == "legacy-token"
    assert identity.token == "legacy-token"
    assert db.saved == [("legacy-token", "machine-dev")]


def test_import_missing_auth_token_from_data_roots_copies_token_for_same_machine(tmp_path):
    machine_id = "7a3429ec-1c0b-5495-9aad-b284f08ae965"
    source_data = tmp_path / "source-data"
    target_data = tmp_path / "target-data"

    _write_identity(source_data, machine_id=machine_id, install_id="1dad7556-bd05-4c5f-ac3a-cbdd176244e6")
    _write_identity(target_data, machine_id=machine_id, install_id="ea184549-1277-475e-bf83-a1db92f303e1")

    from pc_agent.core.database import DatabaseManager

    DatabaseManager._instance = None
    source_db = DatabaseManager(str(source_data / "storage.db"))
    asyncio.run(source_db.init_db())
    asyncio.run(source_db.save_auth_token("primary-token-value", machine_id))

    imported = import_missing_auth_token_from_data_roots(source_data, target_data)

    DatabaseManager._instance = None
    target_db = DatabaseManager(str(target_data / "storage.db"))
    asyncio.run(target_db.init_db())
    imported_token = asyncio.run(target_db.get_auth_token(machine_id))

    assert imported is True
    assert imported_token == "primary-token-value"


def test_import_missing_auth_token_from_data_roots_skips_machine_id_mismatch(tmp_path, monkeypatch):
    source_data = tmp_path / "source-data"
    target_data = tmp_path / "target-data"

    _write_identity(
        source_data,
        machine_id="7a3429ec-1c0b-5495-9aad-b284f08ae965",
        install_id="1dad7556-bd05-4c5f-ac3a-cbdd176244e6",
    )
    _write_identity(
        target_data,
        machine_id="11111111-2222-4333-8444-555555555555",
        install_id="ea184549-1277-475e-bf83-a1db92f303e1",
    )

    from pc_agent.core.database import DatabaseManager
    import pc_agent.core.identity as identity_module

    DatabaseManager._instance = None
    source_db = DatabaseManager(str(source_data / "storage.db"))
    asyncio.run(source_db.init_db())
    asyncio.run(source_db.save_auth_token("primary-token-value", "7a3429ec-1c0b-5495-9aad-b284f08ae965"))

    resolved_values = iter(
        [
            ("11111111-2222-4333-8444-555555555555", "test-target"),
            ("7a3429ec-1c0b-5495-9aad-b284f08ae965", "test-source"),
        ]
    )
    monkeypatch.setattr(identity_module, "resolve_machine_identity", lambda: next(resolved_values))

    imported = import_missing_auth_token_from_data_roots(source_data, target_data)

    assert imported is False
    assert not (target_data / "storage.db").exists()

