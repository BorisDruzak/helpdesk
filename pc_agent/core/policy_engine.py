"""
PolicyEngine - движок политик безопасности для инструментов.

Реализует проверку доступа на основе:
- Роли актора (actor_role)
- Метаданных инструмента (ToolMetadata)
- Уровня риска (risk_level)
- Настроек безопасности (security.allow_remote_code)

Чистая логика без зависимостей от registry/DB.
"""

from typing import TypedDict, Optional

from core.tools import ToolMetadata
from pc_agent.config.config_loader import ConfigLoader


class PolicyDecision(TypedDict):
    """
    Решение политики доступа.
    
    Attributes:
        allow: Разрешен ли доступ
        reason: Причина отказа (если allow=False) или None
        requires_consent: Требуется ли согласие пользователя
        required_role: Требуемая роль для доступа (если применимо)
    """
    allow: bool
    reason: Optional[str]
    requires_consent: bool
    required_role: Optional[str]


class PolicyEngine:
    """
    Движок политик безопасности для проверки доступа к инструментам.
    
    Реализует правила на основе:
    - metadata.allow_roles (если задан)
    - risk_level с ролями по умолчанию
    - metadata.requires_consent
    - security.allow_remote_code (для code_exec)
    """
    
    def __init__(self):
        """Инициализация PolicyEngine."""
        self._config = None
    
    def _get_config(self):
        """Ленивая загрузка конфигурации."""
        if self._config is None:
            self._config = ConfigLoader().load()
        return self._config
    
    def decide(
        self,
        actor_role: str,
        tool_name: str,
        metadata: ToolMetadata,
        params: dict,
        context: dict
    ) -> PolicyDecision:
        """
        Принимает решение о доступе к инструменту.
        
        Args:
            actor_role: Роль актора ('llm', 'support', 'admin')
            tool_name: Имя инструмента (для логирования)
            metadata: Метаданные инструмента
            params: Параметры запроса (не используется в MVP)
            context: Контекст запроса (не используется в MVP)
        
        Returns:
            PolicyDecision с решением о доступе
        """
        # Правило 1: Проверка allow_roles (приоритетное). Если роль в whitelist — доступ разрешён, risk_level не применяем.
        if metadata.allow_roles is not None:
            if actor_role not in metadata.allow_roles:
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role=None
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        # Правило 1.5: Проверка "не admin → consent" для инструментов с requires_consent=True
        # Если actor_role != "admin" и metadata.requires_consent == True, требуется consent_token
        if actor_role != "admin":
            requires_consent_flag = getattr(metadata, "requires_consent", False) if hasattr(metadata, "requires_consent") else False
            
            if requires_consent_flag:
                # Проверяем наличие consent_token в params
                consent_token = params.get("consent_token") if params else None
                if consent_token is None:
                    return PolicyDecision(
                        allow=False,
                        reason="CONSENT_REQUIRED",
                        requires_consent=True,
                        required_role=None
                    )
                # Если consent_token присутствует, продолжаем проверку по risk_level
        
        # Правило 2: Проверка по risk_level
        risk_level = metadata.risk_level
        
        if risk_level == "safe_read":
            # safe_read: разрешено для llm, support, admin
            allowed_roles = {"llm", "support", "admin"}
            if actor_role not in allowed_roles:
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="llm, support или admin"
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        elif risk_level == "sensitive_read":
            # sensitive_read: разрешено для support, admin
            allowed_roles = {"support", "admin"}
            if actor_role not in allowed_roles:
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="support или admin"
                )
            # Проверяем requires_consent
            if metadata.requires_consent and actor_role != "admin":
                # Проверяем наличие consent_token в params
                consent_token = params.get("consent_token") if params else None
                if consent_token is None:
                    return PolicyDecision(
                        allow=False,
                        reason="CONSENT_REQUIRED",
                        requires_consent=True,
                        required_role=None
                    )
                # Если consent_token присутствует, разрешаем доступ
                return PolicyDecision(
                    allow=True,
                    reason=None,
                    requires_consent=False,
                    required_role=None
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        elif risk_level == "system_write":
            # system_write: разрешено только для admin
            if actor_role != "admin":
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="admin"
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        elif risk_level == "code_exec":
            # code_exec: разрешено только для admin
            if actor_role != "admin":
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="admin"
                )
            # Дополнительная проверка: security.allow_remote_code
            config = self._get_config()
            if not config.security.allow_remote_code:
                return PolicyDecision(
                    allow=False,
                    reason="REMOTE_CODE_DISABLED",
                    requires_consent=False,
                    required_role=None
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        else:
            # Неизвестный risk_level - по умолчанию запрещаем
            return PolicyDecision(
                allow=False,
                reason=f"UNKNOWN_RISK_LEVEL: {risk_level}",
                requires_consent=False,
                required_role=None
            )

