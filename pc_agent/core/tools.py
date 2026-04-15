"""Agent-side tool spec helpers backed by the shared contract layer."""

import sys
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from loguru import logger
from core.artifacts import ArtifactManager
try:
    from shared.tool_contracts import (
        ToolMetadata,
        normalize_risk_level,
        to_legacy_risk_level,
    )
except ModuleNotFoundError:  # pragma: no cover - defensive path for nested cwd entrypoints
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from shared.tool_contracts import (
        ToolMetadata,
        normalize_risk_level,
        to_legacy_risk_level,
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
    risk_level: str = Field(default="safe_readonly", description="Legacy risk level for transport compatibility")
    capabilities: list[str] = Field(default_factory=list, description="Список возможностей инструмента")
    params_schema: dict = Field(default_factory=dict, description="JSON Schema для параметров (пока может быть пустым)")
    result_schema: dict = Field(default_factory=dict, description="JSON Schema для результата (опционально, может быть пустым)")
    aliases: list[str] = Field(default_factory=list, description="Legacy aliases for the tool")
    metadata: ToolMetadata = Field(
        default_factory=lambda: ToolMetadata(),
        description="Метаданные инструмента для PolicyEngine"
    )
    contract_version: str = Field(default="1.0.0", description="Version of the external tool contract")
    lifecycle: str = Field(default="stable", description="Lifecycle status for the tool contract")
    dependencies: dict = Field(default_factory=dict, description="Declared runtime dependencies")
    error_codes: list[str] = Field(default_factory=list, description="Stable machine-readable error codes")
    artifact_types: list[dict] = Field(default_factory=list, description="Declared artifact descriptors")
    redaction: dict = Field(default_factory=dict, description="Redaction policy for result serialization")
    resources: dict = Field(default_factory=dict, description="Runtime resource limits")


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
    normalized_risk = normalize_risk_level(spec.metadata.risk_level or spec.risk_level)

    if normalized_risk in ("system_write", "code_exec"):
        if actor_role != "admin":
            reason = (
                f"Инструмент '{spec.name}' имеет уровень риска '{normalized_risk}' "
                f"и требует роль 'admin', но текущая роль: '{actor_role}'"
            )
            return False, reason
    
    # Проверка для sensitive_read: запрет для llm
    if normalized_risk == "sensitive_read":
        if actor_role == "llm":
            reason = (
                f"Инструмент '{spec.name}' имеет уровень риска 'sensitive_read' "
                f"и недоступен для роли 'llm'"
            )
            return False, reason
    
    # Все остальные случаи разрешены
    return True, None


__all__ = [
    "ToolMetadata",
    "ToolSpec",
    "ToolContext",
    "check_policy",
    "normalize_risk_level",
    "to_legacy_risk_level",
]
