from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import Device, Operation


ADMIN_TOKEN = "test-ui-admin-token"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_observer_settings_api_roundtrip_and_runtime_health_fields(test_client):
    response = await test_client.get("/api/admin/settings/observer", headers=_auth())
    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["settings"]["success_trace_sample_rate"] >= 0
    assert payload["settings"]["ok_trace_retention_hours"] >= 1

    patch_response = await test_client.patch(
        "/api/admin/settings/observer",
        headers=_auth(),
        json={
            "success_trace_sample_rate": 0.5,
            "ok_trace_retention_hours": 12,
            "error_trace_retention_hours": 72,
            "action_sync_limit": 90,
        },
    )
    assert patch_response.status == 200
    patched = await patch_response.json()
    assert patched["status"] == "ok"
    assert patched["settings"]["success_trace_sample_rate"] == pytest.approx(0.5)
    assert patched["settings"]["ok_trace_retention_hours"] == 12
    assert patched["settings"]["error_trace_retention_hours"] == 72
    assert patched["settings"]["action_sync_limit"] == 90

    runtime_response = await test_client.get("/api/admin/tech/traces/runtime", headers=_auth())
    assert runtime_response.status == 200
    runtime_payload = await runtime_response.json()
    assert runtime_payload["status"] == "ok"
    assert "settings" in runtime_payload["runtime"]
    assert "health" in runtime_payload["runtime"]


@pytest.mark.asyncio
async def test_observer_settings_sampling_config_does_not_block_explicit_trace_search(test_client):
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000f611"
    device_id = "00000000-0000-0000-0000-00000000f612"
    operation_id = "00000000-0000-0000-0000-00000000f613"

    patch_response = await test_client.patch(
        "/api/admin/settings/observer",
        headers=_auth(),
        json={
            "success_trace_sample_rate": 0.0,
            "always_keep_root_kinds": ["ticket", "agent_update", "module_install"],
        },
    )
    assert patch_response.status == 200

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.18",
                hostname="observer-sampling-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=20),
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="support",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now - timedelta(seconds=20),
                started_at=now - timedelta(seconds=19),
                finished_at=now - timedelta(seconds=18),
                result_summary="ok",
            )
        )
        await session.commit()

    # Warm search can always materialize on-demand.
    search_response = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert search_response.status == 200
    payload = await search_response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 1
