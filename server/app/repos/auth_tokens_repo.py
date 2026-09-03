"""
Auth tokens repository for token management operations.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.db.models import UiToken, Ticket, TicketPublicSession


class AuthTokensRepo:
    """Repository for auth token operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @staticmethod
    def hash_token(token: str) -> str:
        """
        Compute SHA256 hash of token.
        
        Args:
            token: Raw token string
            
        Returns:
            SHA256 hash as hex string (64 characters)
        """
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    @staticmethod
    def get_token_prefix(token: str) -> str:
        """
        Get first 8 characters of token for logging.
        
        Args:
            token: Raw token string
            
        Returns:
            First 8 characters
        """
        return token[:8] if len(token) >= 8 else token
    
    async def create_ui_token(
        self,
        token: str,
        user_login: str,
        actor_role: str,
        expires_at: Optional[datetime] = None
    ) -> Tuple[str, UiToken]:
        """
        Create UI token with hashing.
        
        КРИТИЧНО: В БД сохраняется только SHA256 hash, не raw token.
        Клиент получает raw token для использования.
        
        Args:
            token: Raw token string (will be hashed)
            user_login: User login
            actor_role: Actor role (admin, support, etc.)
            expires_at: Optional expiration time
            
        Returns:
            Tuple of (raw_token, UiToken record)
        """
        token_hash = self.hash_token(token)
        token_prefix = self.get_token_prefix(token)
        
        ui_token = UiToken(
            token_hash=token_hash,
            token_prefix=token_prefix,
            user_login=user_login,
            actor_role=actor_role,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_hash=None,
            rotated_at=None,
            last_used_at=None
        )
        
        self.session.add(ui_token)
        try:
            await self.session.commit()
            await self.session.refresh(ui_token)
            logger.info(f"[AuthTokensRepo] Created UI token: user_login={user_login}, role={actor_role}, prefix={token_prefix}")
            return token, ui_token
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"[AuthTokensRepo] Failed to create UI token: {e}")
            raise
    
    async def verify_ui_token(self, token: str) -> Optional[UiToken]:
        """
        Verify UI token by hash lookup.
        
        Args:
            token: Raw token string
            
        Returns:
            UiToken if valid, None otherwise
            
        Checks:
            - Token hash exists
            - Not revoked
            - Not expired
            - Not replaced (unless within grace period)
        """
        token_clean = (token or "").strip()
        if not token_clean:
            return None
        token_hash = self.hash_token(token_clean)
        
        stmt = select(UiToken).where(
            UiToken.token_hash == token_hash
        )
        result = await self.session.execute(stmt)
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            return None
        
        # Check if revoked
        if token_record.revoked_at is not None:
            return None
        
        # Check if expired
        if token_record.expires_at and token_record.expires_at < datetime.now(timezone.utc):
            return None
        
        # Check if replaced (grace period: 5 minutes)
        if token_record.replaced_by_token_hash:
            if token_record.rotated_at:
                grace_period = timedelta(minutes=5)
                if datetime.now(timezone.utc) - token_record.rotated_at > grace_period:
                    return None  # Grace period expired
            else:
                return None  # Replaced but no rotation time (should not happen)
        
        # Update last_used_at
        token_record.last_used_at = datetime.now(timezone.utc)
        await self.session.commit()
        
        return token_record

    async def create_ticket_public_session(
        self,
        token: str,
        ticket_id: str,
        actor_id: str,
        expires_at: datetime,
    ) -> Tuple[str, TicketPublicSession]:
        token_hash = self.hash_token(token)
        token_prefix = self.get_token_prefix(token)

        record = TicketPublicSession(
            token_hash=token_hash,
            token_prefix=token_prefix,
            ticket_id=ticket_id,
            actor_id=actor_id,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
        )
        self.session.add(record)
        try:
            await self.session.commit()
            await self.session.refresh(record)
            logger.info(
                f"[AuthTokensRepo] Created public ticket session: ticket_id={ticket_id}, prefix={token_prefix}"
            )
            return token, record
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"[AuthTokensRepo] Failed to create public ticket session: {e}")
            raise

    async def verify_ticket_public_session(self, token: str) -> Optional[TicketPublicSession]:
        token_clean = (token or "").strip()
        if not token_clean:
            return None
        token_hash = self.hash_token(token_clean)
        stmt = (
            select(TicketPublicSession)
            .join(Ticket, Ticket.ticket_id == TicketPublicSession.ticket_id)
            .where(TicketPublicSession.token_hash == token_hash)
            .where(func.lower(Ticket.status).notin_(("closed", "canceled")))
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return None
        if record.revoked_at is not None:
            return None
        if record.expires_at < datetime.now(timezone.utc):
            return None
        record.last_used_at = datetime.now(timezone.utc)
        await self.session.commit()
        return record

    async def revoke_ticket_public_sessions(self, ticket_id: str, commit: bool = True) -> int:
        stmt = (
            update(TicketPublicSession)
            .where(
                and_(
                    TicketPublicSession.ticket_id == ticket_id,
                    TicketPublicSession.revoked_at.is_(None),
                )
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return int(result.rowcount or 0)
    
    async def revoke_ui_token(self, token: str) -> bool:
        """
        Revoke UI token.
        
        Args:
            token: Raw token string
            
        Returns:
            True if token was revoked, False if not found
        """
        token_hash = self.hash_token(token)
        
        stmt = (
            update(UiToken)
            .where(UiToken.token_hash == token_hash)
            .where(UiToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        if result.rowcount > 0:
            logger.info(f"[AuthTokensRepo] Revoked UI token: prefix={self.get_token_prefix(token)}")
            return True
        return False

    async def revoke_active_ui_tokens_for_user(self, user_login: str, *, commit: bool = True) -> int:
        """
        Revoke every non-revoked UI token for one UI user.
        """
        login = (user_login or "").strip()
        if not login:
            return 0

        stmt = (
            update(UiToken)
            .where(func.lower(UiToken.user_login) == login.lower())
            .where(UiToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        if commit:
            await self.session.commit()

        count = int(result.rowcount or 0)
        if count:
            logger.info(f"[AuthTokensRepo] Revoked {count} active UI token(s): user_login={login}")
        return count
    
    async def get_ui_token_by_user(self, user_login: str) -> Optional[UiToken]:
        """
        Get active UI token for user_login.
        
        Args:
            user_login: User login
            
        Returns:
            Active UiToken or None
        """
        stmt = (
            select(UiToken)
            .where(UiToken.user_login == user_login)
            .where(UiToken.revoked_at.is_(None))
            .order_by(UiToken.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
