"""
Stage 10: Репозиторий UI пользователей (ui_users, ui_user_audit).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.db.models import UiUser, UiUserAudit
from shared.redaction import redact_sensitive_payload

VALID_ROLES = ("admin", "support", "auditor", "user")
DEFAULT_USER_ROLE = "user"
MAX_USER_LOGIN_LENGTH = 100


def normalize_user_login(value: object) -> str:
    return str(value or "").strip().lower()


class UiUsersRepo:
    """Репозиторий для ui_users и ui_user_audit."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_login(self, user_login: str) -> Optional[UiUser]:
        """Получить пользователя по логину."""
        normalized_login = normalize_user_login(user_login)
        if not normalized_login:
            return None
        stmt = (
            select(UiUser)
            .where(func.lower(func.trim(UiUser.user_login)) == normalized_login)
            .order_by(UiUser.user_login)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(
        self,
        include_inactive: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> List[UiUser]:
        """Список пользователей (без паролей в ответе — вызывающий не должен отдавать password_hash)."""
        stmt = select(UiUser).order_by(UiUser.user_login)
        if not include_inactive:
            stmt = stmt.where(UiUser.is_active == True)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_user(
        self,
        user_login: str,
        password_hash: str,
        actor_role: str = DEFAULT_USER_ROLE,
        actor_id: Optional[str] = None,
    ) -> UiUser:
        """Создать пользователя. Роль нормализуется к admin при невалидной."""
        login = normalize_user_login(user_login)
        if not login or len(login) > MAX_USER_LOGIN_LENGTH:
            raise ValueError("Invalid user_login")
        role = (actor_role or DEFAULT_USER_ROLE).strip().lower()
        if role not in VALID_ROLES:
            raise ValueError("Invalid actor_role")
        existing = await self.get_by_login(login)
        if existing is not None:
            raise ValueError("User already exists")
        user = UiUser(
            user_login=login,
            password_hash=password_hash,
            actor_role=role,
            is_active=True,
            failed_attempts=0,
            locked_until=None,
        )
        self.session.add(user)
        await self._audit(login, "user_created", actor_id, {"actor_role": role})
        try:
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"[UiUsersRepo] create_user conflict: {e}")
            raise ValueError("User already exists") from e

    async def update_user(
        self,
        user_login: str,
        actor_role: Optional[str] = None,
        is_active: Optional[bool] = None,
        actor_id: Optional[str] = None,
    ) -> Optional[UiUser]:
        """Обновить роль и/или is_active."""
        user = await self.get_by_login(user_login)
        if not user:
            return None
        before = {"actor_role": user.actor_role, "is_active": user.is_active}
        if actor_role is not None:
            role = str(actor_role or "").strip().lower()
            if role not in VALID_ROLES:
                raise ValueError("Invalid actor_role")
            user.actor_role = role
        if is_active is not None:
            user.is_active = is_active
        after = {"actor_role": user.actor_role, "is_active": user.is_active}
        await self._audit(user.user_login, "user_updated", actor_id, {"before": before, "after": after})
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def set_password(
        self,
        user_login: str,
        password_hash: str,
        actor_id: Optional[str] = None,
    ) -> bool:
        """Установить новый хеш пароля. Сбрасывает failed_attempts и locked_until."""
        user = await self.get_by_login(user_login)
        if not user:
            return False
        user.password_hash = password_hash
        user.failed_attempts = 0
        user.locked_until = None
        await self._audit(user.user_login, "password_changed", actor_id, {})
        await self.session.commit()
        return True

    async def record_login_success(self, user_login: str) -> None:
        """Обновить last_login_at и сбросить failed_attempts, locked_until."""
        user = await self.get_by_login(user_login)
        if not user:
            return
        user.last_login_at = datetime.now(timezone.utc)
        user.failed_attempts = 0
        user.locked_until = None
        await self._audit(user.user_login, "login_success", normalize_user_login(user_login), {})
        await self.session.commit()

    async def increment_failed_attempts(
        self,
        user_login: str,
        max_attempts: int,
        lock_minutes: int,
    ) -> bool:
        """
        Увеличить счётчик неудачных попыток. При достижении max_attempts установить locked_until.
        Returns: True если пользователь теперь заблокирован.
        """
        user = await self.get_by_login(user_login)
        if not user:
            return False
        user.failed_attempts = (user.failed_attempts or 0) + 1
        locked = False
        if user.failed_attempts >= max_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
            locked = True
        await self._audit(
            user.user_login,
            "login_failed",
            normalize_user_login(user_login),
            {"failed_attempts": user.failed_attempts, "locked": locked},
        )
        await self.session.commit()
        return locked

    def is_locked(self, user: UiUser) -> bool:
        """Проверить, истёк ли lock."""
        if not user.locked_until:
            return False
        return datetime.now(timezone.utc) < user.locked_until

    async def deactivate_user(self, user_login: str, actor_id: Optional[str] = None) -> bool:
        """Мягкая деактивация (is_active=False)."""
        return await self.update_user(user_login, is_active=False, actor_id=actor_id) is not None

    async def _audit(
        self,
        user_login: str,
        action: str,
        actor_id: Optional[str],
        details_json: dict,
    ) -> None:
        """Записать запись в ui_user_audit."""
        audit = UiUserAudit(
            user_login=user_login,
            action=action,
            actor_id=actor_id,
            details_json=redact_sensitive_payload(details_json or {}),
        )
        self.session.add(audit)

    async def get_audit(
        self,
        user_login: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UiUserAudit]:
        """Список записей аудита (опционально по user_login)."""
        stmt = select(UiUserAudit).order_by(UiUserAudit.created_at.desc())
        if user_login is not None:
            stmt = stmt.where(func.lower(func.trim(UiUserAudit.user_login)) == normalize_user_login(user_login))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
