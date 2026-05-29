"""OBS1 account-session/public-requester mutation boundary checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRuntimeAudit
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


SOURCE = "observer.account_boundary"
BOUNDARY_AUDIT_EVENTS = {
    "account_boundary_mutation_success",
    "public_boundary_mutation_success",
    "requester_projection_forbidden_field",
}


async def check_account_boundary(
    session: AsyncSession,
    *,
    run_id: str | None = None,
    lookback: timedelta = timedelta(hours=24),
) -> list[ObserverIntegrityEventInput]:
    cutoff = datetime.now(timezone.utc) - lookback
    rows = (
        await session.execute(
            select(AgentRuntimeAudit)
            .where(AgentRuntimeAudit.event_type.in_(BOUNDARY_AUDIT_EVENTS), AgentRuntimeAudit.created_at >= cutoff)
            .order_by(AgentRuntimeAudit.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    events: list[ObserverIntegrityEventInput] = []
    for row in rows:
        details = row.details_json if isinstance(row.details_json, dict) else {}
        mutation_kind = str(details.get("mutation_kind") or row.event_type)
        target_id = str(details.get("ticket_id") or details.get("target_id") or row.ticket_id or "unknown")
        events.append(
            ObserverIntegrityEventInput(
                event_type=row.event_type,
                severity="critical",
                source=SOURCE,
                dedupe_key=f"{row.event_type}:{target_id}:{row.actor_role or 'unknown'}",
                device_id=row.device_id,
                ticket_id=str(details.get("ticket_id") or row.ticket_id or "") or None,
                operation_id=row.operation_id,
                actor_role=row.actor_role,
                expected="Requester/public mutations must only succeed with valid account-session/public authorization and safe projection fields.",
                actual=f"Boundary anomaly audit event recorded: {mutation_kind}",
                evidence={
                    "audit_id": row.id,
                    "audit_event_type": row.event_type,
                    "mutation_kind": mutation_kind,
                    "target_id": target_id,
                    "actor_role": row.actor_role,
                    "boundary_state": details.get("auth_state") or details.get("boundary_state"),
                    "forbidden_field": details.get("forbidden_field"),
                },
                runbook="docs/runbooks/observer_account_boundary.md",
                run_id=run_id,
            )
        )
    return events
