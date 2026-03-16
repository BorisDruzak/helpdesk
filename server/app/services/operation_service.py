"""
Service for managing operation lifecycle.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repos.operations_repo import OperationsRepo
from app.db.models import Operation
from websocket.ui_publisher import UiPublisher, NoOpUiPublisher
import config


class OperationService:
    """
    Service for managing operation lifecycle with SLA tracking and optimistic locking.
    
    All status transitions use expected_statuses for race condition protection.
    Deadline calculation is based on operation kind and current status.
    """
    
    def __init__(self, session: AsyncSession, publisher: Optional[UiPublisher] = None):
        """
        Initialize service with a database session and optional UI publisher.
        
        Args:
            session: Async SQLAlchemy session
            publisher: Optional UI publisher (default: None = no push)
        """
        self.session = session
        self.repo = OperationsRepo(session)
        self.publisher = publisher  # Can be None for tests
    
    async def _push_operation_update(self, operation_id: str):
        """
        Helper method to push operation_updated event to UI subscribers.
        
        Reloads operation from DB to get latest state before pushing.
        """
        if not self.publisher:
            return
        
        try:
            operation = await self.repo.get_by_operation_id(operation_id)
            if operation:
                await self.publisher.push_operation_updated(operation)
        except Exception as e:
            logger.error(f"[OperationService] Failed to push operation update: {e}", exc_info=True)
    
    def _get_sla_timeout(
        self,
        kind: str,
        timeout_type: str
    ) -> int:
        """
        Get SLA timeout for operation kind.
        
        Args:
            kind: Operation kind ('tool_call', 'command', 'screenshot', etc.)
            timeout_type: Type of timeout ('delivery_timeout', 'execution_timeout', 'consent_timeout')
        
        Returns:
            Timeout in seconds
        """
        # Check for kind-specific override
        if kind in config.OPERATION_SLA_OVERRIDES:
            overrides = config.OPERATION_SLA_OVERRIDES[kind]
            if timeout_type in overrides:
                return overrides[timeout_type]
        
        # Return default timeout
        if timeout_type == "delivery_timeout":
            return config.OPERATION_DELIVERY_TIMEOUT
        elif timeout_type == "execution_timeout":
            return config.OPERATION_EXECUTION_TIMEOUT
        elif timeout_type == "consent_timeout":
            return config.OPERATION_CONSENT_TIMEOUT
        elif timeout_type == "accepted_timeout":
            return config.OPERATION_ACCEPTED_TIMEOUT
        else:
            return 180  # Default 3 minutes
    
    def calculate_deadline(
        self,
        operation: Operation
    ) -> Optional[datetime]:
        """
        Calculate deadline based on operation status and kind.
        
        Args:
            operation: Operation instance
        
        Returns:
            Deadline datetime or None if no deadline applies
        """
        now = datetime.now(timezone.utc)
        kind = operation.kind
        status = operation.status
        
        # Queued/sent: delivery timeout from queued_at
        if status in ["queued", "sent"]:
            timeout = self._get_sla_timeout(kind, "delivery_timeout")
            return operation.queued_at + timedelta(seconds=timeout)
        
        # Accepted: check if we should wait for running or apply execution timeout
        # Use accepted_timeout to detect stuck operations
        elif status == "accepted":
            timeout = self._get_sla_timeout(kind, "accepted_timeout")
            return operation.accepted_at + timedelta(seconds=timeout)
        
        # Running: execution timeout from started_at (Этап 5: step timeout_override_sec)
        elif status == "running":
            timeout = (
                operation.timeout_override_sec
                if operation.timeout_override_sec is not None
                else self._get_sla_timeout(kind, "execution_timeout")
            )
            start_time = operation.started_at or operation.accepted_at or operation.queued_at
            return start_time + timedelta(seconds=timeout)
        
        # Waiting consent: consent timeout from when consent was requested
        elif status == "waiting_consent":
            # Use started_at as the time consent was requested
            # (mark_waiting_consent should set started_at)
            timeout = self._get_sla_timeout(kind, "consent_timeout")
            start_time = operation.started_at or operation.accepted_at or operation.queued_at
            return start_time + timedelta(seconds=timeout)
        
        # Cancel requested: short timeout for cancel acknowledgment (1 minute)
        elif status == "cancel_requested":
            # Use finished_at as the time cancel was requested
            request_time = operation.finished_at or now
            return request_time + timedelta(seconds=60)
        
        # Terminal statuses: no deadline
        else:
            return None
    
    def update_deadline(
        self,
        operation: Operation
    ) -> Optional[datetime]:
        """
        Update operation deadline based on current status.
        
        Args:
            operation: Operation instance
        
        Returns:
            New deadline or None
        """
        new_deadline = self.calculate_deadline(operation)
        operation.deadline_at = new_deadline
        return new_deadline
    
    async def enqueue_operation(
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
        max_retries: int = 3,
        initial_status: str = "queued"
    ) -> Operation:
        """
        Enqueue a new operation with specified initial status.
        
        This should be called in the same transaction as device_outbox.enqueue.
        
        Args:
            operation_id: Operation identifier (equals request_id and command_id)
            device_id: Device identifier
            kind: Operation kind
            actor_role: Actor role
            trace_id: Trace ID
            ticket_id: Optional ticket ID
            job_id: Optional job ID
            tool_name: Optional tool name
            max_retries: Max retries
            initial_status: Initial status (default: "queued", can be "waiting_consent")
        
        Returns:
            Created Operation instance
        """
        operation = await self.repo.create_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind=kind,
            actor_role=actor_role,
            trace_id=trace_id,
            ticket_id=ticket_id,
            job_id=job_id,
            tool_name=tool_name,
            command_name=command_name,
            timeout_override_sec=timeout_override_sec,
            playbook_run_id=playbook_run_id,
            status=initial_status,
            max_retries=max_retries
        )
        
        # Calculate and set initial deadline
        deadline = self.calculate_deadline(operation)
        if deadline:
            await self.repo.update_status(
                operation_id=operation_id,
                new_status="queued",
                deadline_at=deadline
            )
            operation.deadline_at = deadline
        
        logger.info(
            f"[OperationService] Enqueued operation: "
            f"operation_id={operation_id} kind={kind} deadline={deadline}"
        )
        
        # Push update to UI (operation created)
        await self._push_operation_update(operation_id)
        
        return operation
    
    async def mark_sent(
        self,
        operation_id: str,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as sent (command sent over WebSocket).
        
        Args:
            operation_id: Operation identifier
            expected_statuses: Expected current statuses (default: ['queued'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["queued"]
        
        # Get operation to calculate new deadline
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for mark_sent: {operation_id}"
            )
            return False
        
        operation.status = "sent"
        operation.sent_at = datetime.now(timezone.utc)
        new_deadline = self.calculate_deadline(operation)
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="sent",
            expected_statuses=expected_statuses,
            timestamp_field="sent_at",
            deadline_at=new_deadline
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as sent: "
                f"operation_id={operation_id} deadline={new_deadline}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_accepted(
        self,
        operation_id: str,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as accepted (agent sent command_ack with accepted=true).
        
        Args:
            operation_id: Operation identifier
            expected_statuses: Expected current statuses (default: ['sent', 'queued'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["sent", "queued"]
        
        # Get operation to calculate new deadline
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for mark_accepted: {operation_id}"
            )
            return False
        
        operation.status = "accepted"
        operation.accepted_at = datetime.now(timezone.utc)
        new_deadline = self.calculate_deadline(operation)
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="accepted",
            expected_statuses=expected_statuses,
            timestamp_field="accepted_at",
            deadline_at=new_deadline
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as accepted: "
                f"operation_id={operation_id} deadline={new_deadline}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_running(
        self,
        operation_id: str,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as running (tool_call_started/agent_action received).
        
        Args:
            operation_id: Operation identifier
            expected_statuses: Expected current statuses (default: ['accepted', 'sent'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["accepted", "sent"]
        
        # Get operation to calculate new deadline
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for mark_running: {operation_id}"
            )
            return False
        
        operation.status = "running"
        operation.started_at = datetime.now(timezone.utc)
        new_deadline = self.calculate_deadline(operation)
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="running",
            expected_statuses=expected_statuses,
            timestamp_field="started_at",
            deadline_at=new_deadline
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as running: "
                f"operation_id={operation_id} deadline={new_deadline}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_waiting_consent(
        self,
        operation_id: str,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as waiting_consent (consent_required received).
        
        Args:
            operation_id: Operation identifier
            expected_statuses: Expected current statuses (default: ['accepted', 'running'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["accepted", "running"]
        
        # Get operation to calculate new deadline
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for mark_waiting_consent: {operation_id}"
            )
            return False
        
        operation.status = "waiting_consent"
        # Set started_at if not already set (for deadline calculation)
        if not operation.started_at:
            operation.started_at = datetime.now(timezone.utc)
        new_deadline = self.calculate_deadline(operation)
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="waiting_consent",
            expected_statuses=expected_statuses,
            timestamp_field="started_at" if not operation.started_at else None,
            deadline_at=new_deadline
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as waiting_consent: "
                f"operation_id={operation_id} deadline={new_deadline}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_succeeded(
        self,
        operation_id: str,
        result_summary: Optional[str] = None,
        result_event_id: Optional[int] = None,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as succeeded.
        
        Args:
            operation_id: Operation identifier
            result_summary: Optional result summary
            result_event_id: Optional result event ID
            expected_statuses: Expected current statuses (default: ['running', 'accepted', 'waiting_consent'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["running", "accepted", "waiting_consent"]
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="succeeded",
            expected_statuses=expected_statuses,
            timestamp_field="finished_at",
            result_summary=result_summary,
            result_event_id=result_event_id,
            deadline_at=None  # Clear deadline for terminal status
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as succeeded: "
                f"operation_id={operation_id}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_failed(
        self,
        operation_id: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        result_event_id: Optional[int] = None,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as failed.
        
        Args:
            operation_id: Operation identifier
            error_code: Optional error code
            error_message: Optional error message
            result_event_id: Optional result event ID
            expected_statuses: Expected current statuses (default: ['running', 'accepted', 'sent', 'queued'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["running", "accepted", "sent", "queued"]
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="failed",
            expected_statuses=expected_statuses,
            timestamp_field="finished_at",
            error_code=error_code,
            error_message=error_message,
            result_event_id=result_event_id,
            deadline_at=None  # Clear deadline for terminal status
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as failed: "
                f"operation_id={operation_id} error_code={error_code}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_timed_out(
        self,
        operation_id: str,
        error_message: Optional[str] = None,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as timed_out.
        
        Args:
            operation_id: Operation identifier
            error_message: Optional timeout message
            expected_statuses: Expected current statuses (default: any non-terminal)
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = [
                "queued", "sent", "accepted", "running", 
                "waiting_consent", "cancel_requested"
            ]
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="timed_out",
            expected_statuses=expected_statuses,
            timestamp_field="finished_at",
            error_code="timeout",
            error_message=error_message or "Operation timed out",
            deadline_at=None  # Clear deadline for terminal status
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as timed_out: "
                f"operation_id={operation_id}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_cancel_requested(
        self,
        operation_id: str,
        status_before_cancel: Optional[str] = None,
        cancel_reason: Optional[str] = None,
        cancel_requested_at: Optional[datetime] = None,
        active_cancel_operation_id: Optional[str] = None,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as cancel_requested (user requested cancel).
        
        This is an intermediate status. The operation will be marked as 'canceled'
        only after the agent confirms cancellation.
        
        КРИТИЧНО: Использует guarded update для предотвращения гонок.
        WHERE status != 'cancel_requested' AND status NOT IN (terminal_statuses)
        
        Args:
            operation_id: Operation identifier
            status_before_cancel: Исходный статус перед cancel_requested (для rollback)
            cancel_reason: Причина отмены
            cancel_requested_at: Время запроса отмены
            active_cancel_operation_id: ID созданной cancel-op операции (для идемпотентности)
            expected_statuses: Expected current statuses (default: any non-terminal, excluding cancel_requested)
        
        Returns:
            True if successful, False if status mismatch or already cancel_requested
        """
        if expected_statuses is None:
            expected_statuses = [
                "queued", "sent", "accepted", "running", "waiting_consent"
            ]
        
        # Get operation to calculate new deadline and save status_before_cancel
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for mark_cancel_requested: {operation_id}"
            )
            return False
        
        # Guard: не перезаписывать если уже cancel_requested
        if operation.status == "cancel_requested":
            logger.info(
                f"[OperationService] Operation already cancel_requested: {operation_id}"
            )
            return False
        
        # Guard: не terminal
        terminal_statuses = ["succeeded", "failed", "timed_out", "canceled"]
        if operation.status in terminal_statuses:
            logger.warning(
                f"[OperationService] Cannot cancel terminal operation: {operation_id} status={operation.status}"
            )
            return False
        
        # Сохранить исходный статус если не передан
        if status_before_cancel is None:
            status_before_cancel = operation.status
        
        # Время запроса отмены
        if cancel_requested_at is None:
            cancel_requested_at = datetime.now(timezone.utc)
        
        operation.status = "cancel_requested"
        new_deadline = self.calculate_deadline(operation)
        
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="cancel_requested",
            expected_statuses=expected_statuses,
            timestamp_field="finished_at",
            deadline_at=new_deadline,
            status_before_cancel=status_before_cancel,
            cancel_reason=cancel_reason,
            cancel_requested_at=cancel_requested_at,
            active_cancel_operation_id=active_cancel_operation_id
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as cancel_requested: "
                f"operation_id={operation_id} status_before_cancel={status_before_cancel} "
                f"deadline={new_deadline}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def mark_canceled(
        self,
        operation_id: str,
        result_event_id: Optional[int] = None,
        canceled_at: Optional[datetime] = None,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Mark operation as canceled (agent confirmed cancellation).
        
        КРИТИЧНО: Очищает status_before_cancel и active_cancel_operation_id после успешного cancel.
        
        Args:
            operation_id: Operation identifier
            result_event_id: Optional result event ID
            canceled_at: Время подтверждения отмены
            expected_statuses: Expected current statuses (default: ['cancel_requested'])
        
        Returns:
            True if successful, False if status mismatch
        """
        if expected_statuses is None:
            expected_statuses = ["cancel_requested"]
        
        if canceled_at is None:
            canceled_at = datetime.now(timezone.utc)
        
        # Очистить cancel-поля после успешного cancel
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="canceled",
            expected_statuses=expected_statuses,
            result_event_id=result_event_id,
            canceled_at=canceled_at,
            deadline_at=None,  # Clear deadline for terminal status
            status_before_cancel=None,  # Очистить после успешного cancel
            active_cancel_operation_id=None  # Очистить для разрешения повторного cancel
        )
        
        if success:
            logger.info(
                f"[OperationService] Marked operation as canceled: "
                f"operation_id={operation_id}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success
    
    async def rollback_cancel_request(
        self,
        operation_id: str,
        expected_statuses: Optional[List[str]] = None
    ) -> bool:
        """
        Rollback cancel_requested to status_before_cancel.
        
        Используется при ошибке cancel-команды (agent вернул error).
        
        КРИТИЧНО: Очищает status_before_cancel и active_cancel_operation_id.
        
        Args:
            operation_id: Operation identifier
            expected_statuses: Expected current statuses (default: ['cancel_requested'])
        
        Returns:
            True if successful, False if operation not found or no status_before_cancel
        """
        if expected_statuses is None:
            expected_statuses = ["cancel_requested"]
        
        # Получить операцию для status_before_cancel
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation or not operation.status_before_cancel:
            logger.warning(
                f"[OperationService] Cannot rollback: operation not found or no status_before_cancel: {operation_id}"
            )
            return False
        
        # Guarded update: rollback только если еще в cancel_requested
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status=operation.status_before_cancel,
            expected_statuses=expected_statuses,
            # Очистить cancel-поля
            status_before_cancel=None,
            active_cancel_operation_id=None,
            cancel_reason=None  # Или оставить для audit
        )
        
        if success:
            logger.info(
                f"[OperationService] Rolled back cancel request: "
                f"operation_id={operation_id} restored_status={operation.status_before_cancel}"
            )
        
        return success
    
    async def get_active_operations(
        self,
        device_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Operation]:
        """
        Get active (non-terminal) operations.
        
        Args:
            device_id: Optional device filter
            ticket_id: Optional ticket filter
            limit: Maximum operations to return
        
        Returns:
            List of active operations
        """
        return await self.repo.get_active_operations(
            device_id=device_id,
            ticket_id=ticket_id,
            limit=limit
        )
    
    async def get_operations_exceeding_deadline(
        self,
        limit: int = 100
    ) -> List[Operation]:
        """
        Get operations that have exceeded their deadline.
        
        Args:
            limit: Maximum operations to return
        
        Returns:
            List of operations with deadline in the past
        """
        return await self.repo.get_operations_exceeding_deadline(limit=limit)
    
    async def approve_consent(
        self,
        operation_id: str,
        decided_by: str,  # actor_role or user_login
        reason: Optional[str] = None
    ) -> bool:
        """
        Approve consent for operation in waiting_consent status.
        
        Phase 5: Transitions operation from waiting_consent → queued and enqueues command.
        
        КРИТИЧНО: После approve операция enqueued в device_outbox и переходит в queued.
        
        Args:
            operation_id: Operation identifier
            decided_by: Who approved (actor_role or user_login)
            reason: Optional reason for approval
        
        Returns:
            True if successful, False if operation not in waiting_consent
        """
        # Get operation
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for approve_consent: {operation_id}"
            )
            return False
        
        # Guard: только операции в waiting_consent
        if operation.status != "waiting_consent":
            logger.warning(
                f"[OperationService] Cannot approve non-waiting_consent operation: "
                f"operation_id={operation_id} status={operation.status}"
            )
            return False
        
        # Create consent decision
        await self.repo.create_consent_decision(
            operation_id=operation_id,
            decision="approved",
            decided_by=decided_by,
            reason=reason
        )
        
        # Transition: waiting_consent → queued
        new_deadline = self.calculate_deadline(operation)  # Will recalculate for queued status
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="queued",
            expected_statuses=["waiting_consent"],
            deadline_at=new_deadline
        )
        
        if not success:
            logger.warning(
                f"[OperationService] Failed to transition to queued: operation_id={operation_id}"
            )
            return False
        
        # КРИТИЧНО: Enqueue command в device_outbox
        # Восстанавливаем команду из operation
        if operation.kind == "tool_call" and operation.tool_name:
            # Для tool_call: команда = "run_tool"
            from app.repos.device_outbox_repo import DeviceOutboxRepo
            from app.repos.ticket_events_repo import TicketEventsRepo
            
            # Пытаемся восстановить params из tool_call_started события
            tool_params = {}
            if operation.ticket_id:
                try:
                    events_repo = TicketEventsRepo(self.session)
                    # Ищем tool_call_started событие с этим operation_id
                    events = await events_repo.get_events(
                        ticket_id=operation.ticket_id,
                        limit=1000  # Достаточно для поиска
                    )
                    
                    # Ищем событие tool_call_started с operation_id
                    for event in events:
                        if (event.event_type == "tool_call_started" and 
                            event.operation_id == operation_id):
                            # Восстанавливаем params из payload
                            event_payload = event.payload
                            if isinstance(event_payload, dict):
                                tool_params = event_payload.get("params", {})
                                logger.debug(
                                    f"[OperationService] Restored params from tool_call_started: "
                                    f"operation_id={operation_id} params={tool_params}"
                                )
                            break
                except Exception as e:
                    logger.warning(
                        f"[OperationService] Failed to restore params from ticket_events: {e}"
                    )
                    # Fallback to empty params
            
            # Формируем params для run_tool команды
            params = {
                "tool_name": operation.tool_name,
                "ticket_id": operation.ticket_id,
                "params": tool_params  # Восстановленные или пустые params
            }
            
            if operation.job_id:
                params["job_id"] = operation.job_id
            
            outbox_repo = DeviceOutboxRepo(self.session)
            await outbox_repo.enqueue_command(
                device_id=operation.device_id,
                command_id=operation_id,  # command_id = operation_id
                command="run_tool",
                params=params,
                request_id=operation_id,
                trace_id=operation.trace_id,
                actor_role=operation.actor_role,
                operation_id=operation_id
            )
            
            logger.info(
                f"[OperationService] Enqueued command after approve: "
                f"operation_id={operation_id} command=run_tool tool_name={operation.tool_name}"
            )
        else:
            logger.warning(
                f"[OperationService] Cannot enqueue non-tool_call operation: "
                f"operation_id={operation_id} kind={operation.kind}"
            )
        
        logger.info(
            f"[OperationService] Approved consent: operation_id={operation_id} "
            f"decided_by={decided_by}"
        )
        
        # Push update to UI
        await self._push_operation_update(operation_id)
        
        return True
    
    async def deny_consent(
        self,
        operation_id: str,
        decided_by: str,  # actor_role or user_login
        reason: Optional[str] = None
    ) -> bool:
        """
        Deny consent for operation in waiting_consent status.
        
        Phase 5: Transitions operation from waiting_consent → denied (terminal status).
        
        КРИТИЧНО: Статус denied терминальный, отдельно от failed (для UX и аналитики).
        
        Args:
            operation_id: Operation identifier
            decided_by: Who denied (actor_role or user_login)
            reason: Optional reason for denial
        
        Returns:
            True if successful, False if operation not in waiting_consent
        """
        # Get operation
        operation = await self.repo.get_by_operation_id(operation_id)
        if not operation:
            logger.warning(
                f"[OperationService] Operation not found for deny_consent: {operation_id}"
            )
            return False
        
        # Guard: только операции в waiting_consent
        if operation.status != "waiting_consent":
            logger.warning(
                f"[OperationService] Cannot deny non-waiting_consent operation: "
                f"operation_id={operation_id} status={operation.status}"
            )
            return False
        
        # Create consent decision
        await self.repo.create_consent_decision(
            operation_id=operation_id,
            decision="denied",
            decided_by=decided_by,
            reason=reason
        )
        
        # Transition: waiting_consent → denied (terminal)
        success = await self.repo.update_status(
            operation_id=operation_id,
            new_status="denied",
            expected_statuses=["waiting_consent"],
            timestamp_field="finished_at",
            error_code="CONSENT_DENIED",
            error_message=reason or "Consent denied",
            deadline_at=None  # Clear deadline for terminal status
        )
        
        if success:
            logger.info(
                f"[OperationService] Denied consent: operation_id={operation_id} "
                f"decided_by={decided_by} reason={reason}"
            )
            # Push update to UI
            await self._push_operation_update(operation_id)
        
        return success