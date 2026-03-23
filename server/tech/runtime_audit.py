"""Best-effort runtime audit writer for agent lifecycle events."""
from typing import Optional

from loguru import logger

from app.db import get_session
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo


async def write_agent_runtime_audit(
    *,
    device_id: str,
    event_type: str,
    severity: str = "info",
    source: str = "server",
    operation_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    details_json: Optional[dict] = None,
) -> None:
    """Persist runtime audit record; never breaks business flow on failure."""
    try:
        async with get_session() as session:
            repo = AgentRuntimeAuditRepo(session)
            await repo.add(
                device_id=device_id,
                event_type=event_type,
                severity=severity,
                source=source,
                operation_id=operation_id,
                ticket_id=ticket_id,
                actor_id=actor_id,
                actor_role=actor_role,
                details_json=details_json or {},
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            f"[runtime_audit] failed to write event={event_type} device_id={device_id}: {exc}"
        )
