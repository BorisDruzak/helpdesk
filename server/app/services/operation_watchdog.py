"""
Operation Watchdog - периодическая проверка таймаутов операций.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.operation_service import OperationService
from app.repos.operations_repo import OperationsRepo
import config


class OperationWatchdog:
    """
    Watchdog для мониторинга таймаутов операций.
    
    Периодически проверяет операции с истекшим deadline и устанавливает
    статус timed_out через OperationService.
    Этап 5: после mark_timed_out вызывается advance_after_terminal для playbook-run.
    """
    
    def __init__(self, interval: Optional[int] = None):
        """
        Initialize watchdog.
        
        Args:
            interval: Check interval in seconds (default: from config)
        """
        self.interval = interval or config.OPERATION_WATCHDOG_INTERVAL
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.app = None  # Устанавливается через set_app(app) для advance_after_terminal
    
    def set_app(self, app) -> None:
        """Привязать приложение (для доступа к state и вызова advance_after_terminal)."""
        self.app = app
    
    async def _check_timeouts(self) -> None:
        """
        Проверить операции с истекшим deadline и установить timed_out.
        """
        try:
            async with get_session() as session:
                # КРИТИЧНО: Используем UiPublisher из state для push обновлений
                # OperationWatchdog использует глобальный state через get_watchdog()
                # Для watchdog можно использовать None (no push) или получить state из app context
                # Пока используем None, т.к. watchdog не имеет прямого доступа к app
                op_service = OperationService(session, publisher=None)
                
                # Получить операции с истекшим deadline
                expired_ops = await op_service.get_operations_exceeding_deadline(
                    limit=100
                )
                
                if not expired_ops:
                    return
                
                logger.info(
                    f"[OperationWatchdog] Found {len(expired_ops)} operations "
                    f"with expired deadline"
                )
                
                # Обработать каждую операцию
                for operation in expired_ops:
                    try:
                        # Формировать детальное сообщение об ошибке
                        now = datetime.now(timezone.utc)
                        deadline = operation.deadline_at
                        overdue = (now - deadline).total_seconds() if deadline else 0
                        
                        error_message = (
                            f"Operation timed out in status '{operation.status}'. "
                            f"Deadline: {deadline.isoformat() if deadline else 'N/A'}, "
                            f"Overdue: {int(overdue)}s"
                        )
                        
                        # Попытаться установить timed_out
                        success = await op_service.mark_timed_out(
                            operation_id=operation.operation_id,
                            error_message=error_message
                        )
                        
                        if success:
                            # КРИТИЧНО: Flush для применения изменений в сессии перед проверкой
                            await session.flush()
                            
                            # Перезагрузить операцию из БД для проверки реального статуса
                            updated_op = await op_service.repo.get_by_operation_id(operation.operation_id)
                            
                            if updated_op and updated_op.status == "timed_out":
                                logger.warning(
                                    f"[OperationWatchdog] Operation timed out: "
                                    f"operation_id={operation.operation_id} "
                                    f"old_status={operation.status} "
                                    f"new_status={updated_op.status} "
                                    f"overdue={int(overdue)}s"
                                )
                                
                                # PR3: Обновить device_outbox при timeout
                                # Операция timeout → outbox должен быть failed с error_code=TIMEOUT
                                try:
                                    from app.repos import DeviceOutboxRepo
                                    outbox_repo = DeviceOutboxRepo(session)
                                    
                                    # Ищем запись в outbox по operation_id (command_id == operation_id)
                                    outbox_entry = await outbox_repo.get_command_by_id(operation.operation_id)
                                    
                                    if outbox_entry and outbox_entry.status not in ['delivered', 'failed']:
                                        # Помечаем outbox как failed с error_code=TIMEOUT
                                        await outbox_repo.mark_as_failed(
                                            outbox_id=outbox_entry.id,
                                            error_code="TIMEOUT",
                                            error_message=f"Operation timed out in status {operation.status}",
                                            should_retry=False  # Timeout не ретраится
                                        )
                                        logger.warning(
                                            f"[OperationWatchdog] Outbox marked as failed (timeout): "
                                            f"command_id={operation.operation_id} error_code=TIMEOUT"
                                        )
                                except Exception as outbox_error:
                                    logger.error(
                                        f"[OperationWatchdog] Failed to update outbox for timed out operation: {outbox_error}",
                                        exc_info=True
                                    )
                                    # КРИТИЧНО: Не откатываем транзакцию из-за ошибки outbox
                                    # Операция уже помечена как timed_out, это важнее
                                # Этап 5: Playbook Engine — продвижение при timed_out (run не зависает)
                                if self.app and "state" in self.app:
                                    try:
                                        from app.services.playbook_engine import advance_after_terminal
                                        state = self.app["state"]
                                        payload = {"error": {"code": "TIMEOUT", "message": error_message}}
                                        await advance_after_terminal(
                                            session, state, operation.operation_id, "timed_out", payload
                                        )
                                    except Exception as pe:
                                        logger.debug(
                                            f"[OperationWatchdog] advance_after_terminal for timed_out: {pe}"
                                        )
                            else:
                                # КРИТИЧНО: mark_timed_out вернул success=True, но статус не изменился
                                # Это может быть из-за race condition или проблемы с транзакцией
                                actual_status = updated_op.status if updated_op else "NOT_FOUND"
                                logger.error(
                                    f"[OperationWatchdog] CRITICAL: mark_timed_out returned success=True, "
                                    f"but operation status is not timed_out! "
                                    f"operation_id={operation.operation_id} "
                                    f"old_status={operation.status} "
                                    f"actual_status={actual_status}"
                                )
                        else:
                            # Не удалось обновить - возможно, статус уже изменился (race condition)
                            # Благодаря guards в operations_repo, terminal состояния защищены
                            logger.warning(
                                f"[OperationWatchdog] Could not mark as timed_out "
                                f"(status changed?): operation_id={operation.operation_id} "
                                f"current_status={operation.status}"
                            )
                    
                    except Exception as e:
                        logger.error(
                            f"[OperationWatchdog] Error processing timeout for "
                            f"operation {operation.operation_id}: {e}",
                            exc_info=True
                        )
                        # КРИТИЧНО: Продолжаем обработку других операций даже при ошибке
                        # Не откатываем всю транзакцию из-за одной ошибки
                
                # КРИТИЧНО: Commit транзакции в конце, даже если были ошибки в отдельных операциях
                # Это гарантирует, что успешные обновления не потеряются
                try:
                    await session.commit()
                    logger.debug(
                        f"[OperationWatchdog] Committed timeout updates for {len(expired_ops)} operations"
                    )
                except Exception as commit_error:
                    logger.error(
                        f"[OperationWatchdog] CRITICAL: Failed to commit timeout updates: {commit_error}",
                        exc_info=True
                    )
                    await session.rollback()
        
        except Exception as e:
            logger.error(
                f"[OperationWatchdog] Error in timeout check: {e}",
                exc_info=True
            )
    
    async def _run_loop(self) -> None:
        """
        Основной цикл watchdog.
        """
        logger.info(
            f"[OperationWatchdog] Started with interval={self.interval}s"
        )
        
        while self._running:
            try:
                await self._check_timeouts()
            except Exception as e:
                logger.error(
                    f"[OperationWatchdog] Error in watchdog loop: {e}",
                    exc_info=True
                )
            
            # Ждать следующей итерации
            await asyncio.sleep(self.interval)
        
        logger.info("[OperationWatchdog] Stopped")
    
    async def start(self) -> None:
        """
        Запустить watchdog.
        """
        if self._running:
            logger.warning("[OperationWatchdog] Already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[OperationWatchdog] Starting...")
    
    async def stop(self) -> None:
        """
        Остановить watchdog.
        """
        if not self._running:
            return
        
        logger.info("[OperationWatchdog] Stopping...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
            self._task = None
    
    async def force_check(self) -> None:
        """
        Принудительно запустить проверку таймаутов (для тестирования).
        """
        logger.info("[OperationWatchdog] Force checking timeouts...")
        await self._check_timeouts()


# Singleton instance
_watchdog_instance: Optional[OperationWatchdog] = None


def get_watchdog() -> OperationWatchdog:
    """
    Получить singleton экземпляр watchdog.
    
    Returns:
        OperationWatchdog instance
    """
    global _watchdog_instance
    if _watchdog_instance is None:
        _watchdog_instance = OperationWatchdog()
    return _watchdog_instance
