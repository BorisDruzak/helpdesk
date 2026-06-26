from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import AgentToken, Device
from app.repos.auth_tokens_repo import AuthTokensRepo
from auth.device_fingerprint import compare_device_fingerprints, normalize_device_fingerprint
from auth.service import AuthService
from websocket import agent_handshake


pytestmark = pytest.mark.db_cleanup("agent_runtime")

def _fingerprint(**overrides):
    base = {
        "schema": "device_fingerprint_v1",
        "components": {
            "system_uuid": "sys-a",
            "baseboard": "board-a",
            "cpu": "cpu-a",
            "boot_volume": "disk-a",
        },
        "mac_hashes": ["mac-a", "mac-b"],
    }
    for key, value in overrides.items():
        if key == "components":
            base["components"] = {**base["components"], **value}
        else:
            base[key] = value
    return base


def test_device_fingerprint_allows_one_changed_component():
    stored = normalize_device_fingerprint(_fingerprint())
    incoming = normalize_device_fingerprint(_fingerprint(components={"baseboard": "board-b"}))

    verdict = compare_device_fingerprints(stored, incoming)

    assert verdict.allowed is True
    assert verdict.mismatched_count == 1
    assert verdict.comparable_count >= 4


def test_device_fingerprint_blocks_multiple_changed_components():
    stored = normalize_device_fingerprint(_fingerprint())
    incoming = normalize_device_fingerprint(
        _fingerprint(
            components={
                "baseboard": "board-b",
                "cpu": "cpu-b",
            },
            mac_hashes=["mac-z"],
        )
    )

    verdict = compare_device_fingerprints(stored, incoming)

    assert verdict.allowed is False
    assert verdict.mismatched_count >= 2
    assert verdict.status == "mismatch"


@pytest.mark.asyncio
async def test_generate_agent_token_enforces_active_token_limit(test_client):
    device_id = str(uuid.uuid4())
    auth_service = AuthService(test_client.app["state"])

    first = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)
    second = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)
    with pytest.raises(ValueError, match="Active agent token limit exceeded"):
        await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AgentToken)
                .where(AgentToken.device_id == device_id)
                .order_by(AgentToken.created_at.asc())
            )
        ).scalars().all()

    assert {AuthTokensRepo.hash_token(first), AuthTokensRepo.hash_token(second)} == {row.token_hash for row in rows}
    assert sum(1 for row in rows if row.revoked_at is None) == 2


@pytest.mark.asyncio
async def test_generate_agent_token_explicit_rotation_revokes_old_active_tokens(test_client):
    device_id = str(uuid.uuid4())
    auth_service = AuthService(test_client.app["state"])

    first = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)
    second = await auth_service.generate_agent_token(
        device_id=device_id,
        expires_hours=24,
        replace_existing=True,
    )

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AgentToken)
                .where(AgentToken.device_id == device_id)
                .order_by(AgentToken.created_at.asc())
            )
        ).scalars().all()

    assert {AuthTokensRepo.hash_token(first), AuthTokensRepo.hash_token(second)} == {row.token_hash for row in rows}
    assert sum(1 for row in rows if row.revoked_at is None) == 1
    assert rows[-1].token_hash == AuthTokensRepo.hash_token(second)


