"""
Stage 12: Retention/Archive — перемещение старых ticket_events и ticket_admin_audit в archive-таблицы.

Политики: ticket_events hot 180 дней, ticket_admin_audit hot 365 дней.
Запуск: по расписанию (cron/ежедневно). В dry_run только подсчёт без переноса.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from config import (
    TICKET_RETENTION_ENABLED,
    TICKET_EVENTS_HOT_RETENTION_DAYS,
    TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS,
    TICKET_RETENTION_BATCH_SIZE,
    TICKET_RETENTION_MAX_BATCHES_PER_RUN,
    TICKET_RETENTION_DRY_RUN,
)


async def run_retention(session: AsyncSession) -> dict:
    """
    Один прогон retention: перенос старых записей в archive.
    Returns: { "status": "ok"|"error", "moved_events": int, "moved_audit": int, "error": str? }
    """
    started_at = datetime.now(timezone.utc)
    if not TICKET_RETENTION_ENABLED:
        return {"status": "ok", "moved_events": 0, "moved_audit": 0, "started_at": started_at}
    cutoff_events = started_at - timedelta(days=TICKET_EVENTS_HOT_RETENTION_DAYS)
    cutoff_audit = started_at - timedelta(days=TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS)
    moved_events = 0
    moved_audit = 0
    try:
        for _ in range(TICKET_RETENTION_MAX_BATCHES_PER_RUN):
            if TICKET_RETENTION_DRY_RUN:
                r = await session.execute(
                    text("SELECT COUNT(*) FROM ticket_events WHERE created_at < :cutoff"),
                    {"cutoff": cutoff_events},
                )
                count = r.scalar() or 0
                to_move = min(count, TICKET_RETENTION_BATCH_SIZE)
                if to_move == 0:
                    break
                moved_events += to_move
                break
            # DELETE RETURNING + INSERT в archive одним запросом
            r = await session.execute(
                text("""
                    WITH to_del AS (
                        SELECT id FROM ticket_events
                        WHERE created_at < :cutoff
                        ORDER BY id
                        LIMIT :batch_size
                    ),
                    deleted AS (
                        DELETE FROM ticket_events WHERE id IN (SELECT id FROM to_del)
                        RETURNING id, ticket_id, device_id, agent_seq, event_type, payload, trace_id, event_id, operation_id, created_at
                    )
                    INSERT INTO ticket_events_archive
                    (id, ticket_id, device_id, agent_seq, event_type, payload, trace_id, event_id, operation_id, created_at)
                    SELECT id, ticket_id, device_id, agent_seq, event_type, payload, trace_id, event_id, operation_id, created_at
                    FROM deleted
                """),
                {"cutoff": cutoff_events, "batch_size": TICKET_RETENTION_BATCH_SIZE},
            )
            moved_events += r.rowcount
            if r.rowcount < TICKET_RETENTION_BATCH_SIZE:
                break

        for _ in range(TICKET_RETENTION_MAX_BATCHES_PER_RUN):
            if TICKET_RETENTION_DRY_RUN:
                r = await session.execute(
                    text("SELECT COUNT(*) FROM ticket_admin_audit WHERE created_at < :cutoff"),
                    {"cutoff": cutoff_audit},
                )
                count = r.scalar() or 0
                to_move = min(count, TICKET_RETENTION_BATCH_SIZE)
                if to_move == 0:
                    break
                moved_audit += to_move
                break
            r = await session.execute(
                text("""
                    WITH to_del AS (
                        SELECT id FROM ticket_admin_audit
                        WHERE created_at < :cutoff
                        ORDER BY id
                        LIMIT :batch_size
                    ),
                    deleted AS (
                        DELETE FROM ticket_admin_audit WHERE id IN (SELECT id FROM to_del)
                        RETURNING id, entity_type, entity_id, action, actor_id, actor_role, before_json, after_json, trace_id, created_at
                    )
                    INSERT INTO ticket_admin_audit_archive
                    (id, entity_type, entity_id, action, actor_id, actor_role, before_json, after_json, trace_id, created_at)
                    SELECT id, entity_type, entity_id, action, actor_id, actor_role, before_json, after_json, trace_id, created_at
                    FROM deleted
                """),
                {"cutoff": cutoff_audit, "batch_size": TICKET_RETENTION_BATCH_SIZE},
            )
            moved_audit += r.rowcount
            if r.rowcount < TICKET_RETENTION_BATCH_SIZE:
                break

        if not TICKET_RETENTION_DRY_RUN:
            await session.commit()
        return {"status": "ok", "moved_events": moved_events, "moved_audit": moved_audit, "started_at": started_at}
    except Exception as e:
        await session.rollback()
        logger.exception(f"[Retention] error: {e}")
        return {"status": "error", "moved_events": moved_events, "moved_audit": moved_audit, "error": str(e), "started_at": started_at}


async def run_retention_and_record(get_session_fn):
    """
    Выполнить run_retention и записать результат в ticket_retention_runs.
    get_session_fn — async context manager, например app.db.get_session.
    Удобно вызывать из cron/планировщика.
    """
    async with get_session_fn() as session:
        result = await run_retention(session)
    finished_at = datetime.now(timezone.utc)
    started_at = result.get("started_at", finished_at)
    status = result.get("status", "ok")
    moved_events = result.get("moved_events", 0)
    moved_audit = result.get("moved_audit", 0)
    error = result.get("error")
    try:
        async with get_session_fn() as session:
            await record_retention_run(session, started_at, finished_at, status, moved_events, moved_audit, error)
    except Exception as e:
        logger.warning(f"[Retention] record_retention_run failed: {e}")
    return result


async def record_retention_run(
    session: AsyncSession,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    moved_events: int,
    moved_audit: int,
    error: Optional[str] = None,
) -> None:
    """Записать запись в ticket_retention_runs (таблица создаётся миграцией 030)."""
    await session.execute(
        text("""
            INSERT INTO ticket_retention_runs (started_at, finished_at, status, moved_events, moved_audit, error)
            VALUES (:started_at, :finished_at, :status, :moved_events, :moved_audit, :error)
        """),
        {
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "moved_events": moved_events,
            "moved_audit": moved_audit,
            "error": error,
        },
    )
    await session.commit()
