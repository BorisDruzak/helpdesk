import asyncio
from types import SimpleNamespace

import pytest

import websocket.device_outbox_sender as sender_module
from websocket.device_outbox_sender import (
    DeviceDispatchService,
    DeviceReadyQueue,
    DeviceOutboxSender,
    PollingDeviceOutboxSender,
    ShardDispatcher,
)


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


class _FakeSession:
    def __init__(self, events):
        self.events = events

    async def commit(self):
        self.events.append("commit")


class _FakeSessionFactory:
    def __init__(self, events):
        self.events = events

    async def __aenter__(self):
        return _FakeSession(self.events)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeOnlineState:
    def __init__(self):
        self.ui_publisher = None

    def is_agent_online(self, device_id):
        return True

    def get_agent(self, device_id):
        return {"ws": object(), "metadata": {"device_id": device_id}}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_sharded_dispatch_commits_each_command_before_next_send(monkeypatch):
    events = []
    commands = [
        SimpleNamespace(id=1, command_id="cmd-1", device_id="device-1"),
        SimpleNamespace(id=2, command_id="cmd-2", device_id="device-1"),
    ]

    class _FakeRepo:
        def __init__(self, session):
            self.session = session

        async def claim_dispatch_ready_device(self, **kwargs):
            return True

        async def get_pending_commands_for_device(self, **kwargs):
            return commands

        async def has_pending_for_device(self, **kwargs):
            return False

        async def release_dispatch_ready_device(self, device_id):
            events.append(f"release:{device_id}")

    async def fake_send_single_command(state, ws, agent_device_id, cmd, repo):
        events.append(f"send:{cmd.command_id}")

    monkeypatch.setattr(sender_module, "get_session", lambda: _FakeSessionFactory(events))
    monkeypatch.setattr(sender_module, "DeviceOutboxRepo", _FakeRepo)
    monkeypatch.setattr(sender_module, "_send_single_command", fake_send_single_command)

    service = DeviceDispatchService(
        state_manager=_FakeOnlineState(),
        shard_id=0,
        shard_count=1,
        fetch_limit=10,
        lease_seconds=30,
        instance_id="test-dispatcher",
    )
    service._running = True

    await service._drain_device("device-1")

    assert events.index("send:cmd-1") < events.index("send:cmd-2")
    first_send_index = events.index("send:cmd-1")
    second_send_index = events.index("send:cmd-2")
    assert "commit" in events[first_send_index + 1 : second_send_index]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_polling_dispatch_commits_each_command_before_next_send(monkeypatch):
    events = []
    commands = [
        SimpleNamespace(id=1, command_id="cmd-1", device_id="device-1"),
        SimpleNamespace(id=2, command_id="cmd-2", device_id="device-1"),
    ]

    class _FakeRepo:
        def __init__(self, session):
            self.session = session

        async def get_all_pending_commands(self, limit):
            return commands

    async def fake_send_single_command(state, ws, agent_device_id, cmd, repo):
        events.append(f"send:{cmd.command_id}")

    monkeypatch.setattr(sender_module, "get_session", lambda: _FakeSessionFactory(events))
    monkeypatch.setattr(sender_module, "DeviceOutboxRepo", _FakeRepo)
    monkeypatch.setattr(sender_module, "_send_single_command", fake_send_single_command)

    sender = PollingDeviceOutboxSender(_FakeOnlineState(), poll_interval=60.0)

    await sender._process_pending_commands()

    assert events.index("send:cmd-1") < events.index("send:cmd-2")
    first_send_index = events.index("send:cmd-1")
    second_send_index = events.index("send:cmd-2")
    assert "commit" in events[first_send_index + 1 : second_send_index]
