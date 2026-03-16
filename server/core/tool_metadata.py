"""
ToolMetadata model for server-side policy engine.

Sync with pc_agent/core/tools.py ToolMetadata.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


# Уровни риска для PolicyEngine
PolicyRiskLevel = Literal["safe_read", "sensitive_read", "system_write", "code_exec"]


class ToolMetadata(BaseModel):
    """
    Метаданные инструмента для PolicyEngine.
    
    Определяет уровень риска, области доступа, необходимость согласия
    и разрешенные роли для использования инструмента.
    
    КРИТИЧНО: Должен быть синхронизирован с pc_agent/core/tools.py ToolMetadata.
    """
    
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


