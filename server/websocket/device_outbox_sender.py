"""
Device outbox runtime.

Supports two internal dispatch modes:
- poll: legacy poll-all loop
- sharded: push-first per-device dispatch with reconcile sweep
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos import DeviceOutboxRepo
from config import (
    DEVICE_DISPATCH_FETCH_LIMIT,
    DEVICE_DISPATCH_MODE,
    DEVICE_DISPATCH_RECONCILE_SECONDS,
    DEVICE_DISPATCH_SHARDS,
)


class DeviceReadyQueue:
    """Queue of ready device IDs with dedupe via ready-set."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        self._ready: set[str] = set()
        self._cv = asyncio.Condition()

    async def enqueue(self, device_id: str) -> None:
        async with self._cv:
            if device_id not in self._ready:
                self._ready.add(device_id)
                self._queue.append(device_id)
                self._cv.notify(1)

    async def pop(self) -> str:
        async with self._cv:
            while not self._queue:
                await self._cv.wait()
            device_id = self._queue.popleft()
            self._ready.discard(device_id)
            return device_id

    async def size(self) -> int:
        async with self._cv:
            return len(self._queue)


class DeviceDispatchService:
    """Push-first, per-device sequential dispatcher."""

    def __init__(self, state_manager, shard_id: int, shard_count: int, fetch_limit: int) -> None:
        self.state = state_manager
        self.shard_id = shard_id
        self.shard_count = shard_count
        self.fetch_limit = fetch_limit
        self._queue = DeviceReadyQueue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker(), name=f"device-dispatch-{self.shard_id}")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._queue.enqueue("__stop__")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def enqueue_device(self, device_id: str) -> None:
        if self._device_to_shard(device_id) != self.shard_id:
            return
        await self._queue.enqueue(device_id)
        queue_len = await self._queue.size()
        if queue_len >= 100:
            logger.warning(
                f"[DeviceDispatchService] queue pressure: shard={self.shard_id} size={queue_len}"
            )

    async def on_agent_online(self, device_id: str) -> None:
        await self.enqueue_device(device_id)

    async def _worker(self) -> None:
        while self._running:
            device_id = await self._queue.pop()
            if device_id == "__stop__":
                continue
            try:
                await self._drain_device(device_id)
            except Exception as exc:
                logger.error(f"[DeviceDispatchService] drain failed: device_id={device_id} error={exc}", exc_info=True)

    def _device_to_shard(self, device_id: str) -> int:
        return abs(hash(device_id)) % self.shard_count

    async def _drain_device(self, device_id: str) -> None:
        if not self.state.is_agent_online(device_id):
            return
        started_at = datetime.now(timezone.utc)
        while self._running:
            async with get_session() as session:
                repo = DeviceOutboxRepo(session)
                pending = await repo.get_pending_commands_for_device(device_id=device_id, limit=self.fetch_limit)
                if not pending:
                    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                    logger.debug(
                        f"[DeviceDispatchService] drained device_id={device_id} shard={self.shard_id} "
                        f"elapsed_ms={elapsed_ms}"
                    )
                    return

                agent_info = self.state.get_agent(device_id)
                if not agent_info:
                    return
                ws = agent_info["ws"]
                metadata = agent_info.get("metadata", {})
                agent_device_id = metadata.get("device_id", device_id)

                for cmd in pending:
                    try:
                        await _send_single_command(self.state, ws, agent_device_id, cmd, repo)
                    except Exception as exc:
                        logger.error(
                            f"[DeviceDispatchService] Failed to send command: device_id={device_id} "
                            f"command_id={cmd.command_id} error={exc}"
                        )
                        await repo.mark_as_failed(
                            outbox_id=cmd.id,
                            error_code="SEND_ERROR",
                            error_message=str(exc),
                            should_retry=True,
                        )
                        break
                await session.commit()

                has_more = await repo.has_pending_for_device(device_id=device_id)
                if not has_more:
                    return


