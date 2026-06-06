from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ServerRuntimeSnapshot

ADMIN_TOKEN = "test-ui-admin-token"
USER_TOKEN = "test-ui-user:plain-user"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ai_integration_mcp_endpoint_returns_manifest_and_runtime_snapshot(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add(
            ServerRuntimeSnapshot(
                process_kind="server",
                instance_id="api-test",
                pid=123,
                git_revision="abc1234",
                status="ok",
                collected_at=now,
                expires_at=now + timedelta(minutes=2),
                snapshot={
                    "service_health": {"api": "ok", "agent_ws_connections": 0},
                    "mcp": {"server": "helpdesk-server-debug", "mode": "debug_readonly"},
                },
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/admin/ai-integration/mcp", headers=_auth(ADMIN_TOKEN))

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["mcp"]["manifest"]["name"] == "helpdesk-server-debug"
    assert payload["mcp"]["runtime_status"]["status"] == "ok"
    assert payload["mcp"]["runtime_status"]["runtime_snapshot_available"] is True
    assert payload["mcp"]["runtime_status"]["snapshot"]["git_revision"] == "abc1234"
    assert payload["mcp"]["reload"]["required_after_deploy"] is True

    forbidden_response = await test_client.get("/api/web/admin/ai-integration/mcp", headers=_auth(USER_TOKEN))
    assert forbidden_response.status == 403
