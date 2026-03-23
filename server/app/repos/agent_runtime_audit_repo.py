"""Repository for append-only agent_runtime_audit records."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRuntimeAudit


class AgentRuntimeAuditRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
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
    ) -> AgentRuntimeAudit:
        rec = AgentRuntimeAudit(
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            source=source,
            operation_id=operation_id,
            ticket_id=ticket_id,
            actor_id=actor_id,
            actor_role=actor_role,
            details_json=details_json,
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def list_feed(
        self,
        *,
        device_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        dt_from: Optional[datetime] = None,
        dt_to: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AgentRuntimeAudit]:
        stmt = select(AgentRuntimeAudit)
        if device_id:
            stmt = stmt.where(AgentRuntimeAudit.device_id == device_id)
        if event_type:
            stmt = stmt.where(AgentRuntimeAudit.event_type == event_type)
        if severity:
            stmt = stmt.where(AgentRuntimeAudit.severity == severity)
        if dt_from:
            stmt = stmt.where(AgentRuntimeAudit.created_at >= dt_from)
        if dt_to:
            stmt = stmt.where(AgentRuntimeAudit.created_at <= dt_to)
        stmt = stmt.order_by(AgentRuntimeAudit.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
