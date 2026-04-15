"""
Базовые сущности для универсальной формулы инструментов.

Определяет:
- RiskLevel: уровни риска инструментов
- ToolSpec: спецификация инструмента
- ToolContext: контекст выполнения инструмента
- check_policy: функция проверки политики доступа
"""

from typing import Literal, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from loguru import logger
from core.artifacts import ArtifactManager


# Уровни риска инструментов (старый формат для обратной совместимости)
RiskLevel = Literal["safe_readonly", "sensitive_read", "write_action", "break_glass"]

# Новые уровни риска для PolicyEngine
PolicyRiskLevel = Literal["safe_read", "sensitive_read", "system_write", "code_exec"]


class ToolMetadata(BaseModel):
    """
    Метаданные инструмента для PolicyEngine.
    
    Определяет уровень риска, области доступа, необходимость согласия
    и разрешенные роли для использования инструмента.
    """
    
    domain: str = Field(
        default="system",
        description="Логический домен/namespace инструмента"
    )
    platforms: list[str] = Field(
        default_factory=lambda: ["any"],
        description="Поддерживаемые платформы"
    )
    risk_level: PolicyRiskLevel = Field(
        default="safe_read",
        description="Уровень риска инструмента"
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Список областей доступа (scopes)"
    )
    requires_consent: bool = Field(
        default=False,
        description="Требуется ли согласие пользователя для использования"
    )
    allow_roles: Optional[list[str]] = Field(
        default=None,
        description="Список разрешенных ролей. Если None, PolicyEngine решает по risk_level"
    )
    timeout_sec: Optional[int] = Field(
        default=None,
        description="Рекомендуемый таймаут выполнения"
    )
    idempotent: bool = Field(
        default=False,
        description="Идемпотентен ли диагностический шаг"
    )
    origin: str = Field(
        default="builtin",
        description="Источник инструмента: builtin/managed/legacy"
    )
    side_effects: bool = Field(
        default=False,
        description="Есть ли у инструмента побочные эффекты"
    )


class ToolSpec(BaseModel):
    """
    Спецификация инструмента.
    
    Описывает метаданные инструмента: имя, описание, версию,
    уровень риска, возможности и схемы параметров/результатов.
    """
    
    name: str = Field(..., description="Имя инструмента (например, 'collect.system', 'diag.logs.collect')")
    description: str = Field(..., description="Описание назначения инструмента")
    version: str = Field(default="0.0.0", description="Версия инструмента")
    risk_level: RiskLevel = Field(default="safe_readonly", description="Уровень риска инструмента")
    capabilities: list[str] = Field(default_factory=list, description="Список возможностей инструмента")
    params_schema: dict = Field(default_factory=dict, description="JSON Schema для параметров (пока может быть пустым)")
    result_schema: dict = Field(default_factory=dict, description="JSON Schema для результата (опционально, может быть пустым)")
    aliases: list[str] = Field(default_factory=list, description="Legacy aliases for the tool")
    metadata: ToolMetadata = Field(
        default_factory=lambda: ToolMetadata(),
        description="Метаданные инструмента для PolicyEngine"
    )


@dataclass
class ToolContext:
    """
    Контекст выполнения инструмента.
    
    Содержит информацию о роли актора, идентификаторах запроса/устройства,
    логгере, менеджере артефактов, конфигурации и лимитах.
    """
    
    actor_role: str = field(metadata={"description": "Роль актора: 'user', 'admin' или 'llm'"})
    request_id: str = field(metadata={"description": "Идентификатор запроса"})
    device_id: Optional[str] = field(default=None, metadata={"description": "Идентификатор устройства"})
    logger: Any = field(default_factory=lambda: logger, metadata={"description": "Логгер (loguru)"})
    artifact_manager: Optional[ArtifactManager] = field(default=None, metadata={"description": "Менеджер артефактов"})
    config: Optional[dict] = field(default=None, metadata={"description": "Конфигурация/настройки (если доступно)"})
    limits: dict = field(
        default_factory=lambda: {
            "max_artifacts": None,  # Заглушка: максимальное количество артефактов
            "max_bytes": None  # Заглушка: максимальный размер в байтах
        },
        metadata={"description": "Лимиты выполнения (max_artifacts, max_bytes)"}
    )


def check_policy(spec: ToolSpec, actor_role: str) -> tuple[bool, Optional[str]]:
    """
    Проверяет политику доступа к инструменту на основе уровня риска и роли актора.
    
    Правила по умолчанию:
    - Если risk_level in ("write_action", "break_glass") и actor_role != "admin" -> запрет
    - Если risk_level == "sensitive_read" и actor_role == "llm" -> запрет
    - Иначе разрешить
    
    Args:
        spec: Спецификация инструмента
        actor_role: Роль актора ("user", "admin" или "llm")
    
    Returns:
        Кортеж (разрешено: bool, причина_отказа: str | None)
        Если разрешено=True, то причина_отказа=None
        Если разрешено=False, то причина_отказа содержит описание причины отказа
    """
    # Проверка для write_action и break_glass: только admin
    if spec.risk_level in ("write_action", "break_glass"):
        if actor_role != "admin":
            reason = (
                f"Инструмент '{spec.name}' имеет уровень риска '{spec.risk_level}' "
                f"и требует роль 'admin', но текущая роль: '{actor_role}'"
            )
            return False, reason
    
    # Проверка для sensitive_read: запрет для llm
    if spec.risk_level == "sensitive_read":
        if actor_role == "llm":
            reason = (
                f"Инструмент '{spec.name}' имеет уровень риска 'sensitive_read' "
                f"и недоступен для роли 'llm'"
            )
            return False, reason
    
    # Все остальные случаи разрешены
    return True, None

