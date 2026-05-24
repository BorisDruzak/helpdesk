"""
Auth tokens repository for token management operations.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.db.models import AgentToken, UiToken, TicketPublicSession


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
    
    async def create_agent_token(
        self,
        token: str,
        device_id: str,
        expires_at: Optional[datetime] = None,
        replace_existing: bool = False,
        max_active_tokens: Optional[int] = None,
        commit: bool = True,
    ) -> Tuple[str, AgentToken]:
        """
        Create agent token with hashing.
        
        КРИТИЧНО: В БД сохраняется только SHA256 hash, не raw token.
        Клиент получает raw token для использования.
        
        Args:
            token: Raw token string (will be hashed)
            device_id: Device identifier
            expires_at: Optional expiration time
            
        Returns:
            Tuple of (raw_token, AgentToken record)
            
        replace_existing:
            When true, old active tokens for the same device are revoked in the
            same transaction. Device identity is protected by machine_id and the
            device fingerprint, not by a hard active-token counter.
        """
        token_hash = self.hash_token(token)
        token_prefix = self.get_token_prefix(token)
        now = datetime.now(timezone.utc)

        if replace_existing:
            await self.revoke_active_agent_tokens_for_device(
                device_id,
                except_token_hash=token_hash,
                commit=False,
            )
        elif max_active_tokens is not None:
            active_count = await self.check_active_token_limit(device_id)
            if active_count >= max(int(max_active_tokens), 1):
                raise ValueError(f"Active agent token limit exceeded ({active_count}/{max_active_tokens})")
        
        agent_token = AgentToken(
            token_hash=token_hash,
            token_prefix=token_prefix,
            device_id=device_id,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_hash=None,
            rotated_at=None,
            last_used_at=None
        )
        
        self.session.add(agent_token)
        try:
            if commit:
                await self.session.commit()
                await self.session.refresh(agent_token)
            else:
                await self.session.flush()
            logger.info(f"[AuthTokensRepo] Created agent token: device_id={device_id}, prefix={token_prefix}")
            return token, agent_token
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"[AuthTokensRepo] Failed to create agent token: {e}")
            raise

    async def revoke_active_agent_tokens_for_device(
        self,
        device_id: str,
        *,
        except_token_hash: Optional[str] = None,
        replaced_by_token_hash: Optional[str] = None,
        commit: bool = True,
    ) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(AgentToken)
            .where(AgentToken.device_id == device_id)
            .where(AgentToken.revoked_at.is_(None))
        )
        if except_token_hash:
            stmt = stmt.where(AgentToken.token_hash != except_token_hash)
        values = {"revoked_at": now}
        if replaced_by_token_hash:
            values.update({"replaced_by_token_hash": replaced_by_token_hash, "rotated_at": now})
        result = await self.session.execute(stmt.values(**values))
        if commit:
            await self.session.commit()
        count = int(result.rowcount or 0)
        if count:
            logger.info(f"[AuthTokensRepo] Revoked {count} old active agent token(s): device_id={device_id}")
        return count
    
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
    
    async def verify_agent_token(self, token: str) -> Optional[AgentToken]:
        """
        Verify agent token by hash lookup.
        
        Args:
            token: Raw token string
            
        Returns:
            AgentToken if valid, None otherwise
            
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
        
        stmt = select(AgentToken).where(
            AgentToken.token_hash == token_hash
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
        stmt = select(TicketPublicSession).where(TicketPublicSession.token_hash == token_hash)
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
    
    async def revoke_agent_token(self, token: str) -> bool:
        """
        Revoke agent token.
        
        Args:
            token: Raw token string
            
        Returns:
            True if token was revoked, False if not found
        """
        token_hash = self.hash_token(token)
        
        stmt = (
            update(AgentToken)
            .where(AgentToken.token_hash == token_hash)
            .where(AgentToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        if result.rowcount > 0:
            logger.info(f"[AuthTokensRepo] Revoked agent token: prefix={self.get_token_prefix(token)}")
            return True
        return False
    
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
    
    async def rotate_agent_token(
        self,
        old_token: str,
        new_token: str,
        device_id: str,
        expires_at: Optional[datetime] = None
    ) -> Tuple[str, AgentToken]:
        """
        Rotate agent token (create new, mark old as replaced).
        
        Args:
            old_token: Old token to replace
            new_token: New token to create
            device_id: Device identifier
            expires_at: Optional expiration time for new token
            
        Returns:
            Tuple of (new_raw_token, new AgentToken record)
        """
        old_token_hash = self.hash_token(old_token)
        new_token_hash = self.hash_token(new_token)
        
        # Mark old token as replaced
        stmt = (
            update(AgentToken)
            .where(AgentToken.token_hash == old_token_hash)
            .where(AgentToken.revoked_at.is_(None))
            .values(
                replaced_by_token_hash=new_token_hash,
                rotated_at=datetime.now(timezone.utc)
            )
        )
        await self.session.execute(stmt)
        
        # Create new token
        _, new_token_record = await self.create_agent_token(
            new_token,
            device_id,
            expires_at,
            replace_existing=False,
            max_active_tokens=None,
        )
        
        await self.session.commit()
        logger.info(f"[AuthTokensRepo] Rotated agent token: device_id={device_id}")
        
        return new_token, new_token_record
    
    async def check_active_token_limit(self, device_id: str) -> int:
        """
        Check number of active tokens for device_id.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Number of active (not revoked) tokens
        """
        stmt = (
            select(func.count(AgentToken.token_hash))
            .where(AgentToken.device_id == device_id)
            .where(AgentToken.revoked_at.is_(None))
            .where(AgentToken.replaced_by_token_hash.is_(None))
            .where((AgentToken.expires_at.is_(None)) | (AgentToken.expires_at > datetime.now(timezone.utc)))
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Cleanup expired tokens (mark as revoked).
        
        Returns:
            Number of tokens cleaned up
        """
        now = datetime.now(timezone.utc)
        
        # Cleanup expired agent tokens
        stmt_agent = (
            update(AgentToken)
            .where(AgentToken.expires_at < now)
            .where(AgentToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result_agent = await self.session.execute(stmt_agent)
        agent_count = result_agent.rowcount
        
        # Cleanup expired UI tokens
        stmt_ui = (
            update(UiToken)
            .where(UiToken.expires_at < now)
            .where(UiToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result_ui = await self.session.execute(stmt_ui)
        ui_count = result_ui.rowcount
        
        await self.session.commit()
        
        total = agent_count + ui_count
        if total > 0:
            logger.info(f"[AuthTokensRepo] Cleaned up {total} expired tokens (agent: {agent_count}, ui: {ui_count})")
        
        return total
    
    async def get_agent_token_by_device(self, device_id: str) -> Optional[AgentToken]:
        """
        Get active agent token for device_id.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Active AgentToken or None
        """
        stmt = (
            select(AgentToken)
            .where(AgentToken.device_id == device_id)
            .where(AgentToken.revoked_at.is_(None))
            .order_by(AgentToken.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
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
    
    async def get_agent_tokens_by_device(self, device_id: str) -> List[AgentToken]:
        """
        Get all agent tokens for device_id (including revoked).
        
        Args:
            device_id: Device identifier
            
        Returns:
            List of AgentToken objects ordered by created_at desc
        """
        stmt = (
            select(AgentToken)
            .where(AgentToken.device_id == device_id)
            .order_by(AgentToken.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def rebind_agent_token(self, token_hash: str, new_device_id: str) -> bool:
        """
        Rebind active token to another device_id.

        Used only in controlled reprovision scenarios when an existing agent
        receives a fresh token that was issued for a never-seen device_id.
        """
        stmt = (
            update(AgentToken)
            .where(AgentToken.token_hash == token_hash)
            .where(AgentToken.revoked_at.is_(None))
            .values(device_id=new_device_id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        if result.rowcount > 0:
            logger.warning(
                f"[AuthTokensRepo] Rebound agent token {token_hash[:16]}... "
                f"to device_id={new_device_id}"
            )
            return True
        return False
    
    async def revoke_agent_token_by_hash(self, token_hash: str, *, device_id: str) -> bool:
        """
        Revoke agent token by hash.
        
        Args:
            token_hash: Token hash (SHA256)
            
        Returns:
            True if token was revoked, False if not found or already revoked
        """
        stmt = (
            update(AgentToken)
            .where(AgentToken.token_hash == token_hash)
            .where(AgentToken.device_id == device_id)
            .where(AgentToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        if result.rowcount > 0:
            logger.info(f"[AuthTokensRepo] Revoked agent token by hash: device_id={device_id}, hash_prefix={token_hash[:12]}")
            return True
        return False
