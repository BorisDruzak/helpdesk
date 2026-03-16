"""
Event Validator для Protocol V3.

Phase B: Валидация device binding и структуры событий.
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from loguru import logger

# Import database components (lazy import)
try:
    from app.repos import TicketEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


@dataclass
class ValidationResult:
    """Результат валидации события."""
    valid: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    
    @classmethod
    def success(cls):
        """Создает успешный результат валидации."""
        return cls(valid=True)
    
    @classmethod
    def failure(
        cls,
        error_code: str,
        error_message: str,
        retryable: bool = False
    ):
        """Создает результат с ошибкой валидации."""
        return cls(
            valid=False,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable
        )


class EventValidator:
    """
    Валидатор для Protocol V3 событий.
    
    Проверяет:
    - Наличие обязательных полей
    - Device binding для ticket events
    - Существование тикетов
    - Корректность структуры событий
    """
    
    def __init__(self):
        """Инициализация валидатора."""
        pass
    
    async def validate_ticket_event(
        self,
        session,
        ticket_id: str,
        device_id: str,
        agent_seq: Optional[int],
        event_type: str,
        payload: dict
    ) -> ValidationResult:
        """
        Валидирует событие тикета.
        
        Проверяет:
        1. Наличие agent_seq (обязательно для ticket events)
        2. Существование тикета
        3. Device binding (тикет принадлежит device_id)
        
        Args:
            session: Database session
            ticket_id: ID тикета
            device_id: ID устройства, отправившего событие
            agent_seq: Sequence number агента (обязательно)
            event_type: Тип события
            payload: Payload события
        
        Returns:
            ValidationResult с результатом валидации
        """
        # Валидация 1: agent_seq обязателен для ticket events
        if agent_seq is None:
            return ValidationResult.failure(
                error_code="VALIDATION_ERROR",
                error_message="Missing agent_seq for ticket event",
                retryable=False
            )
        
        # Если DB недоступна, пропускаем валидацию binding
        if not DB_AVAILABLE:
            logger.warning(
                f"[Validator] DB not available, skipping device binding validation "
                f"for ticket_id={ticket_id}"
            )
            return ValidationResult.success()
        
        try:
            # Валидация 2 и 3: проверка существования тикета и device binding
            # КРИТИЧНО: Проверяем, что TicketEventsRepo доступен
            if not DB_AVAILABLE:
                logger.warning(
                    f"[Validator] DB not available, skipping ticket validation "
                    f"for ticket_id={ticket_id}"
                )
                return ValidationResult.success()
            
            ticket_events_repo = TicketEventsRepo(session)
            ticket = await ticket_events_repo.get_ticket(ticket_id)
            
            if not ticket:
                # Тикет не существует
                return ValidationResult.failure(
                    error_code="UNKNOWN_TICKET",
                    error_message=f"Ticket {ticket_id} not found",
                    retryable=False
                )
            
            if ticket.device_id != device_id:
                # Device mismatch - тикет принадлежит другому устройству
                return ValidationResult.failure(
                    error_code="DEVICE_MISMATCH",
                    error_message=(
                        f"Ticket {ticket_id} bound to {ticket.device_id}, "
                        f"not {device_id}"
                    ),
                    retryable=False
                )
            
            # Валидация успешна
            return ValidationResult.success()
            
        except Exception as e:
            # Ошибка при валидации - retryable
            logger.error(
                f"[Validator] Error during ticket validation: {e}",
                exc_info=True
            )
            return ValidationResult.failure(
                error_code="SERVER_ERROR",
                error_message=f"Validation error: {str(e)}",
                retryable=True
            )
    
    async def validate_device_event(
        self,
        device_id: str,
        device_seq: Optional[int],
        event_type: str,
        payload: dict
    ) -> ValidationResult:
        """
        Валидирует событие устройства (без привязки к тикету).
        
        Проверяет:
        1. Наличие device_seq (опционально, но рекомендуется)
        
        Args:
            device_id: ID устройства
            device_seq: Sequence number устройства
            event_type: Тип события
            payload: Payload события
        
        Returns:
            ValidationResult с результатом валидации
        """
        # Для device events device_seq опционален, но предупреждаем если отсутствует
        if device_seq is None:
            logger.warning(
                f"[Validator] Device event without device_seq: "
                f"device_id={device_id} event_type={event_type}"
            )
        
        # Device events всегда валидны (нет strict binding)
        return ValidationResult.success()
    
    def validate_structure(
        self,
        outbox_item: dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидирует структуру outbox_item.
        
        Проверяет наличие обязательных полей на верхнем уровне.
        
        Args:
            outbox_item: Полный envelope outbox_item
        
        Returns:
            (valid, error_message): Tuple с результатом валидации
        """
        # Проверка type
        if outbox_item.get("type") != "outbox_item":
            return False, f"Invalid type: {outbox_item.get('type')}"
        
        # Проверка payload
        payload = outbox_item.get("payload")
        if not payload:
            return False, "Missing payload"
        
        # Проверка outbox_id
        if not payload.get("outbox_id"):
            return False, "Missing outbox_id in payload"
        
        # Проверка item_type
        if not payload.get("item_type"):
            return False, "Missing item_type in payload"
        
        # Проверка trace_id (обязателен для корреляции)
        if not outbox_item.get("trace_id"):
            return False, "Missing trace_id"
        
        return True, None
