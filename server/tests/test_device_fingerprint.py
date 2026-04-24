from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import AgentToken, Device
from app.repos.auth_tokens_repo import AuthTokensRepo
from auth.device_fingerprint import compare_device_fingerprints, normalize_device_fingerprint
from auth.service import AuthService


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
async def test_generate_agent_token_rotates_old_active_tokens(test_client):
    device_id = str(uuid.uuid4())
    auth_service = AuthService(test_client.app["state"])

    first = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)
    second = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)
    third = await auth_service.generate_agent_token(device_id=device_id, expires_hours=24)

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AgentToken)
                .where(AgentToken.device_id == device_id)
                .order_by(AgentToken.created_at.asc())
            )
        ).scalars().all()

    assert {AuthTokensRepo.hash_token(first), AuthTokensRepo.hash_token(second), AuthTokensRepo.hash_token(third)} == {
        row.token_hash for row in rows
    }
    assert sum(1 for row in rows if row.revoked_at is None) == 1
    assert rows[-1].token_hash == AuthTokensRepo.hash_token(third)


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
