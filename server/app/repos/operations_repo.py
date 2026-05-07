"""
Repository for operations table.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import Operation, ConsentDecision


class OperationsRepo:
    """
    Repository for managing operations in the database.
    
    Provides methods for:
    - Creating operations
    - Retrieving operations by operation_id
    - Updating operation status with optimistic locking
    - Retrieving active operations
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a database session.
        
        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
    
    async def create_operation(
        self,
        operation_id: str,
        device_id: str,
        kind: str,
        actor_role: str,
        trace_id: str,
        ticket_id: Optional[str] = None,
        job_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        command_name: Optional[str] = None,
        timeout_override_sec: Optional[int] = None,
        playbook_run_id: Optional[int] = None,
        retry_of_operation_id: Optional[str] = None,
        status: str = "queued",
        deadline_at: Optional[datetime] = None,
        max_retries: int = 3
    ) -> Operation:
        """
        Create a new operation.
        
        Args:
            operation_id: Operation identifier (UUID, equals request_id and command_id)
            device_id: Device identifier
            kind: Operation kind ('tool_call', 'command', etc.)
            actor_role: Role of the actor initiating the operation
            trace_id: Trace ID for correlation
            ticket_id: Optional ticket identifier
            job_id: Optional job identifier
            tool_name: Optional tool name for tool_call operations
            status: Initial status (default: 'queued')
            deadline_at: Optional deadline timestamp
            max_retries: Maximum number of retry attempts
        
        Returns:
            Created Operation instance
        
        Raises:
            Exception: If database operation fails
        """
        operation = Operation(
            operation_id=operation_id,
            device_id=device_id,
            ticket_id=ticket_id,
            job_id=job_id,
            kind=kind,
            tool_name=tool_name,
            command_name=command_name,
            timeout_override_sec=timeout_override_sec,
            playbook_run_id=playbook_run_id,
            retry_of_operation_id=retry_of_operation_id,
            actor_role=actor_role,
            trace_id=trace_id,
            status=status,
            deadline_at=deadline_at,
            queued_at=datetime.now(timezone.utc),
            retry_count=0,
            max_retries=max_retries
        )
        
        self.session.add(operation)
        await self.session.flush()
        
        logger.info(
            f"[OperationsRepo] Created operation: "
            f"operation_id={operation_id} device_id={device_id} "
            f"kind={kind} status={status}"
        )
        
        return operation
    
    PENDING_STATUSES = ("queued", "sent", "accepted", "running")

    async def has_pending_list_tools(self, device_id: str) -> bool:
        """
        Проверяет, есть ли у устройства уже ожидающая/выполняющаяся операция list_tools.
        Используется для debounce/защиты от шторма повторных list_tools.
        """
        stmt = (
            select(Operation.operation_id)
            .where(
                and_(
                    Operation.device_id == device_id,
                    Operation.command_name == "list_tools",
                    Operation.status.in_(self.PENDING_STATUSES),
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_operation_id(
        self,
        operation_id: str
    ) -> Optional[Operation]:
        """
        Get operation by operation_id.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            Operation instance or None if not found
        """
        stmt = select(Operation).where(Operation.operation_id == operation_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_retry_count_if_available(self, operation_id: str) -> Optional[int]:
        """
        Atomically increments manual retry_count if the operation still has retry budget.

        Returns the new retry_count, or None when the retry limit has already been reached.
        """
        stmt = (
            update(Operation)
            .where(
                and_(
                    Operation.operation_id == operation_id,
                    Operation.retry_count < Operation.max_retries,
                )
            )
            .values(retry_count=Operation.retry_count + 1)
            .returning(Operation.retry_count)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        operation_id: str,
        new_status: str,
        expected_statuses: Optional[List[str]] = None,
        timestamp_field: Optional[str] = None,
        deadline_at: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        result_summary: Optional[str] = None,
        result_event_id: Optional[int] = None,
        retry_count: Optional[int] = None,
        # Cancel fields
        status_before_cancel: Optional[str] = None,
        cancel_target_operation_id: Optional[str] = None,
        active_cancel_operation_id: Optional[str] = None,
        cancel_reason: Optional[str] = None,
        cancel_requested_at: Optional[datetime] = None,
        canceled_at: Optional[datetime] = None
    ) -> bool:
        """
        Update operation status with optimistic locking.
        
        Args:
            operation_id: Operation identifier
            new_status: New status to set
            expected_statuses: Optional list of expected current statuses (for optimistic locking)
            timestamp_field: Optional timestamp field to update ('sent_at', 'accepted_at', 'started_at', 'finished_at')
            deadline_at: Optional new deadline timestamp
            error_code: Optional error code (for failed/timed_out statuses)
            error_message: Optional error message
            result_summary: Optional result summary (for succeeded status)
            result_event_id: Optional result event ID
            retry_count: Optional retry count update
        
        Returns:
            True if update was successful, False if status didn't match expected_statuses
        
        Raises:
            Exception: If database operation fails
        """
        # PR2: Guard для защиты terminal состояний от перезаписи
        # Если expected_statuses is None (forced update), проверяем terminal состояния
        if expected_statuses is None:
            current = await self.get_by_operation_id(operation_id)
            if not current:
                logger.warning(
                    f"[OperationsRepo] Operation not found: operation_id={operation_id}"
                )
                return False
            
            # Guard: защита terminal состояний от перезаписи
            terminal_statuses = ["succeeded", "failed", "timed_out", "canceled"]
            if current.status in terminal_statuses:
                # КРИТИЧНО: Нельзя перезаписывать terminal состояния без expected_statuses
                # Это защита от гонок и некорректных forced updates
                logger.warning(
                    f"[OperationsRepo] GUARD: Blocked attempt to overwrite terminal status: "
                    f"operation_id={operation_id} current_status={current.status} "
                    f"new_status={new_status}. Terminal states are immutable."
                )
                return False
        
        # Build update values
        values = {"status": new_status}
        
        # Update timestamp field if specified
        if timestamp_field:
            values[timestamp_field] = datetime.now(timezone.utc)
        
        # Update deadline if specified
        if deadline_at is not None:
            values["deadline_at"] = deadline_at
        
        # Update error fields if specified
        if error_code is not None:
            values["error_code"] = error_code
        if error_message is not None:
            values["error_message"] = error_message
        
        # Update result fields if specified
        if result_summary is not None:
            values["result_summary"] = result_summary
        if result_event_id is not None:
            values["result_event_id"] = result_event_id
        
        # Update retry count if specified
        if retry_count is not None:
            values["retry_count"] = retry_count
        
        # Update cancel fields if specified
        if status_before_cancel is not None:
            values["status_before_cancel"] = status_before_cancel
        if cancel_target_operation_id is not None:
            values["cancel_target_operation_id"] = cancel_target_operation_id
        if active_cancel_operation_id is not None:
            values["active_cancel_operation_id"] = active_cancel_operation_id
        if cancel_reason is not None:
            values["cancel_reason"] = cancel_reason
        if cancel_requested_at is not None:
            values["cancel_requested_at"] = cancel_requested_at
        if canceled_at is not None:
            values["canceled_at"] = canceled_at
        
        # Build WHERE clause
        where_clause = Operation.operation_id == operation_id
        
        # Add optimistic locking if expected_statuses specified
        if expected_statuses:
            where_clause = and_(
                where_clause,
                Operation.status.in_(expected_statuses)
            )
        
        # Execute update
        stmt = (
            update(Operation)
            .where(where_clause)
            .values(**values)
        )
        
        result = await self.session.execute(stmt)
        updated = result.rowcount > 0
        
        if updated:
            logger.info(
                f"[OperationsRepo] Updated operation: "
                f"operation_id={operation_id} new_status={new_status} "
                f"expected_statuses={expected_statuses}"
            )
        else:
            logger.warning(
                f"[OperationsRepo] Failed to update operation (status mismatch): "
                f"operation_id={operation_id} new_status={new_status} "
                f"expected_statuses={expected_statuses}"
            )
        
        return updated

    async def clear_cancel_tracking(self, operation_id: str) -> bool:
        """Clears transient cancel bookkeeping fields after terminal resolution."""
        stmt = (
            update(Operation)
            .where(Operation.operation_id == operation_id)
            .values(
                status_before_cancel=None,
                active_cancel_operation_id=None,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def get_operations(
        self,
        device_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Operation]:
        """
        Get operations with optional filters.
        
        Args:
            device_id: Optional device filter
            ticket_id: Optional ticket filter
            statuses: Optional list of statuses to filter by
            limit: Maximum number of operations to return
        
        Returns:
            List of Operation instances
        """
        stmt = select(Operation)
        
        if device_id:
            stmt = stmt.where(Operation.device_id == device_id)
        
        if ticket_id:
            stmt = stmt.where(Operation.ticket_id == ticket_id)
        
        if statuses:
            stmt = stmt.where(Operation.status.in_(statuses))
        
        stmt = stmt.order_by(Operation.queued_at.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_operations(
        self,
        device_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Operation]:
        """
        Get active (non-terminal) operations.
        
        Active statuses: queued, sent, accepted, running, waiting_consent, cancel_requested
        Terminal statuses: succeeded, failed, timed_out, canceled
        
        Args:
            device_id: Optional device filter
            ticket_id: Optional ticket filter
            limit: Maximum number of operations to return
        
        Returns:
            List of Operation instances
        """
        active_statuses = [
            "queued", "sent", "accepted", "running", 
            "waiting_consent", "cancel_requested"
        ]
        
        return await self.get_operations(
            device_id=device_id,
            ticket_id=ticket_id,
            statuses=active_statuses,
            limit=limit
        )
    
    async def get_operations_exceeding_deadline(
        self,
        limit: int = 100
    ) -> List[Operation]:
        """
        Get operations that have exceeded their deadline.
        
        Args:
            limit: Maximum number of operations to return
        
        Returns:
            List of Operation instances with deadline_at in the past
        """
        now = datetime.now(timezone.utc)
        
        # Only check non-terminal operations
        active_statuses = [
            "queued", "sent", "accepted", "running", 
            "waiting_consent", "cancel_requested"
        ]
        
        stmt = (
            select(Operation)
            .where(
                and_(
                    Operation.status.in_(active_statuses),
                    Operation.deadline_at.isnot(None),
                    Operation.deadline_at < now
                )
            )
            .order_by(Operation.deadline_at.asc())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_recent_operations(
        self,
        device_id: str,
        kinds: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Operation]:
        """
        Получает последние операции для устройства.
        
        Args:
            device_id: ID устройства
            kinds: Список kinds для фильтрации (опционально)
            limit: Максимальное количество операций
        
        Returns:
            Список операций, отсортированных по времени создания (новые первыми)
        """
        stmt = (
            select(Operation)
            .where(Operation.device_id == device_id)
            .order_by(Operation.queued_at.desc())
            .limit(limit)
        )
        
        if kinds:
            stmt = stmt.where(Operation.kind.in_(kinds))
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def create_consent_decision(
        self,
        operation_id: str,
        decision: str,  # 'approved' or 'denied'
        decided_by: str,  # actor_role or user_login
        reason: Optional[str] = None
    ) -> ConsentDecision:
        """
        Create a consent decision record.
        
        Args:
            operation_id: Operation identifier
            decision: Decision ('approved' or 'denied')
            decided_by: Who made the decision (actor_role or user_login)
            reason: Optional reason for decision
        
        Returns:
            Created ConsentDecision instance
        """
        consent_decision = ConsentDecision(
            operation_id=operation_id,
            decision=decision,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc),
            reason=reason
        )
        self.session.add(consent_decision)
        await self.session.flush()  # Flush to get ID if needed
        return consent_decision
    
    async def get_consent_decision(
        self,
        operation_id: str
    ) -> Optional[ConsentDecision]:
        """
        Get consent decision for operation.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            ConsentDecision if found, None otherwise
        """
        stmt = select(ConsentDecision).where(
            ConsentDecision.operation_id == operation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
