from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.engine import async_sessionmaker
from app.db.models import Ticket

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_admin_run_tool_system_ticket_uses_canonical_status(test_client, test_engine, monkeypatch):
    device_id = "device-admin-run-tool-canonical"
    test_client.app["state"].is_agent_online = lambda checked_device_id: checked_device_id == device_id

    async def _fake_run_tool(self, **kwargs):
        assert kwargs["device_id"] == device_id
        assert kwargs["ticket_id"]
        assert kwargs["tool_name"] == "inventory.collect"
        return {"payload": {"status": "success", "data": {"ok": True}}}

    monkeypatch.setattr("api.admin.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client.post(
        "/api/admin/run_tool",
        json={
            "device_id": device_id,
            "tool_name": "inventory.collect",
            "params": {},
        },
    )
    payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "ok"
    assert payload["ticket_id"]

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.scalar(select(Ticket).where(Ticket.ticket_id == payload["ticket_id"]))

    assert ticket is not None
    assert ticket.status == "in_progress"
