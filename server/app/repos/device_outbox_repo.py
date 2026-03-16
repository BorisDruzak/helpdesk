"""
Repository for device_outbox table operations.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import DeviceOutbox, Operation


class DeviceOutboxRepo:
    """
    Repository for managing device outbox in the database.
    
    Provides methods for:
    - Enqueuing commands for devices
    - Retrieving pending commands
    - Updating command lifecycle (sent, delivered, failed)
    - Retry logic
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a database session.
        
        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
    
    async def enqueue_command(
        self,
        device_id: str,
        command_id: str,
        command: str,
        params: dict,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        actor_role: str = "user",
        max_retries: int = 3,
        operation_id: Optional[str] = None
    ) -> int:
        """
        Enqueue a command for a device.
        
        Args:
            device_id: Device identifier
            command_id: Command identifier (UUID)
            command: Command name
            params: Command parameters as dict
            request_id: Optional request ID for tracking
            trace_id: Optional trace ID for correlation
            actor_role: Role of the actor initiating the command
            max_retries: Maximum number of retry attempts
            operation_id: Optional operation ID for tracking (КРИТИЧНО: operation_id = command_id)
        
        Returns:
            Outbox entry ID
        
        Raises:
            Exception: If database operation fails
        """
        outbox_entry = DeviceOutbox(
            device_id=device_id,
            command_id=command_id,
            command=command,
            params=params,
            status="pending",
            request_id=request_id,
            trace_id=trace_id,
            actor_role=actor_role,
            operation_id=operation_id,  # Добавлено для операций
            retry_count=0,
            max_retries=max_retries,
            created_at=datetime.now(timezone.utc)
        )
        
        self.session.add(outbox_entry)
        await self.session.flush()
        
        logger.info(
            f"[DeviceOutboxRepo] Enqueued command: "
            f"id={outbox_entry.id} device_id={device_id} "
            f"command_id={command_id} command={command}"
        )
        
        return outbox_entry.id
    
    async def get_pending_commands(
        self,
        device_id: str,
        limit: int = 10
    ) -> List[DeviceOutbox]:
        """
        Get pending commands for a device.
        
        Phase 5: Пропускает команды для операций со статусом waiting_consent или denied.
        
        Args:
            device_id: Device identifier
            limit: Maximum number of commands to return
        
        Returns:
            List of DeviceOutbox entries with status="pending" and operation status not in (waiting_consent, denied)
        """
        # Phase 5: JOIN с operations для фильтрации waiting_consent/denied
        stmt = (
            select(DeviceOutbox)
            .outerjoin(
                Operation,
                DeviceOutbox.operation_id == Operation.operation_id
            )
            .where(
                and_(
                    DeviceOutbox.device_id == device_id,
                    DeviceOutbox.status == "pending",
                    # Пропускаем команды для операций в waiting_consent или denied
                    # Если operation_id NULL или operation.status не в (waiting_consent, denied) - включаем
                    (
                        (Operation.operation_id.is_(None)) |
                        (~Operation.status.in_(["waiting_consent", "denied"]))
                    )
                )
            )
            .order_by(DeviceOutbox.created_at.asc())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        commands = result.scalars().all()
        
        logger.debug(
            f"[DeviceOutboxRepo] Retrieved {len(commands)} pending commands "
            f"for device_id={device_id}"
        )
        
        return list(commands)
    
    async def mark_as_sent(
        self,
        outbox_id: int
    ) -> bool:
        """
        Mark a command as sent.
        
        Args:
            outbox_id: Outbox entry ID
        
        Returns:
            True if updated, False if entry not found
        """
        stmt = (
            update(DeviceOutbox)
            .where(DeviceOutbox.id == outbox_id)
            .values(
                status="sent",
                sent_at=datetime.now(timezone.utc)
            )
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount == 0:
            logger.warning(
                f"[DeviceOutboxRepo] Command not found for mark_as_sent: "
                f"outbox_id={outbox_id}"
            )
            return False
        
        logger.debug(
            f"[DeviceOutboxRepo] Marked as sent: outbox_id={outbox_id}"
        )
        
        return True
    
    async def mark_as_delivered(
        self,
        command_id: str
    ) -> bool:
        """
        Mark a command as delivered.
        
        КРИТИЧНО: Поддерживает статусы "pending" и "sent" (для finally block гарантий).
        Это позволяет обновить outbox даже если команда еще не была отправлена (edge case).
        
        Args:
            command_id: Command identifier
        
        Returns:
            True if updated, False if entry not found or already in terminal state
        """
        stmt = (
            update(DeviceOutbox)
            .where(
                and_(
                    DeviceOutbox.command_id == command_id,
                    DeviceOutbox.status.in_(["pending", "sent"])  # Поддерживаем оба статуса
                )
            )
            .values(
                status="delivered",
                delivered_at=datetime.now(timezone.utc)
            )
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount == 0:
            logger.warning(
                f"[DeviceOutboxRepo] Command not found or not in 'pending'/'sent' status "
                f"for mark_as_delivered: command_id={command_id}"
            )
            return False
        
        logger.info(
            f"[DeviceOutboxRepo] Marked as delivered: command_id={command_id}"
        )
        
        return True
    
    async def mark_as_failed(
        self,
        outbox_id: int,
        error_code: str,
        error_message: str,
        should_retry: bool = False
    ) -> bool:
        """
        Mark a command as failed, optionally incrementing retry count.
        
        Args:
            outbox_id: Outbox entry ID
            error_code: Error code
            error_message: Error message
            should_retry: If True, increment retry_count and reset to pending if under max_retries
        
        Returns:
            True if updated, False if entry not found
        """
        # Get current entry
        stmt = select(DeviceOutbox).where(DeviceOutbox.id == outbox_id)
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if entry is None:
            logger.warning(
                f"[DeviceOutboxRepo] Command not found for mark_as_failed: "
                f"outbox_id={outbox_id}"
            )
            return False
        
        if should_retry and entry.retry_count < entry.max_retries:
            # Retry: increment retry_count and reset to pending
            entry.retry_count += 1
            entry.status = "pending"
            entry.error_code = error_code
            entry.error_message = error_message
            
            logger.warning(
                f"[DeviceOutboxRepo] Command marked for retry: "
                f"outbox_id={outbox_id} retry_count={entry.retry_count}/{entry.max_retries}"
            )
        else:
            # Failed permanently
            entry.status = "failed"
            entry.failed_at = datetime.now(timezone.utc)
            entry.error_code = error_code
            entry.error_message = error_message
            
            logger.error(
                f"[DeviceOutboxRepo] Command marked as failed: "
                f"outbox_id={outbox_id} error_code={error_code}"
            )
        
        return True
    
    async def get_command_by_id(
        self,
        command_id: str
    ) -> Optional[DeviceOutbox]:
        """
        Get a command by command_id.
        
        Args:
            command_id: Command identifier
        
        Returns:
            DeviceOutbox entry if found, None otherwise
        """
        stmt = (
            select(DeviceOutbox)
            .where(DeviceOutbox.command_id == command_id)
            .order_by(DeviceOutbox.created_at.desc())
            .limit(1)
        )
        
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        return entry
    
    async def get_all_pending_commands(
        self,
        limit: int = 100
    ) -> List[DeviceOutbox]:
        """
        Get all pending commands across all devices (for recovery).
        
        Phase 5: Пропускает команды для операций со статусом waiting_consent или denied.
        
        Args:
            limit: Maximum number of commands to return
        
        Returns:
            List of DeviceOutbox entries with status="pending" and operation status not in (waiting_consent, denied)
        """
        # Phase 5: JOIN с operations для фильтрации waiting_consent/denied
        stmt = (
            select(DeviceOutbox)
            .outerjoin(
                Operation,
                DeviceOutbox.operation_id == Operation.operation_id
            )
            .where(
                and_(
                    DeviceOutbox.status == "pending",
                    # Пропускаем команды для операций в waiting_consent или denied
                    # Если operation_id NULL или operation.status не в (waiting_consent, denied) - включаем
                    (
                        (Operation.operation_id.is_(None)) |
                        (~Operation.status.in_(["waiting_consent", "denied"]))
                    )
                )
            )
            .order_by(DeviceOutbox.created_at.asc())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        commands = result.scalars().all()
        
        logger.info(
            f"[DeviceOutboxRepo] Retrieved {len(commands)} pending commands "
            f"across all devices (excluding waiting_consent/denied)"
        )
        
        return list(commands)

    async def get_sent_without_operation(self, limit: int = 100) -> List[DeviceOutbox]:
        """
        Находит записи device_outbox со status='sent', у которых нет соответствующей операции
        (operation_id IS NULL или операции с таким operation_id нет в operations).
        Используется для cleanup/repair (Этап 1 стабилизации).
        """
        stmt = (
            select(DeviceOutbox)
            .outerjoin(Operation, DeviceOutbox.operation_id == Operation.operation_id)
            .where(
                and_(
                    DeviceOutbox.status == "sent",
                    Operation.operation_id.is_(None),
                )
            )
            .order_by(DeviceOutbox.sent_at.asc().nulls_last())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def repair_sent_without_operation(self, limit: int = 100) -> int:
        """
        Помечает записи device_outbox status='sent' без операции как failed (ORPHAN_SENT).
        Возвращает количество обновлённых записей.
        """
        orphans = await self.get_sent_without_operation(limit=limit)
        count = 0
        for entry in orphans:
            entry.status = "failed"
            entry.failed_at = datetime.now(timezone.utc)
            entry.error_code = "ORPHAN_SENT"
            entry.error_message = "Repair: sent without corresponding operation"
            count += 1
        if count:
            logger.info(
                f"[DeviceOutboxRepo] Repair: marked {count} sent-without-operation entries as failed (ORPHAN_SENT)"
            )
        return count
