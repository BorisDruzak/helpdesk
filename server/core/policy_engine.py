"""
Server-side PolicyEngine for checking risky operations before enqueue.

Implements policy checks based on:
- Actor role (actor_role)
- Tool metadata (ToolMetadata)
- Risk level (risk_level)
- Consent requirements

This is the first line of defense before creating operations.
Agent-side policy check remains as second line of defense.
"""
from typing import Optional, Dict, Any
from loguru import logger

from core.tool_metadata import ToolMetadata, PolicyRiskLevel


class PolicyDecision:
    """
    Policy decision result.
    
    Attributes:
        allow: Whether access is allowed
        reason: Reason for denial (if allow=False) or None
        requires_consent: Whether consent is required
        required_role: Required role for access (if applicable)
    """
    
    def __init__(
        self,
        allow: bool,
        reason: Optional[str] = None,
        requires_consent: bool = False,
        required_role: Optional[str] = None
    ):
        self.allow = allow
        self.reason = reason
        self.requires_consent = requires_consent
        self.required_role = required_role
    
    def __repr__(self) -> str:
        return (
            f"<PolicyDecision(allow={self.allow}, reason={self.reason!r}, "
            f"requires_consent={self.requires_consent}, required_role={self.required_role!r})>"
        )


class PolicyEngine:
    """
    Server-side policy engine for checking risky operations.
    
    Implements rules based on:
    - metadata.allow_roles (if set)
    - risk_level with default roles
    - metadata.requires_consent
    - Security configuration (for code_exec)
    
    КРИТИЧНО: This is server-side check BEFORE creating operation.
    Agent-side policy check remains as second line of defense.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PolicyEngine.
        
        Args:
            config: Optional configuration dict with security settings
                   (e.g., {"allow_remote_code": False})
        """
        self.config = config or {}
    
    def check_policy(
        self,
        actor_role: str,
        tool_name: str,
        metadata: ToolMetadata,
        params: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        """
        Check policy for tool execution.
        
        Args:
            actor_role: Actor role ('admin', 'support', 'llm', 'user', 'agent', 'system')
            tool_name: Tool name (for logging)
            metadata: Tool metadata with risk_level, requires_consent, allow_roles
            params: Optional tool parameters (for consent_token check)
        
        Returns:
            PolicyDecision with access decision
        """
        # Rule 1: Check allow_roles (priority). Если роль в whitelist — доступ разрешён, risk_level не применяем.
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
                requires_consent=metadata.requires_consent and actor_role != "admin",
                required_role=None
            )
        
        # Rule 1.5: Check "non-admin → consent" for tools with requires_consent=True
        # If actor_role != "admin" and metadata.requires_consent == True, requires consent
        if actor_role != "admin":
            if metadata.requires_consent:
                # For server-side: if requires_consent=True, create operation with waiting_consent
                # Don't check consent_token here - that's handled in consent flow
                return PolicyDecision(
                    allow=True,  # Allow creation, but with waiting_consent status
                    reason=None,
                    requires_consent=True,
                    required_role=None
                )
        
        # Rule 2: Check by risk_level
        risk_level = metadata.risk_level
        
        if risk_level == "safe_read":
            # safe_read: allowed for llm, support, admin
            allowed_roles = {"llm", "support", "admin", "system"}
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
            # sensitive_read: allowed for support, admin
            allowed_roles = {"support", "admin", "system"}
            if actor_role not in allowed_roles:
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="support или admin"
                )
            # Check requires_consent
            if metadata.requires_consent and actor_role != "admin":
                # For server-side: create operation with waiting_consent
                return PolicyDecision(
                    allow=True,
                    reason=None,
                    requires_consent=True,
                    required_role=None
                )
            return PolicyDecision(
                allow=True,
                reason=None,
                requires_consent=False,
                required_role=None
            )
        
        elif risk_level == "system_write":
            # system_write: allowed only for admin
            if actor_role not in {"admin", "system"}:
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
            # code_exec: allowed only for admin
            if actor_role not in {"admin", "system"}:
                return PolicyDecision(
                    allow=False,
                    reason="ROLE_NOT_ALLOWED",
                    requires_consent=False,
                    required_role="admin"
                )
            # Additional check: security.allow_remote_code
            allow_remote_code = self.config.get("allow_remote_code", False)
            if not allow_remote_code:
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
            # Unknown risk_level - deny by default
            logger.warning(
                f"[PolicyEngine] Unknown risk_level: {risk_level} for tool {tool_name}"
            )
            return PolicyDecision(
                allow=False,
                reason=f"UNKNOWN_RISK_LEVEL: {risk_level}",
                requires_consent=False,
                required_role=None
            )
    
    def requires_consent(
        self,
        actor_role: str,
        tool_name: str,
        metadata: ToolMetadata
    ) -> bool:
        """
        Check if tool requires consent for given actor role.
        
        Args:
            actor_role: Actor role
            tool_name: Tool name (for logging)
            metadata: Tool metadata
        
        Returns:
            True if consent is required, False otherwise
        """
        decision = self.check_policy(actor_role, tool_name, metadata)
        return decision.requires_consent
    
    def get_tool_metadata(
        self,
        tool_name: str,
        tools_list: Optional[list[Dict[str, Any]]] = None
    ) -> Optional[ToolMetadata]:
        """
        Get ToolMetadata for tool from tools list.
        
        Args:
            tool_name: Tool name
            tools_list: List of tools from agent (from list_tools command result)
        
        Returns:
            ToolMetadata if found, None otherwise
        """
        if not tools_list:
            return None
        
        # Find tool in list (поддержка форматов агента: "tool" + spec.metadata и legacy: "name"/"tool_id" + metadata)
        for tool in tools_list:
            if (
                tool.get("name") == tool_name
                or tool.get("tool_id") == tool_name
                or tool.get("tool") == tool_name
            ):
                # Метаданные: верхний уровень или внутри spec (формат list_tools агента)
                metadata_dict = tool.get("metadata") or (tool.get("spec") or {}).get("metadata") or {}
                if not isinstance(metadata_dict, dict):
                    metadata_dict = {}
                allow_roles = metadata_dict.get("allow_roles")
                requires_consent = metadata_dict.get("requires_consent", False)
                # Старые снапшоты: для screen-инструментов разрешаем user/agent и не требуем consent (кнопка в GUI = явное действие)
                if tool_name in ("screen.collect", "screen.record"):
                    if allow_roles is None:
                        allow_roles = ["user", "agent", "llm", "support", "admin"]
                    requires_consent = False
                return ToolMetadata(
                    risk_level=metadata_dict.get("risk_level", "safe_read"),
                    scopes=metadata_dict.get("scopes", []),
                    requires_consent=requires_consent,
                    allow_roles=allow_roles
                )
        return None


