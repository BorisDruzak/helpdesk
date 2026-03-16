"""
Модели Pydantic для единого формата ответа команд агента.

Определяет структурированные типы для успешных, ошибочных и частичных ответов,
включая метаданные, артефакты и информацию об ошибках.
"""

from typing import Literal
from pydantic import BaseModel, Field


# Тип статуса выполнения команды
ToolStatus = Literal["success", "error", "partial"]


class ErrorInfo(BaseModel):
    """Информация об ошибке выполнения команды."""
    
    code: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение об ошибке")
    details: dict | None = Field(default=None, description="Дополнительные детали ошибки")
    retriable: bool = Field(default=False, description="Можно ли повторить операцию")


class ArtifactDescriptor(BaseModel):
    """Описание артефакта (файла, данных), созданного командой."""
    
    artifact_id: str | None = Field(default=None, description="Уникальный идентификатор артефакта")
    name: str = Field(..., description="Имя артефакта")
    mime: str | None = Field(default=None, description="MIME-тип артефакта")
    size_bytes: int | None = Field(default=None, description="Размер артефакта в байтах")
    sha256: str | None = Field(default=None, description="SHA256 хеш артефакта")
    url: str | None = Field(default=None, description="URL артефакта (если доступен удаленно)")
    local_path: str | None = Field(default=None, description="Локальный путь к артефакту")
    ttl_seconds: int | None = Field(default=None, description="Время жизни артефакта в секундах")
    kind: str | None = Field(default=None, description="Семантический тип: screenshot, screen_recording, log и т.д.")
    expires_at: str | None = Field(default=None, description="Время истечения TTL (ISO 8601)")


class ToolMeta(BaseModel):
    """Метаданные выполнения команды."""
    
    timestamp_iso: str = Field(..., description="ISO-формат временной метки выполнения")
    duration_ms: int | None = Field(default=None, description="Длительность выполнения в миллисекундах")
    request_id: str | None = Field(default=None, description="Идентификатор запроса")
    agent_id: str | None = Field(default=None, description="Идентификатор агента")
    command: str | None = Field(default=None, description="Название выполненной команды")
    module_versions: dict[str, str] = Field(default_factory=dict, description="Версии модулей, участвовавших в выполнении")


class ToolData(BaseModel):
    """Данные результата выполнения команды."""
    
    observations: dict = Field(default_factory=dict, description="Наблюдения и результаты выполнения")
    result: dict | None = Field(default=None, description="Структурированный результат команды (для job и других операций)")
    artifacts: list[ArtifactDescriptor] = Field(default_factory=list, description="Список созданных артефактов")
    warnings: list[str] = Field(default_factory=list, description="Список предупреждений")
    errors: list[ErrorInfo] | None = Field(default=None, description="Список ошибок (для partial статуса)")


class ToolResponse(BaseModel):
    """Единый формат ответа команды агента."""
    
    status: ToolStatus = Field(..., description="Статус выполнения команды")
    data: ToolData | None = Field(default=None, description="Данные результата (для success и partial)")
    error: ErrorInfo | None = Field(default=None, description="Информация об ошибке (для error)")
    meta: ToolMeta = Field(..., description="Метаданные выполнения")


def ok(data: ToolData, meta: ToolMeta) -> ToolResponse:
    """
    Создает успешный ответ команды.
    
    Args:
        data: Данные результата выполнения
        meta: Метаданные выполнения
    
    Returns:
        ToolResponse со статусом "success"
    """
    return ToolResponse(
        status="success",
        data=data,
        error=None,
        meta=meta
    )


def fail(
    code: str,
    message: str,
    meta: ToolMeta,
    details: dict | None = None,
    retriable: bool = False
) -> ToolResponse:
    """
    Создает ответ об ошибке выполнения команды.
    
    Args:
        code: Код ошибки
        message: Сообщение об ошибке
        meta: Метаданные выполнения
        details: Дополнительные детали ошибки
        retriable: Можно ли повторить операцию
    
    Returns:
        ToolResponse со статусом "error"
    """
    error = ErrorInfo(
        code=code,
        message=message,
        details=details,
        retriable=retriable
    )
    return ToolResponse(
        status="error",
        data=None,
        error=error,
        meta=meta
    )


def partial(
    data: ToolData,
    meta: ToolMeta,
    warnings: list[str],
    errors: list[ErrorInfo] | None = None
) -> ToolResponse:
    """
    Создает частично успешный ответ команды.
    
    Args:
        data: Данные результата выполнения
        meta: Метаданные выполнения
        warnings: Список предупреждений
        errors: Список ошибок (опционально)
    
    Returns:
        ToolResponse со статусом "partial"
    """
    # Обновляем warnings в data
    data.warnings = warnings
    
    # Если есть errors, добавляем их в data
    if errors is not None:
        data.errors = errors
    
    return ToolResponse(
        status="partial",
        data=data,
        error=None,
        meta=meta
    )

