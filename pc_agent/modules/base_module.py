"""
Базовый абстрактный класс для всех модулей сбора данных.

Этот модуль определяет контракт (интерфейс), который должны реализовать
все модули-коллекторы в системе. Использует паттерн Abstract Base Class (ABC)
для обеспечения строгой типизации и контроля реализации.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, Any, Iterator, Optional

from pc_agent.core.action_trace import get_action_trace_recorder
from shared.redaction import redact_sensitive_payload


@dataclass(slots=True)
class ModuleTraceBinding:
    module_name: str
    tool_name: Optional[str]
    ticket_id: Optional[str]
    operation_id: Optional[str]
    trace_id: Optional[str]
    request_id: Optional[str]
    session_key: Optional[str]
    parent_action_id: Optional[str]


_MODULE_TRACE_BINDING: ContextVar[Optional[ModuleTraceBinding]] = ContextVar(
    "module_trace_binding",
    default=None,
)


class BaseCollector(ABC):
    """
    Абстрактный базовый класс для всех модулей-коллекторов данных.
    
    Все пользовательские модули должны наследоваться от этого класса
    и реализовывать обязательные абстрактные методы и свойства.
    
    Паттерн ABC гарантирует, что:
    1. Нельзя создать экземпляр BaseCollector напрямую
    2. Дочерние классы ОБЯЗАНЫ реализовать все @abstractmethod
    3. Обеспечивается единообразный интерфейс для всех модулей
    """
    
    @contextmanager
    def bind_trace(
        self,
        *,
        tool_name: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
        session_key: Optional[str] = None,
        parent_action_id: Optional[str] = None,
    ) -> Iterator[ModuleTraceBinding]:
        binding = ModuleTraceBinding(
            module_name=self.name,
            tool_name=tool_name,
            ticket_id=ticket_id,
            operation_id=operation_id,
            trace_id=trace_id,
            request_id=request_id,
            session_key=session_key,
            parent_action_id=parent_action_id,
        )
        token = _MODULE_TRACE_BINDING.set(binding)
        try:
            yield binding
        finally:
            _MODULE_TRACE_BINDING.reset(token)

    def _current_trace_binding(self) -> Optional[ModuleTraceBinding]:
        return _MODULE_TRACE_BINDING.get()

    def trace_event(
        self,
        step: str,
        *,
        status: str = "ok",
        stage: str = "event",
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[dict]:
        binding = self._current_trace_binding()
        if binding is None:
            return None
        context = get_action_trace_recorder().context(
            source="module",
            action="module.step",
            category="tool",
            parent_action_id=binding.parent_action_id,
            ticket_id=binding.ticket_id,
            operation_id=binding.operation_id,
            tool_name=binding.tool_name,
            trace_id=binding.trace_id,
            request_id=binding.request_id,
            session_key=binding.session_key,
        )
        payload_details = redact_sensitive_payload(
            {
                "step": str(step or "").strip() or "step",
                "module_name": binding.module_name,
                **(details or {}),
            }
        )
        return get_action_trace_recorder().record(
            context,
            stage=stage,
            status=status,
            summary=summary,
            details=payload_details,
        )

    @contextmanager
    def trace_span(
        self,
        step: str,
        *,
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Iterator[None]:
        self.trace_event(step, stage="start", status="running", summary=summary, details=details)
        try:
            yield
        except Exception as exc:
            self.trace_event(
                step,
                stage="finish",
                status="error",
                summary=str(exc),
                details={"exception_type": type(exc).__name__, **(details or {})},
            )
            raise
        else:
            self.trace_event(step, stage="finish", status="ok", summary=summary, details=details)

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Уникальное имя модуля-коллектора.
        
        Это свойство используется для:
        - Идентификации модуля в логах
        - Маркировки собранных данных
        - Регистрации модуля в фабрике
        
        Returns:
            str: Имя модуля (например: "screen", "system", "input")
        
        Example:
            @property
            def name(self) -> str:
                return "screen"
        """
        pass
    
    @abstractmethod
    async def collect(self) -> Dict[str, Any]:
        """
        Асинхронный метод для сбора данных модулем.
        
        Этот метод вызывается оркестратором с определенным интервалом
        и должен возвращать собранные данные в виде словаря наблюдений.
        
        Метод должен:
        1. Быть асинхронным (async def)
        2. Возвращать dict с наблюдениями (JSON-совместимый)
        3. Не блокировать event loop долгими операциями
        4. Выбрасывать исключения при ошибках (оркестратор обработает их)
        
        Returns:
            Dict[str, Any]: Словарь с наблюдениями (observations).
                           JSON-совместимый словарь без обёрток типа
                           {"module":..., "status":...}.
                           Структура зависит от конкретного модуля.
        
        Raises:
            Exception: В случае ошибок сбора данных.
                      Исключения обрабатываются оркестратором и формируются
                      в структурированный ответ с ErrorInfo.
        
        Example:
            async def collect(self) -> Dict[str, Any]:
                # Сбор данных...
                return {
                    "timestamp": time.time(),
                    "cpu": 45.2,
                    "ram": 67.8
                }
        """
        pass
    
    def version(self) -> str:
        """
        Возвращает версию модуля.
        
        Может быть переопределен в дочерних классах для указания
        конкретной версии модуля. По умолчанию возвращает "0.0.0".
        
        Returns:
            str: Версия модуля в формате "X.Y.Z"
        
        Example:
            def version(self) -> str:
                return "1.2.3"
        """
        # Проверяем наличие поля __version__ в классе
        if hasattr(self.__class__, '__version__'):
            return self.__class__.__version__
        return "0.0.0"
    
    def __repr__(self) -> str:
        """
        Строковое представление модуля для отладки и логирования.
        
        Форматирует вывод модуля в удобочитаемом виде:
        <Collector: имя_модуля>
        
        Returns:
            str: Отформатированное представление модуля
        
        Example:
            >>> print(screen_module)
            <Collector: screen>
        """
        return f"<Collector: {self.name}>"
    
    def __str__(self) -> str:
        """
        Пользовательское строковое представление модуля.
        
        Returns:
            str: Имя модуля
        """
        return self.name
