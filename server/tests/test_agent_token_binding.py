from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import AgentToken, Device
from auth.service import AuthService
from app.repos.auth_tokens_repo import AuthTokensRepo
from websocket.agent_handshake import handle_handshake


pytestmark = pytest.mark.db_cleanup("agent_runtime")

class _HandshakeWsStub:
    def __init__(self) -> None:
        self.closed = False
        self.close_code = None
        self.close_message = None
        self.sent_payloads = []

    async def close(self, code=None, message=None):
        self.closed = True
        self.close_code = code
        self.close_message = message

    async def send_json(self, payload):
        self.sent_payloads.append(payload)


async def _insert_real_device(device_id: str, *, hostname: str = "known-host") -> None:
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
                protocol_version="ws_ticket_v3",
                agent_version="3.0.1",
                hostname=hostname,
                os="Windows",
                capabilities={"protocol_v3": True},
                tools_version="tools_v1",
                current_toolset_hash="known-toolset",
                device_metadata={"modules": ["system"]},
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_generate_agent_token_creates_placeholder_device_for_fk(test_client):
    device_id = str(uuid.uuid4())
    auth_service = AuthService(test_client.app["state"])

    token = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)

    assert token
    async with get_session() as session:
        device = await session.get(Device, device_id)
        token_row = (
            await session.execute(
                select(AgentToken).where(AgentToken.token_hash == AuthTokensRepo.hash_token(token))
            )
        ).scalar_one_or_none()

    assert device is not None
    assert device.protocol_version == "pending"
    assert device.agent_version == ""
    assert device.hostname is None
    assert token_row is not None
    assert token_row.device_id == device_id


@pytest.mark.asyncio
async def test_handshake_rebinds_fresh_token_to_existing_device(test_client):
    existing_device_id = str(uuid.uuid4())
    fresh_token_device_id = str(uuid.uuid4())
    await _insert_real_device(existing_device_id)

    auth_service = AuthService(test_client.app["state"])
    token = await auth_service.generate_agent_token(
        device_id=fresh_token_device_id,
        expires_hours=24,
    )

    ws = _HandshakeWsStub()
    request = SimpleNamespace(remote="127.0.0.1", headers={"User-Agent": "pytest"})
    handshake_message = {
        "type": "handshake",
        "protocol_version": "ws_ticket_v3",
        "device_id": existing_device_id,
        "token": token,
        "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        "payload": {
            "uuid": existing_device_id,
            "device_id": existing_device_id,
            "hostname": "known-host",
            "agent_version": "3.0.1",
            "os": "Windows",
            "os_type": "windows",
            "modules": [],
        },
    }

    _, _, resolved_device_id, authenticated = await handle_handshake(
        ws=ws,
        data=handshake_message,
        request=request,
        state=test_client.app["state"],
    )

    assert authenticated is True
    assert ws.closed is False
    assert resolved_device_id == existing_device_id

    async with get_session() as session:
        rebound_token = (
            await session.execute(
                select(AgentToken).where(AgentToken.token_hash == AuthTokensRepo.hash_token(token))
            )
        ).scalar_one()
        rebound_device = await session.get(Device, existing_device_id)
        phantom_device = await session.get(Device, fresh_token_device_id)

    assert rebound_token.device_id == existing_device_id
    assert rebound_device is not None
    assert phantom_device is None


@pytest.mark.asyncio
async def test_handshake_rebinds_legacy_install_token_to_machine_id(test_client):
    legacy_install_id = str(uuid.uuid4())
    canonical_machine_id = str(uuid.uuid4())
    await _insert_real_device(legacy_install_id, hostname="legacy-install-host")

    auth_service = AuthService(test_client.app["state"])
    token = await auth_service.generate_agent_token(
        device_id=legacy_install_id,
        expires_hours=24,
    )

    ws = _HandshakeWsStub()
    request = SimpleNamespace(remote="127.0.0.1", headers={"User-Agent": "pytest"})
    handshake_message = {
        "type": "handshake",
        "protocol_version": "ws_ticket_v3",
        "device_id": canonical_machine_id,
        "token": token,
        "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        "payload": {
            "uuid": canonical_machine_id,
            "machine_id": canonical_machine_id,
            "install_id": legacy_install_id,
            "hostname": "canonical-host",
            "agent_version": "3.1.0",
            "os": "Windows",
            "os_type": "windows",
            "modules": [],
        },
    }

    _, _, resolved_device_id, authenticated = await handle_handshake(
        ws=ws,
        data=handshake_message,
        request=request,
        state=test_client.app["state"],
    )

    assert authenticated is True
    assert ws.closed is False
    assert resolved_device_id == canonical_machine_id

    async with get_session() as session:
        rebound_token = (
            await session.execute(
                select(AgentToken).where(AgentToken.token_hash == AuthTokensRepo.hash_token(token))
            )
        ).scalar_one()
        canonical_device = await session.get(Device, canonical_machine_id)
        legacy_device = await session.get(Device, legacy_install_id)

    assert rebound_token.device_id == canonical_machine_id
    assert canonical_device is not None
    assert legacy_device is not None