@pytest.mark.asyncio
async def test_connection_request_blocks_fingerprint_mismatch(test_client, test_engine):
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.0",
                hostname="secure-host",
                os="Windows",
                capabilities={},
                device_metadata={
                    "machine_id": device_id,
                    "device_fingerprint": _fingerprint(),
                },
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/connection_request",
        json={
            "device_id": device_id,
            "hostname": "secure-host",
            "metadata": {
                "machine_id": device_id,
                "device_fingerprint": _fingerprint(
                    components={"baseboard": "board-b", "cpu": "cpu-b"},
                    mac_hashes=["mac-z"],
                ),
            },
        },
    )
    payload = await response.json()

    assert response.status == 409
    assert payload["status"] == "blocked"
    assert payload["error_code"] == "DEVICE_FINGERPRINT_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_handshake_rebind_keeps_token_on_original_device_when_fingerprint_mismatches(monkeypatch):
    token_device_id = str(uuid.uuid4())
    payload_device_id = str(uuid.uuid4())
    token_hash = AuthTokensRepo.hash_token(f"agent-rebind-{uuid.uuid4().hex}")
    token_binding = {"device_id": token_device_id}
    devices = {
        token_device_id: SimpleNamespace(
            device_id=token_device_id,
            deleted_at=None,
            protocol_version="pending",
            agent_version="",
            hostname=None,
            os=None,
            current_toolset_hash=None,
            device_metadata={},
        ),
        payload_device_id: SimpleNamespace(
            device_id=payload_device_id,
            deleted_at=None,
            protocol_version="ws_ticket_v3",
            agent_version="3.1.0",
            hostname="known-agent-host",
            os="Windows",
            current_toolset_hash="toolset-a",
            device_metadata={
                "machine_id": payload_device_id,
                "device_fingerprint": _fingerprint(),
            },
        ),
    }

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_get_by_device_id(self, device_id, *, include_deleted=True):
        return devices.get(device_id)

    async def fake_rebind_agent_token(self, token_hash, new_device_id, *, expected_device_id=None):
        assert expected_device_id == token_device_id
        token_binding["device_id"] = new_device_id
        return True

    async def fake_get_agent_tokens_by_device(self, device_id):
        return [object()] if token_binding["device_id"] == device_id else []

    async def fake_write_agent_runtime_audit(**_kwargs):
        return None

    monkeypatch.setattr(agent_handshake, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_handshake, "ENABLE_DB_PERSISTENCE", True)
    monkeypatch.setattr(agent_handshake, "get_session", lambda: FakeSessionContext())
    monkeypatch.setattr(agent_handshake, "write_agent_runtime_audit", fake_write_agent_runtime_audit)
    monkeypatch.setattr("app.repos.devices_repo.DevicesRepo.get_by_device_id", fake_get_by_device_id)
    monkeypatch.setattr("app.repos.auth_tokens_repo.AuthTokensRepo.rebind_agent_token", fake_rebind_agent_token)
    monkeypatch.setattr("app.repos.auth_tokens_repo.AuthTokensRepo.get_agent_tokens_by_device", fake_get_agent_tokens_by_device)

    token_info = {
        "device_id": token_device_id,
        "token_hash": token_hash,
        "token_prefix": token_hash[:8],
    }
    mismatched_fingerprint = _fingerprint(
        components={"baseboard": "board-b", "cpu": "cpu-b"},
        mac_hashes=["mac-z"],
    )

    resolved_device_id = await agent_handshake._resolve_handshake_device_id(
        token_info=token_info,
        payload_device_id=payload_device_id,
        payload_install_id=None,
        payload_fingerprint=mismatched_fingerprint,
    )
    fingerprint_allowed, fingerprint_verdict = await agent_handshake._handshake_fingerprint_allowed(
        resolved_device_id,
        mismatched_fingerprint,
    )

    assert resolved_device_id == payload_device_id
    assert fingerprint_allowed is False
    assert fingerprint_verdict["status"] == "mismatch"
    assert token_binding["device_id"] == token_device_id


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_handshake_rebind_uses_expected_original_token_binding(monkeypatch):
    token_device_id = str(uuid.uuid4())
    payload_device_id = str(uuid.uuid4())
    competing_device_id = str(uuid.uuid4())
    token_hash = AuthTokensRepo.hash_token(f"agent-rebind-{uuid.uuid4().hex}")
    token_binding = {"device_id": token_device_id}
    expected_bindings: list[str | None] = []
    fingerprint = _fingerprint()
    devices = {
        payload_device_id: SimpleNamespace(
            device_id=payload_device_id,
            deleted_at=None,
            protocol_version="ws_ticket_v3",
            agent_version="3.1.0",
            hostname="known-agent-host",
            os="Windows",
            current_toolset_hash="toolset-a",
            device_metadata={
                "machine_id": payload_device_id,
                "device_fingerprint": fingerprint,
            },
        ),
    }

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_get_by_device_id(self, device_id, *, include_deleted=True):
        return devices.get(device_id)

    async def fake_rebind_agent_token(self, token_hash, new_device_id, *, expected_device_id=None):
        expected_bindings.append(expected_device_id)
        if expected_device_id != token_binding["device_id"]:
            return False
        token_binding["device_id"] = new_device_id
        return True

    async def fake_get_agent_tokens_by_device(self, device_id):
        return [object()] if token_binding["device_id"] == device_id else []

    async def fake_write_agent_runtime_audit(**_kwargs):
        return None

    monkeypatch.setattr(agent_handshake, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_handshake, "ENABLE_DB_PERSISTENCE", True)
    monkeypatch.setattr(agent_handshake, "get_session", lambda: FakeSessionContext())
    monkeypatch.setattr(agent_handshake, "write_agent_runtime_audit", fake_write_agent_runtime_audit)
    monkeypatch.setattr("app.repos.devices_repo.DevicesRepo.get_by_device_id", fake_get_by_device_id)
    monkeypatch.setattr("app.repos.auth_tokens_repo.AuthTokensRepo.rebind_agent_token", fake_rebind_agent_token)
    monkeypatch.setattr("app.repos.auth_tokens_repo.AuthTokensRepo.get_agent_tokens_by_device", fake_get_agent_tokens_by_device)

    token_info = {
        "device_id": token_device_id,
        "token_hash": token_hash,
        "token_prefix": token_hash[:8],
    }

    resolved_device_id = await agent_handshake._resolve_handshake_device_id(
        token_info=token_info,
        payload_device_id=payload_device_id,
        payload_install_id=None,
        payload_fingerprint=fingerprint,
    )

    assert resolved_device_id == payload_device_id
    assert expected_bindings == [token_device_id]
    assert token_binding["device_id"] == payload_device_id

    token_binding["device_id"] = competing_device_id
    expected_bindings.clear()

    resolved_device_id = await agent_handshake._resolve_handshake_device_id(
        token_info=token_info,
        payload_device_id=payload_device_id,
        payload_install_id=None,
        payload_fingerprint=fingerprint,
    )

    assert resolved_device_id == token_device_id
    assert expected_bindings == [token_device_id]
    assert token_binding["device_id"] == competing_device_id
