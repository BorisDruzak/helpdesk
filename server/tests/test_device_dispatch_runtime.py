import asyncio

import pytest

from websocket.device_outbox_sender import DeviceReadyQueue, ShardDispatcher


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
    shard_ids = [abs(hash("stable-device")) % dispatcher.shards for _ in range(5)]
    assert len(set(shard_ids)) == 1
    assert len(dispatcher.services) == 4
