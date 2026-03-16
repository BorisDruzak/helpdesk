"""
Device Outbox Sender - reliable command delivery loop.

This module implements a background task that:
1. Polls device_outbox for pending commands
2. Sends commands to connected agents via WebSocket
3. Tracks lifecycle (pending -> sent -> delivered/failed)
4. Implements retry logic with exponential backoff
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from aiohttp import web

from app.db import get_session
from app.repos import DeviceOutboxRepo


# Fair-selection: не более стольких команд на устройство за один проход
DEVICE_OUTBOX_PER_DEVICE_CAP = 20
# Глобальный лимит за один проход
DEVICE_OUTBOX_GLOBAL_CAP = 100
# Запрашиваем из БД больше, чтобы после per-device cap осталось до global_cap
DEVICE_OUTBOX_FETCH_LIMIT = 500


class DeviceOutboxSender:
    """
    Background sender loop for reliable command delivery.
    
    Implements Phase C: Device Outbox from V3 Protocol migration plan.
    Fair-selection: per-device cap и global cap, чтобы одно устройство не забирало весь лимит.
    """
    
    def __init__(self, state_manager, poll_interval: float = 1.0):
        """
        Initialize the outbox sender.
        
        Args:
            state_manager: StateManager instance for accessing connected agents
            poll_interval: Interval in seconds between polls (default: 1.0)
        """
        self.state = state_manager
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def start(self):
        """Start the sender loop."""
        if self._running:
            logger.warning("[DeviceOutboxSender] Already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._sender_loop())
        logger.success("[DeviceOutboxSender] Started")
    
    def stop(self):
        """Stop the sender loop."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
        
        logger.warning("[DeviceOutboxSender] Stopped")
    
    async def _sender_loop(self):
        """
        Main sender loop that processes pending commands.
        
        This loop:
        1. Polls device_outbox for pending commands
        2. Groups commands by device_id
        3. Sends commands to connected agents
        4. Updates command status (sent/failed)
        """
        logger.info("[DeviceOutboxSender] Sender loop started")
        
        try:
            while self._running:
                try:
                    await self._process_pending_commands()
                except Exception as e:
                    logger.error(f"[DeviceOutboxSender] Error processing commands: {e}", exc_info=True)
                
                # Sleep before next poll
                await asyncio.sleep(self.poll_interval)
        
        except asyncio.CancelledError:
            logger.info("[DeviceOutboxSender] Sender loop cancelled")
        except Exception as e:
            logger.error(f"[DeviceOutboxSender] Sender loop crashed: {e}", exc_info=True)
    
    async def _process_pending_commands(self):
        """
        Process all pending commands from device_outbox.
        
        Queries database for pending commands, groups by device_id,
        and sends to connected agents.
        """
        async with get_session() as session:
            repo = DeviceOutboxRepo(session)
            
            raw_pending = await repo.get_all_pending_commands(limit=DEVICE_OUTBOX_FETCH_LIMIT)
            if not raw_pending:
                return
            
            # Fair-selection: не более per_device_cap на устройство, затем не более global_cap всего
            commands_by_device = {}
            for cmd in raw_pending:
                if cmd.device_id not in commands_by_device:
                    commands_by_device[cmd.device_id] = []
                commands_by_device[cmd.device_id].append(cmd)
            capped = []
            for device_id, cmds in commands_by_device.items():
                capped.extend(cmds[:DEVICE_OUTBOX_PER_DEVICE_CAP])
            capped.sort(key=lambda c: c.created_at if c.created_at else "")
            pending_commands = capped[:DEVICE_OUTBOX_GLOBAL_CAP]
            
            logger.debug(
                f"[DeviceOutboxSender] Processing {len(pending_commands)} pending commands "
                f"(fair: per_device<={DEVICE_OUTBOX_PER_DEVICE_CAP}, global<={DEVICE_OUTBOX_GLOBAL_CAP})"
            )
            
            commands_by_device = {}
            for cmd in pending_commands:
                if cmd.device_id not in commands_by_device:
                    commands_by_device[cmd.device_id] = []
                commands_by_device[cmd.device_id].append(cmd)
            
            for device_id, commands in commands_by_device.items():
                await self._send_commands_to_device(device_id, commands, repo)
            
            # Commit all updates
            await session.commit()
    
    async def _send_commands_to_device(
        self,
        device_id: str,
        commands: list,
        repo: DeviceOutboxRepo
    ):
        """
        Send commands to a specific device.
        
        Args:
            device_id: Target device identifier
            commands: List of DeviceOutbox entries to send
            repo: DeviceOutboxRepo instance
        """
        # Check if agent is connected
        agent_info = self.state.get_agent(device_id)
        
        if not agent_info:
            logger.debug(
                f"[DeviceOutboxSender] Agent not connected: device_id={device_id}, "
                f"skipping {len(commands)} commands"
            )
            return
        
        ws = agent_info["ws"]
        metadata = agent_info.get("metadata", {})
        agent_device_id = metadata.get("device_id", device_id)
        
        # Send each command
        for cmd in commands:
            try:
                await self._send_single_command(ws, agent_device_id, cmd, repo)
            except Exception as e:
                logger.error(
                    f"[DeviceOutboxSender] Failed to send command: "
                    f"device_id={device_id} command_id={cmd.command_id} error={e}"
                )
                
                # Mark as failed with retry
                await repo.mark_as_failed(
                    outbox_id=cmd.id,
                    error_code="SEND_ERROR",
                    error_message=str(e),
                    should_retry=True
                )
    
    async def _send_single_command(
        self,
        ws: web.WebSocketResponse,
        agent_device_id: str,
        cmd,
        repo: DeviceOutboxRepo
    ):
        """
        Send a single command to the agent.
        
        Args:
            ws: WebSocket connection
            agent_device_id: Agent's device ID
            cmd: DeviceOutbox entry
            repo: DeviceOutboxRepo instance
        """
        # КРИТИЧНО: Используем command_id как request_id (так как command_id == request_id)
        request_id = cmd.command_id
        
        # КРИТИЧНО: Получаем ticket_id и job_id из operations через operation_id
        ticket_id = None
        job_id = None
        if cmd.operation_id:
            from app.repos import OperationsRepo
            op_repo = OperationsRepo(repo.session)
            operation = await op_repo.get_by_operation_id(cmd.operation_id)
            if operation:
                ticket_id = operation.ticket_id
                job_id = operation.job_id
        
        # Если ticket_id/job_id не найдены в operations, пытаемся извлечь из params
        if not ticket_id:
            ticket_id = cmd.params.get("ticket_id")
        if not job_id:
            job_id = cmd.params.get("job_id") or cmd.params.get("chat_job_id")
        
        # Build command envelope
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
                "actor_role": cmd.actor_role
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor_role": "server"
            }
        }
        
        # КРИТИЧНО: Добавляем ticket_id и job_id в envelope (Protocol V3)
        if ticket_id:
            command_envelope["ticket_id"] = ticket_id
        if job_id:
            command_envelope["job_id"] = job_id
        
        # Send via WebSocket
        await ws.send_json(command_envelope)
        
        # КРИТИЧНО: Атомарно обновляем outbox status И operation status
        # В рамках одной транзакции (session уже начата в _process_pending_commands)
        await repo.mark_as_sent(outbox_id=cmd.id)
        
        # Update operation status to 'sent' if operation exists
        if cmd.operation_id:
            from app.services import OperationService
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            ui_publisher = self.state.ui_publisher if hasattr(self.state, 'ui_publisher') else None
            op_service = OperationService(repo.session, publisher=ui_publisher)  # Use same session
            
            success = await op_service.mark_sent(
                operation_id=cmd.operation_id,
                expected_statuses=["queued"]
            )
            
            if not success:
                logger.warning(
                    f"[DeviceOutboxSender] Failed to mark operation as sent: "
                    f"operation_id={cmd.operation_id} (possibly already sent or status mismatch)"
                )
        
        logger.info(
            f"[DeviceOutboxSender] TX command: device_id={cmd.device_id} "
            f"command_id={cmd.command_id} command={cmd.command} request_id={request_id} "
            f"operation_id={cmd.operation_id}"
        )


async def recover_pending_commands(state_manager):
    """
    Recovery function to process pending commands on server startup.
    
    This ensures that commands enqueued before a server restart are not lost.
    Should be called once during server initialization.
    
    Args:
        state_manager: StateManager instance
    """
    logger.info("[DeviceOutboxSender] Starting command recovery...")
    
    try:
        async with get_session() as session:
            repo = DeviceOutboxRepo(session)
            
            # Get all pending commands
            pending_commands = await repo.get_all_pending_commands(limit=1000)
            
            if not pending_commands:
                logger.info("[DeviceOutboxSender] No pending commands to recover")
                return
            
            logger.info(
                f"[DeviceOutboxSender] Found {len(pending_commands)} pending commands, "
                f"will be processed by sender loop"
            )
            
            # Commands will be processed by the sender loop automatically
            # We just log for visibility
            
    except Exception as e:
        logger.error(f"[DeviceOutboxSender] Command recovery failed: {e}", exc_info=True)
