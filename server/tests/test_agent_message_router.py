from types import SimpleNamespace

import pytest

from websocket.agent_services import AgentMessageRouter
from websocket.contexts import AgentConnectionContext, EnvelopeContext

pytestmark = pytest.mark.no_db


class _StubService:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result

    async def handle(self, *args, **kwargs):
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_router_routes_handshake_to_service():
    handshake = _StubService(result=None)
    ack = _StubService()
    result = _StubService()
    rpc = _StubService()
    outbox = _StubService()
    command = _StubService()
    router = AgentMessageRouter(handshake, ack, result, rpc, outbox, command)

    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(get_agent=lambda _id: None),
    )
    envelope = EnvelopeContext.from_message({"type": "handshake"})
    await router.route({"type": "handshake"}, ctx, envelope)

    assert handshake.calls == 1
    assert ack.calls == 0
    assert result.calls == 0


@pytest.mark.asyncio
async def test_router_returns_continue_for_outbox_true():
    router = AgentMessageRouter(
        handshake_service=_StubService(),
        command_ack_service=_StubService(),
        command_result_service=_StubService(),
        rpc_response_service=_StubService(),
        outbox_ingest_service=_StubService(result=True),
        agent_command_service=_StubService(),
    )
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(get_agent=lambda _id: None),
    )
    envelope = EnvelopeContext.from_message({"type": "outbox_item"})
    result = await router.route({"type": "outbox_item"}, ctx, envelope)
    assert result == "__continue__"
