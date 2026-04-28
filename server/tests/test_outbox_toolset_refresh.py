from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.db import get_session
from app.db.models import Device
from websocket.outbox_ingest_components import OutboxEventPublishService, OutboxPersistenceOutcome


@pytest.mark.asyncio
async def test_tools_changed_event_enqueues_list_tools_refresh():
    device_id = "device-tools-refresh"
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="tools-refresh-host",
                os="windows",
                capabilities={},
                device_metadata={},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    issued: list[dict] = []

    async def fake_enqueue_command_async(**kwargs):
        issued.append(kwargs)
        return "list-tools-op"

    ctx = SimpleNamespace(agent_id=device_id, state=SimpleNamespace())
    outcome = OutboxPersistenceOutcome(
        should_continue=True,
        decision="ack",
        outbox_id="outbox-tools-changed",
        trace_id="trace-tools-changed",
        event_type="tools_changed",
        payload_event={
            "event": "tools_changed",
            "toolset_hash": "new-toolset-hash",
            "tools_count": 3,
        },
    )

    with patch("websocket.protocol.enqueue_command_async", new=fake_enqueue_command_async):
        await OutboxEventPublishService().publish_after_commit(ctx=ctx, outcome=outcome)

    assert [item["command"] for item in issued] == ["list_tools"]
    assert issued[0]["device_id"] == device_id
    assert issued[0]["actor_role"] == "server"
    assert issued[0]["trace_id"] == "trace-tools-changed"
    assert issued[0]["require_online"] is False
