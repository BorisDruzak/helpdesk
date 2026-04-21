import asyncio

import pytest

import websocket.device_outbox_sender as sender_module
from websocket.device_outbox_sender import DeviceReadyQueue, DeviceOutboxSender, ShardDispatcher


@pytest.mark.asyncio
async def test_device_ready_queue_deduplicates_until_popped():
    queue = DeviceReadyQueue()
    await queue.enqueue("device-1")
    await queue.enqueue("device-1")
    await queue.enqueue("device-1")

    first = await queue.pop()
    assert first == "device-1"

    # After pop the device can be scheduled again.
    await queue.enqueue("device-1")
    second = await queue.pop()
    assert second == "device-1"


@pytest.mark.asyncio
async def test_device_ready_queue_size_tracks_depth():
    queue = DeviceReadyQueue()
    assert await queue.size() == 0
    await queue.enqueue("d1")
    await queue.enqueue("d2")
    await queue.enqueue("d2")  # dedupe
    assert await queue.size() == 2
    await queue.pop()
    assert await queue.size() == 1


@pytest.mark.asyncio
async def test_shard_dispatcher_keeps_same_device_in_same_shard():
    class _DummyState:
        pass

    dispatcher = ShardDispatcher(_DummyState(), shards=4, fetch_limit=10, reconcile_seconds=30)
    shard_ids = [
        dispatcher.services[0]._device_to_shard("stable-device")
        for _ in range(5)
    ]
    assert len(set(shard_ids)) == 1
    assert len(dispatcher.services) == 4


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_device_outbox_sender_stop_async_waits_for_polling_loop(monkeypatch):
    class _DummyState:
        pass

    monkeypatch.setattr(sender_module, "DEVICE_DISPATCH_MODE", "poll")
    sender = DeviceOutboxSender(_DummyState(), poll_interval=60.0)

    await sender.start_async()
    polling_impl = sender._polling_impl

    assert polling_impl is not None
    assert polling_impl._task is not None
    assert polling_impl._task.done() is False

    await sender.stop_async()

    assert polling_impl._task is None


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_device_outbox_sender_stop_async_waits_for_sharded_dispatcher(monkeypatch):
    class _DummyDispatcher:
        def __init__(self, *args, **kwargs):
            self.started = 0
            self.stopped = 0

        async def start(self) -> None:
            self.started += 1

        async def stop(self) -> None:
            self.stopped += 1

    class _DummyState:
        pass

    monkeypatch.setattr(sender_module, "DEVICE_DISPATCH_MODE", "sharded")
    monkeypatch.setattr(sender_module, "ShardDispatcher", _DummyDispatcher)

    sender = DeviceOutboxSender(_DummyState(), poll_interval=1.0)
    dispatcher = sender._sharded_impl

    assert dispatcher is not None

    await sender.start_async()
    await sender.stop_async()

    assert dispatcher.started == 1
    assert dispatcher.stopped == 1
