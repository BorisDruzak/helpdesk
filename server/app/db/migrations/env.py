"""
Alembic migration environment configuration.

This file configures Alembic to work with async SQLAlchemy and PostgreSQL.
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import the Base to ensure all models are loaded
from app.db.base import Base
# Import all models to register them with Base.metadata
from app.db.models import (  # noqa: F401 - Import to register models
    JobEvent,
    Ticket,
    TicketEvent,
    TicketWait,
    Problem,
    ProblemTicketLink,
    TicketAdminAudit,
    TicketChangeLink,
    TicketQueue,
    TicketQueueOlaTarget,
    TicketBusinessCalendar,
    TicketCategory,
    TicketSlaPolicy,
    TicketSlaTarget,
    TicketPriorityMatrix,
    TicketRoutingRule,
    TicketQueueMember,
    TicketWatcher,
    TicketLink,
    TicketResolutionCode,
    TicketKbLink,
    TicketWorklog,
    TicketNotification,
    TicketNotificationPref,
    DeviceEvent,
    Device,
    DeviceConfig,
    DeviceToolsetSnapshot,
    RemoteAccessSession,
    RemoteAccessEvent,
    Operation,
    Module,
    DeviceModule,
    UiToken,
    UiUser,
    UiUserAudit,
    AuthSession,
    ConsentDecision,
    DownloadAudit,
    Artifact,
    Playbook,
    PlaybookVersion,
    PlaybookStep,
    PlaybookRun,
    PlaybookStepRun,
    DeviceDesiredModule,
)

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Read DATABASE_URL from environment
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with a database connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using async engine.
    
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Get the Alembic config and create an async engine
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    """
    asyncio.run(run_async_migrations())


# Determine which mode to run
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
