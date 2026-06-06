from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.schemas import controlled_error, ok


async def helpdesk_db_health(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        import config

        start = time.perf_counter()
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            await session.rollback()
        return ok(
            {
                "database": _database_name(config.DATABASE_URL),
                "reachable": True,
                "latency_ms": latency_ms,
                "error": None,
            }
        )
    except Exception:
        payload = controlled_error("DB_UNAVAILABLE", "Database connection failed", redacted=True)
        payload["reachable"] = False
        return payload


def _database_name(database_url: str) -> str | None:
    raw = str(database_url or "").strip()
    if not raw:
        return None
    tail = raw.rsplit("/", 1)[-1]
    return tail.split("?", 1)[0] or None