class DispatchReconciler:
    """Safety sweep in case wakeups are missed."""

    def __init__(self, dispatch_services: list[DeviceDispatchService], interval_seconds: int = 30) -> None:
        self.dispatch_services = dispatch_services
        self.interval_seconds = max(5, interval_seconds)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="device-dispatch-reconciler")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval_seconds)
            for service in self.dispatch_services:
                try:
                    async with get_session() as session:
                        repo = DeviceOutboxRepo(session)
                        device_ids = await repo.list_devices_with_pending(
                            limit=200,
                            shard_id=service.shard_id,
                            shard_count=service.shard_count,
                        )
                    if device_ids:
                        logger.debug(
                            f"[DispatchReconciler] shard={service.shard_id} pending_devices={len(device_ids)}"
                        )
                    for device_id in device_ids:
                        await service.enqueue_device(device_id)
                except Exception as exc:
                    logger.error(f"[DispatchReconciler] reconcile failed: {exc}", exc_info=True)


class ShardDispatcher:
    """Owns shard workers and reconcile task."""

    def __init__(self, state_manager, shards: int, fetch_limit: int, reconcile_seconds: int) -> None:
        self.state = state_manager
        self.shards = max(1, shards)
        self.fetch_limit = max(1, fetch_limit)
        self.reconcile_seconds = max(5, reconcile_seconds)
        self.services = [
            DeviceDispatchService(
                state_manager=state_manager,
                shard_id=shard_id,
                shard_count=self.shards,
                fetch_limit=self.fetch_limit,
            )
            for shard_id in range(self.shards)
        ]
        self.reconciler = DispatchReconciler(self.services, interval_seconds=self.reconcile_seconds)

    async def start(self) -> None:
        for service in self.services:
            await service.start()
        await self.reconciler.start()

    async def stop(self) -> None:
        await self.reconciler.stop()
        for service in self.services:
            await service.stop()

    async def enqueue_device(self, device_id: str) -> None:
        shard_id = abs(hash(device_id)) % self.shards
        await self.services[shard_id].enqueue_device(device_id)

    async def on_agent_online(self, device_id: str) -> None:
        await self.enqueue_device(device_id)

    async def recover_pending(self) -> None:
        async with get_session() as session:
            repo = DeviceOutboxRepo(session)
            for shard_id in range(self.shards):
                device_ids = await repo.list_devices_with_pending(
                    limit=1000,
                    shard_id=shard_id,
                    shard_count=self.shards,
                )
                for device_id in device_ids:
                    await self.services[shard_id].enqueue_device(device_id)


