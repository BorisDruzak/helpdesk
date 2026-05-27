from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from websocket.agent_services import HandshakeService
from websocket.agent_handshake import handle_handshake
from websocket.contexts import AgentConnectionContext


pytestmark = pytest.mark.no_db


class _WsStub:
    def __init__(self) -> None:
        self.closed = False
        self.close_code = None
        self.close_message = None

    async def close(self, code=None, message=None):
        self.closed = True
        self.close_code = code
        self.close_message = message


class _DispatchStub:
    def __init__(self) -> None:
        self.on_agent_online = AsyncMock()


@pytest.mark.asyncio
async def test_handshake_service_does_not_dispatch_diagnostic_probe_online():
    ws = _WsStub()
    dispatch = _DispatchStub()

    async def legacy_handler(**_kwargs):
        setattr(ws, "_pc_client_connection_id", "probe-conn")
        setattr(ws, "_pc_client_client_kind", "diagnostic_probe")
        setattr(
            ws,
            "_pc_client_session_metadata",
            {
                "device_id": "device-1",
                "connection_id": "probe-conn",
                "client_kind": "diagnostic_probe",
            },
        )
        return None, "device-1", "device-1", True

    state = SimpleNamespace(get_agent=lambda _device_id: None)
    ctx = AgentConnectionContext(ws=ws, request=SimpleNamespace(), state=state)
    service = HandshakeService(legacy_handler, dispatch_service=dispatch)

    await service.handle(
        {
            "type": "handshake",
            "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        },
        ctx,
    )

    assert ctx.authenticated is True
    assert ctx.connection_id == "probe-conn"
    assert ctx.session_metadata["client_kind"] == "diagnostic_probe"
    dispatch.on_agent_online.assert_not_awaited()


@pytest.mark.asyncio
async def test_handshake_service_dispatches_runtime_agent_online():
    ws = _WsStub()
    dispatch = _DispatchStub()
    agent_info = {
        "ws": ws,
        "metadata": {
            "device_id": "device-1",
            "connection_id": "runtime-conn",
            "client_kind": "agent_runtime",
        },
    }

    async def legacy_handler(**_kwargs):
        return None, "device-1", "device-1", True

    state = SimpleNamespace(get_agent=lambda _device_id: agent_info)
    ctx = AgentConnectionContext(ws=ws, request=SimpleNamespace(), state=state)
    service = HandshakeService(legacy_handler, dispatch_service=dispatch)

    await service.handle(
        {
            "type": "handshake",
            "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        },
        ctx,
    )

    assert ctx.session_metadata["client_kind"] == "agent_runtime"
    dispatch.on_agent_online.assert_awaited_once_with("device-1")


@pytest.mark.asyncio
async def test_invalid_client_kind_is_rejected_before_runtime_registration():
    ws = _WsStub()
    state = SimpleNamespace(register_agent=AsyncMock())

    result = await handle_handshake(
        ws=ws,
        data={
            "type": "handshake",
            "protocol_version": "ws_ticket_v3",
            "token": "not-needed-before-client-kind-validation",
            "payload": {"client_kind": "raw_probe"},
            "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        },
        request=SimpleNamespace(remote="127.0.0.1", headers={}),
        state=state,
    )

    assert result[0] is ws
    assert ws.closed is True
    assert ws.close_code == 4003
