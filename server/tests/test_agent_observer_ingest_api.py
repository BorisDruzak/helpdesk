from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import AgentObserverEvent
from websocket.agent_services import AgentObserverTelemetryService
from websocket.contexts import AgentConnectionContext


class _FakeWs:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_agent_observer_ingest_uses_authenticated_context_device_not_payload() -> None:
    now = datetime.now(timezone.utc)
    ws = _FakeWs()
    ctx = AgentConnectionContext(
        ws=ws,
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="00000000-0000-0000-0000-00000000ab01",
        device_id="00000000-0000-0000-0000-00000000ab01",
        authenticated=True,
    )

    await AgentObserverTelemetryService().handle(
        {
            "type": "agent_observer_batch",
            "request_id": "req-agent-observer-1",
            "device_id": "spoofed-device",
            "events": [
                {
                    "event_id": "ws-agent-observer-1",
                    "event_type": "agent.ws.reconnect",
                    "severity": "warning",
                    "root_kind": "agent_runtime",
                    "component": "websocket",
                    "created_at": now.isoformat(),
                    "attrs_json": {"reason": "connection_lost"},
                }
            ],
        },
        ctx,
    )

    assert ws.sent[-1]["type"] == "agent_observer_batch_ack"
    assert ws.sent[-1]["request_id"] == "req-agent-observer-1"
    assert ws.sent[-1]["accepted_count"] == 1

    async with get_session() as session:
        row = (
            await session.execute(
                sa.select(AgentObserverEvent).where(AgentObserverEvent.event_id == "ws-agent-observer-1")
            )
        ).scalar_one()
        assert row.device_id == "00000000-0000-0000-0000-00000000ab01"


@pytest.mark.asyncio
async def test_agent_observer_ingest_rejects_unauthenticated_and_dedupes() -> None:
    now = datetime.now(timezone.utc)
    service = AgentObserverTelemetryService()
    ws = _FakeWs()
    unauthenticated = AgentConnectionContext(
        ws=ws,
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id=None,
        authenticated=False,
    )

    await service.handle(
        {"type": "agent_observer_batch", "request_id": "unauth", "events": []},
        unauthenticated,
    )
    assert ws.sent[-1]["status"] == "error"
    assert ws.sent[-1]["error_code"] == "UNAUTHENTICATED"

    authenticated = AgentConnectionContext(
        ws=ws,
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="00000000-0000-0000-0000-00000000ab11",
        authenticated=True,
    )
    message = {
        "type": "agent_observer_batch",
        "request_id": "dedupe",
        "events": [
            {
                "event_id": "ws-agent-observer-dedupe",
                "event_type": "agent.update.apply",
                "severity": "error",
                "root_kind": "agent_update",
                "component": "agent",
                "created_at": now.isoformat(),
                "attrs_json": {"reason": "failed once"},
            }
        ],
    }
    await service.handle(message, authenticated)
    await service.handle(message, authenticated)

    assert ws.sent[-1]["accepted_count"] == 1
    async with get_session() as session:
        count = (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(AgentObserverEvent)
                .where(AgentObserverEvent.event_id == "ws-agent-observer-dedupe")
            )
        ).scalar_one()
        assert count == 1