class PollingDeviceOutboxSender:
    """Legacy poll-all sender loop (kept for rollback mode)."""

    def __init__(self, state_manager, poll_interval: float = 1.0):
        self.state = state_manager
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sender_loop())
        logger.success("[PollingDeviceOutboxSender] Started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()

    async def _sender_loop(self):
        try:
            while self._running:
                await self._process_pending_commands()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            pass

    async def _process_pending_commands(self):
        async with get_session() as session:
            repo = DeviceOutboxRepo(session)
            raw_pending = await repo.get_all_pending_commands(limit=500)
            if not raw_pending:
                return
            by_device: dict[str, list] = {}
            for cmd in raw_pending:
                by_device.setdefault(cmd.device_id, []).append(cmd)
            for device_id, commands in by_device.items():
                agent_info = self.state.get_agent(device_id)
                if not agent_info:
                    continue
                ws = agent_info["ws"]
                metadata = agent_info.get("metadata", {})
                agent_device_id = metadata.get("device_id", device_id)
                for cmd in commands:
                    try:
                        await _send_single_command(self.state, ws, agent_device_id, cmd, repo)
                    except Exception as exc:
                        await repo.mark_as_failed(
                            outbox_id=cmd.id,
                            error_code="SEND_ERROR",
                            error_message=str(exc),
                            should_retry=True,
                        )
            await session.commit()


class DeviceOutboxSender:
    """
    Backward-compatible sender wrapper.

    Public API remains the same (`start()`/`stop()`), runtime mode is controlled by config.
    """

    def __init__(self, state_manager, poll_interval: float = 1.0):
        self.state = state_manager
        self.poll_interval = poll_interval
        self.mode = (DEVICE_DISPATCH_MODE or "poll").lower()
        self._polling_impl: Optional[PollingDeviceOutboxSender] = None
        self._sharded_impl: Optional[ShardDispatcher] = None

        if self.mode == "sharded":
            existing_dispatch = getattr(state_manager, "device_dispatch_service", None)
            if isinstance(existing_dispatch, ShardDispatcher):
                self._sharded_impl = existing_dispatch
            else:
                self._sharded_impl = ShardDispatcher(
                    state_manager=state_manager,
                    shards=DEVICE_DISPATCH_SHARDS,
                    fetch_limit=DEVICE_DISPATCH_FETCH_LIMIT,
                    reconcile_seconds=DEVICE_DISPATCH_RECONCILE_SECONDS,
                )
            setattr(state_manager, "device_dispatch_service", self._sharded_impl)
        else:
            self.mode = "poll"
            self._polling_impl = PollingDeviceOutboxSender(state_manager, poll_interval=poll_interval)

    def start(self):
        if self.mode == "sharded" and self._sharded_impl is not None:
            asyncio.create_task(self._sharded_impl.start())
            logger.success("[DeviceOutboxSender] Started in sharded mode")
            return
        if self._polling_impl is not None:
            self._polling_impl.start()
            logger.success("[DeviceOutboxSender] Started in poll mode")

    def stop(self):
        if self.mode == "sharded" and self._sharded_impl is not None:
            asyncio.create_task(self._sharded_impl.stop())
            logger.warning("[DeviceOutboxSender] Stopping sharded dispatcher")
            return
        if self._polling_impl is not None:
            self._polling_impl.stop()
            logger.warning("[DeviceOutboxSender] Stopping poll sender")


async def recover_pending_commands(state_manager):
    """Recover pending queue on startup."""
    mode = (DEVICE_DISPATCH_MODE or "poll").lower()
    if mode == "sharded":
        dispatch = getattr(state_manager, "device_dispatch_service", None)
        if dispatch is None:
            dispatch = ShardDispatcher(
                state_manager=state_manager,
                shards=DEVICE_DISPATCH_SHARDS,
                fetch_limit=DEVICE_DISPATCH_FETCH_LIMIT,
                reconcile_seconds=DEVICE_DISPATCH_RECONCILE_SECONDS,
            )
            setattr(state_manager, "device_dispatch_service", dispatch)
        await dispatch.recover_pending()
        logger.info("[DeviceOutboxSender] Recovered pending commands (sharded)")
        return

    async with get_session() as session:
        repo = DeviceOutboxRepo(session)
        pending_commands = await repo.get_all_pending_commands(limit=1000)
        logger.info(f"[DeviceOutboxSender] Found {len(pending_commands)} pending commands (poll mode)")


async def _send_single_command(state_manager, ws: web.WebSocketResponse, agent_device_id: str, cmd, repo) -> None:
    request_id = cmd.command_id
    ticket_id = None
    job_id = None
    if cmd.operation_id:
        from app.repos import OperationsRepo

        op_repo = OperationsRepo(repo.session)
        operation = await op_repo.get_by_operation_id(cmd.operation_id)
        if operation:
            ticket_id = operation.ticket_id
            job_id = operation.job_id

    if not ticket_id:
        ticket_id = cmd.params.get("ticket_id")
    if not job_id:
        job_id = cmd.params.get("job_id") or cmd.params.get("chat_job_id")

    command_envelope = {
        "type": "command",
        "request_id": request_id,
        "device_id": agent_device_id,
        "protocol_version": "ws_ticket_v3",
        "trace_id": cmd.trace_id or str(uuid.uuid4()),
        "payload": {
            "command": cmd.command,
            "command_id": cmd.command_id,
            "params": cmd.params,
            "actor_role": cmd.actor_role,
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "server",
        },
    }
    if ticket_id:
        command_envelope["ticket_id"] = ticket_id
    if job_id:
        command_envelope["job_id"] = job_id

    await ws.send_json(command_envelope)
    await repo.mark_as_sent(outbox_id=cmd.id)

    if cmd.operation_id:
        from app.services import OperationService

        ui_publisher = state_manager.ui_publisher if hasattr(state_manager, "ui_publisher") else None
        op_service = OperationService(repo.session, publisher=ui_publisher)
        await op_service.mark_sent(operation_id=cmd.operation_id, expected_statuses=["queued"])

    logger.info(
        f"[DeviceOutboxSender] TX command: device_id={cmd.device_id} command_id={cmd.command_id} "
        f"command={cmd.command} request_id={request_id} operation_id={cmd.operation_id}"
    )
