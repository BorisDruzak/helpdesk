import uuid

import pytest


@pytest.mark.asyncio
async def test_tools_run_async_returns_poll_url(test_client, monkeypatch):
    operation_id = str(uuid.uuid4())

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "operation_id": operation_id,
            "device_id": "device-async-1",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client.post(
        "/api/tools/run",
        json={
            "device_id": "device-async-1",
            "ticket_id": "ticket-async-1",
            "tool_name": "echo",
            "params": {"message": "hello"},
        },
    )
    assert response.status == 202
    payload = await response.json()

    assert payload["status"] == "accepted"
    assert payload["operation_id"] == operation_id
    assert payload["poll_url"] == f"/api/operations/{operation_id}"
