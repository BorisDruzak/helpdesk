from types import SimpleNamespace

import pytest

from websocket.agent_services import HandshakeService
from websocket.contexts import AgentConnectionContext
from websocket.device_outbox_sender import ShardDispatcher


class _DispatchRecorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def on_agent_online(self, device_id: str) -> None:
        self.calls.append(device_id)


@pytest.mark.asyncio
async def test_handshake_service_wakes_dispatch_on_reconnect():
    """offline->online reconnect should trigger dispatch wakeup each handshake."""

    async def _legacy_handler(**_kwargs):
        return None, "agent-1", "device-1", True

    dispatch = _DispatchRecorder()
    handshake = HandshakeService(_legacy_handler, dispatch_service=dispatch)
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
    )

    result_first = await handshake.handle({"type": "handshake", "meta": {}}, ctx)
    # Simulate another connect cycle for the same device (offline -> online).
    result_second = await handshake.handle({"type": "handshake", "meta": {}}, ctx)

    assert result_first is None
    assert result_second is None
    assert dispatch.calls == ["device-1", "device-1"]


@pytest.mark.asyncio
async def test_shard_dispatcher_enqueues_multiple_devices_across_shards():
    dispatcher = ShardDispatcher(SimpleNamespace(), shards=4, fetch_limit=10, reconcile_seconds=30)
    scheduled: list[tuple[int, str]] = []

    for shard_id, service in enumerate(dispatcher.services):
        async def _record(device_id: str, current_shard: int = shard_id) -> None:
            scheduled.append((current_shard, device_id))

        service.enqueue_device = _record  # type: ignore[method-assign]

    await dispatcher.on_agent_online("device-A")
    await dispatcher.on_agent_online("device-B")

    scheduled_devices = {device_id for _, device_id in scheduled}
    assert scheduled_devices == {"device-A", "device-B"}
    assert len(scheduled) == 2


@pytest.mark.asyncio
async def test_shard_dispatcher_light_load_50_devices_no_scheduling_loss():
    dispatcher = ShardDispatcher(SimpleNamespace(), shards=8, fetch_limit=20, reconcile_seconds=30)
    scheduled: list[str] = []

    for service in dispatcher.services:
        async def _record(device_id: str) -> None:
            scheduled.append(device_id)

        service.enqueue_device = _record  # type: ignore[method-assign]

    total = 50
    for idx in range(total):
        await dispatcher.on_agent_online(f"device-{idx:02d}")

    assert len(scheduled) == total
    assert len(set(scheduled)) == total
