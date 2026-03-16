"""
AuthContext for authentication and authorization.

AuthContext is the single source of truth for actor_role and actor_id.
It is created from token/session after authentication and passed through
middleware/handler context. We NEVER trust actor_role from JSON body/WS payload.
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class AuthType(str, Enum):
    """Type of authentication."""
    AGENT_TOKEN = "agent_token"
    UI_TOKEN = "ui_token"
    PUBLIC_TICKET_TOKEN = "public_ticket_token"
    SESSION = "session"  # For Phase 2
    SYSTEM = "system"  # Internal system actions


@dataclass
class AuthContext:
    """
    Authentication context containing actor information.
    
    This is the ONLY source of truth for actor_role and actor_id.
    Never trust actor_role from JSON body or WebSocket payload.
    """
    actor_id: str  # device_id for agents, user_login for UI
    actor_role: str  # agent, admin, support, llm, user, system
    auth_type: AuthType
    token: Optional[str] = None  # Raw token (for logging/audit, not stored in DB)
    ticket_scope: Optional[str] = None  # For public ticket tokens
    
    def __repr__(self) -> str:
        return (
            f"<AuthContext(actor_id={self.actor_id!r}, "
            f"actor_role={self.actor_role!r}, auth_type={self.auth_type.value}, "
            f"ticket_scope={self.ticket_scope!r})>"
        )
    
    def is_admin(self) -> bool:
        """Check if actor is admin."""
        return self.actor_role == "admin"
    
    def is_support(self) -> bool:
        """Check if actor is support."""
        return self.actor_role == "support"
    
    def is_agent(self) -> bool:
        """Check if actor is agent."""
        return self.actor_role == "agent"
    
    def is_system(self) -> bool:
        """Check if actor is system."""
        return self.actor_role == "system"
    
    def has_role(self, *roles: str) -> bool:
        """Check if actor has any of the specified roles."""
        return self.actor_role in roles

