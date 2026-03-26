"""
Сервис аутентификации.
"""

import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from loguru import logger

from app.db import get_session
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.devices_repo import DevicesRepo
from app.repos.ui_users_repo import UiUsersRepo
from auth.password_service import verify_password


class ArchivedDeviceError(Exception):
    """Raised when token issuance/auth is attempted for an archived device."""


class AuthService:
    """Сервис для работы с аутентификацией."""
    _LEGACY_TOKEN_STORE: dict[str, dict] = {}
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    async def authenticate(self, login: str, password: str) -> Tuple[bool, str]:
        """
        Проверяет логин и пароль пользователя.
        Stage 10: при AUTH_UI_DB_USERS_ENABLED сначала БД (ui_users), иначе/fallback — state.users.
        Роль при успехе: из ui_users.actor_role (DB) или UI_USER_ROLES/fallback admin (config).
        
        Args:
            login: Логин пользователя
            password: Пароль пользователя
        
        Returns:
            (success, actor_role) — при success=True роль для выдачи токена
        """
        from config import (
            AUTH_UI_DB_USERS_ENABLED,
            AUTH_UI_CONFIG_FALLBACK_ENABLED,
            AUTH_UI_MAX_FAILED_ATTEMPTS,
            AUTH_UI_LOCK_MINUTES,
            UI_USER_ROLES,
        )
        if AUTH_UI_DB_USERS_ENABLED:
            async with get_session() as session:
                repo = UiUsersRepo(session)
                user = await repo.get_by_login(login)
                if user:
                    if not user.is_active:
                        return False, "admin"
                    if repo.is_locked(user):
                        return False, "admin"
                    if verify_password(password, user.password_hash):
                        await repo.record_login_success(login)
                        return True, user.actor_role
                    await repo.increment_failed_attempts(
                        login, AUTH_UI_MAX_FAILED_ATTEMPTS, AUTH_UI_LOCK_MINUTES
                    )
                    return False, "admin"
                # Пользователь не в БД — fallback на config
                if not AUTH_UI_CONFIG_FALLBACK_ENABLED:
                    return False, "admin"
        # Config-based auth (legacy или fallback)
        if login in self.state.users and self.state.users[login] == password:
            from config import UI_USER_ROLES
            role = UI_USER_ROLES.get(login, "admin")
            return True, role
        return False, "admin"
    
    @staticmethod
    def _generate_raw_token() -> str:
        """
        Генерирует случайный токен.
        
        Returns:
            Raw token string (32 bytes, hex encoded = 64 chars)
        """
        return secrets.token_hex(32)
    
    async def generate_agent_token(
        self,
        device_id: str,
        expires_hours: Optional[int] = 4320  # 180 дней (180 * 24 = 4320 часов)
    ) -> str:
        """
        Генерирует токен для агента с сохранением в БД.
        
        КРИТИЧНО: В БД сохраняется только SHA256 hash, не raw token.
        Клиент получает raw token для использования.
        
        Args:
            device_id: UUID устройства
            expires_hours: Срок действия токена в часах (default: 4320 = 180 дней)
        
        Returns:
            Raw token string (для передачи клиенту)
        """
        raw_token = self._generate_raw_token()
        
        expires_at = None
        if expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            devices_repo = DevicesRepo(session)
            try:
                existing_device = await devices_repo.get_by_device_id(device_id, include_deleted=True)
                if existing_device and existing_device.deleted_at is not None:
                    raise ArchivedDeviceError("Device is archived and must be restored before reprovision.")

                # agent_tokens.device_id is linked to devices, so we keep a lightweight
                # placeholder row until the first real handshake fills it with metadata.
                await devices_repo.ensure_device_exists(device_id)
                token, _ = await repo.create_agent_token(
                    token=raw_token,
                    device_id=device_id,
                    expires_at=expires_at
                )
                logger.info(
                    f"[AuthService] Generated agent token: device_id={device_id}. "
                    f"Placeholder device row is ready and will be enriched on first successful handshake."
                )
                return token
            except ValueError as e:
                # Active token limit exceeded
                logger.warning(f"[AuthService] Token limit exceeded: {e}")
                raise
    
    async def generate_ui_token(
        self,
        user_login: str,
        actor_role: str,
        expires_hours: Optional[int] = 1
    ) -> str:
        """
        Генерирует токен для UI пользователя с сохранением в БД.
        
        КРИТИЧНО: В БД сохраняется только SHA256 hash, не raw token.
        Клиент получает raw token для использования.
        
        Args:
            user_login: Логин пользователя
            actor_role: Роль пользователя (admin, support, etc.)
            expires_hours: Срок действия токена в часах (default: 1)
        
        Returns:
            Raw token string (для передачи клиенту)
        """
        raw_token = self._generate_raw_token()
        
        expires_at = None
        if expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token, _ = await repo.create_ui_token(
                token=raw_token,
                user_login=user_login,
                actor_role=actor_role,
                expires_at=expires_at
            )
            logger.info(f"[AuthService] Generated UI token: user_login={user_login}, role={actor_role}")
            return token

    async def generate_ticket_public_session_token(
        self,
        ticket_id: str,
        actor_id: str,
        expires_minutes: int,
    ) -> str:
        raw_token = self._generate_raw_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token, _ = await repo.create_ticket_public_session(
                token=raw_token,
                ticket_id=ticket_id,
                actor_id=actor_id,
                expires_at=expires_at,
            )
            logger.info(f"[AuthService] Generated public ticket session: ticket_id={ticket_id}")
            return token
    
    def generate_token(self, uuid_str: str, login: str) -> str:
        """
        Compatibility method for older integrations.
        
        Prefer generate_agent_token() for new code.
        This method still works but uses legacy in-process storage.
        
        Args:
            uuid_str: UUID устройства
            login: Логин пользователя
        
        Returns:
            Сгенерированный токен
        """
        token = f"token-{uuid_str}"
        
        # Legacy-only storage (не участвует в production auth path).
        self._LEGACY_TOKEN_STORE[token] = {
            "uuid": uuid_str,
            "user": login,
            "created_at": time.time()
        }
        
        logger.warning(f"[AuthService] Using legacy generate_token() for device_id={uuid_str}. Use generate_agent_token() instead.")
        
        return token
    
    async def verify_agent_token(self, token: str) -> Optional[dict]:
        """
        Проверяет валидность токена агента через БД.
        
        Args:
            token: Raw token string
        
        Returns:
            Dict с информацией о токене (device_id, created_at) или None
        """
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            devices_repo = DevicesRepo(session)
            token_record = await repo.verify_agent_token(token)
            
            if token_record:
                device = await devices_repo.get_by_device_id(token_record.device_id, include_deleted=True)
                if device and device.deleted_at is not None:
                    logger.warning(
                        f"[AuthService] Agent token rejected for archived device: "
                        f"device_id={token_record.device_id}"
                    )
                    return None
                return {
                    "device_id": token_record.device_id,
                    "created_at": token_record.created_at.isoformat(),
                    "type": "agent"
                }
            return None
    
    async def verify_ui_token(self, token: str) -> Optional[dict]:
        """
        Проверяет валидность токена UI через БД.
        
        Args:
            token: Raw token string
        
        Returns:
            Dict с информацией о токене (user_login, actor_role, created_at) или None
        """
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token_record = await repo.verify_ui_token(token)
            
            if token_record:
                return {
                    "user_login": token_record.user_login,
                    "actor_role": token_record.actor_role,
                    "created_at": token_record.created_at.isoformat(),
                    "type": "ui"
                }
            return None

    async def verify_ticket_public_session_token(self, token: str) -> Optional[dict]:
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token_record = await repo.verify_ticket_public_session(token)
            if token_record:
                return {
                    "ticket_id": token_record.ticket_id,
                    "actor_id": token_record.actor_id,
                    "created_at": token_record.created_at.isoformat(),
                    "expires_at": token_record.expires_at.isoformat(),
                    "type": "ticket_public",
                }
            return None
    
    def verify_token(self, token: str) -> Optional[dict]:
        """
        Compatibility method for older integrations.
        
        Prefer verify_agent_token() or verify_ui_token() for new code.
        This method checks legacy in-process storage only.
        
        Args:
            token: Токен для проверки
        
        Returns:
            Информация о токене если он валиден, иначе None
        """
        # Legacy-only in-memory store (internal compatibility path).
        if token in self._LEGACY_TOKEN_STORE:
            legacy_data = self._LEGACY_TOKEN_STORE[token]
            logger.debug(f"[AuthService] Token found in legacy token store: {token[:8]}...")
            return legacy_data
        
        # Fallback to DB требует async; этот метод sync — legacy. Использовать verify_agent_token/verify_ui_token (docs/BOTTLENECKS_AND_RISKS.md Phase 3).
        logger.warning(
            "[AuthService] verify_token() called with token not in legacy token store. "
            "Use async verify_agent_token() or verify_ui_token() instead."
        )
        return None
    
    async def revoke_agent_token(self, token: str) -> bool:
        """
        Отзывает токен агента через БД.
        
        Args:
            token: Raw token string
        
        Returns:
            True если токен был отозван, False если не найден
        """
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            return await repo.revoke_agent_token(token)
    
    async def revoke_ui_token(self, token: str) -> bool:
        """
        Отзывает токен UI через БД.
        
        Args:
            token: Raw token string
        
        Returns:
            True если токен был отозван, False если не найден
        """
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            return await repo.revoke_ui_token(token)
    
    def revoke_token(self, token: str) -> None:
        """
        Compatibility method for older integrations.
        
        Prefer revoke_agent_token() or revoke_ui_token() for new code.
        
        Args:
            token: Токен для отзыва
        """
        if token in self._LEGACY_TOKEN_STORE:
            del self._LEGACY_TOKEN_STORE[token]
            logger.info(f"[AuthService] Revoked legacy token: {token[:8]}...")
        else:
            logger.warning(
                "[AuthService] revoke_token() called with token not in legacy store. "
                "Use async revoke_agent_token() or revoke_ui_token() instead."
            )
