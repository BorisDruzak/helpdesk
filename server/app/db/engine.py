"""
Async SQLAlchemy engine and session management.
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from loguru import logger

from app.db.base import Base

# Global engine and session maker
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    Returns the global async engine instance.
    
    Raises:
        RuntimeError: If engine is not initialized
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Returns the global session maker.
    
    Raises:
        RuntimeError: If session maker is not initialized
    """
    if _session_maker is None:
        raise RuntimeError("Session maker not initialized. Call init_db() first.")
    return _session_maker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Usage:
        async with get_session() as session:
            # Use session here
            pass
    
    Yields:
        AsyncSession: Database session
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Гарантированно возвращаем соединение в пул (предотвращает SAWarning о non-checked-in connection)
            await session.close()


async def init_db(database_url: Optional[str] = None) -> None:
    """
    Initialize the database engine and session maker.
    
    Args:
        database_url: Database URL. If None, reads from DATABASE_URL env var.
    
    Raises:
        ValueError: If database_url is not provided and DATABASE_URL env var is not set
    """
    global _engine, _session_maker
    
    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        raise ValueError(
            "DATABASE_URL not provided. "
            "Set DATABASE_URL environment variable or pass database_url parameter."
        )
    
    logger.info(f"🗄️  Initializing database connection...")
    logger.debug(f"Database URL: {database_url.split('@')[-1] if '@' in database_url else 'local'}")
    
    # Create async engine
    _engine = create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
    )
    
    # Create session maker
    _session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    # Test connectivity with a simple query
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        logger.success("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise


async def shutdown_db() -> None:
    """
    Dispose of the database engine and clean up resources.
    """
    global _engine, _session_maker
    
    if _engine is not None:
        logger.info("🗄️  Closing database connections...")
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.success("✅ Database connections closed")


