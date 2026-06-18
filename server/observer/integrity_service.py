"""OBS1 Operational Integrity Observer orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.observer_integrity_repo import (
    ObserverIntegrityEventInput,
    ObserverIntegrityRepo,
    serialize_observer_integrity_event,
)
from observer.checks.account_boundary import check_account_boundary
from observer.checks.account_boundary import SOURCE as ACCOUNT_SOURCE
from observer.checks.governance import SOURCE as GOVERNANCE_SOURCE
from observer.checks.governance import check_governance
from observer.checks.module_toolset import SOURCE as MODULE_TOOLSET_SOURCE
from observer.checks.module_toolset import check_module_toolset
from observer.checks.operation_lifecycle import SOURCE as OPERATION_SOURCE
from observer.checks.operation_lifecycle import check_operation_lifecycle
from observer.checks.protocol_integrity import SOURCE as PROTOCOL_SOURCE
from observer.checks.protocol_integrity import check_protocol_integrity
from observer.checks.runtime_presence import SOURCE as RUNTIME_SOURCE
from observer.checks.runtime_presence import check_runtime_presence
from observer.checks.web_cabinet import SOURCE as WEB_CABINET_SOURCE
from observer.checks.web_cabinet import check_web_cabinet


DEFAULT_KNOWN_CONTAMINATION: list[dict[str, Any]] = [
    {
        "source_phase": "P1",
        "entity_type": "device_outbox",
        "entity_id": "135",
        "reason": "Historical P1 malformed/reconnect probe contamination; not current OBS1 evidence.",
        "notes": "Narrow suppression for device_outbox.id=135 only.",
    },
    {
        "source_phase": "P0",
        "entity_type": "dedupe_key",
        "entity_id": "p0:phantom_malformed_rows",
        "reason": "Historical P0 phantom/malformed rows listed in PLANS.md.",
    },
    {
        "source_phase": "P6",
        "entity_type": "dedupe_key",
        "entity_id": "p6:historical_non_p6_agent_offline_active",
        "reason": "Historical non-P6 agent_offline_active tasks are excluded from OBS1 current baseline.",
    },
]


@dataclass(slots=True)
class ObserverIntegrityScanResult:
    run_id: str | None
    generated: int
    active: int
    suppressed: int
    resolved: int
    event_ids: list[str]


class ObserverIntegrityService:
    def __init__(self, session: AsyncSession, *, state: Any = None) -> None:
        self.session = session
        self.state = state
        self.repo = ObserverIntegrityRepo(session)

    async def seed_known_contamination(self) -> int:
        return await self.repo.ensure_contamination(rows=DEFAULT_KNOWN_CONTAMINATION)

    async def run_scan(self, *, run_id: str | None = None) -> ObserverIntegrityScanResult:
        await self.seed_known_contamination()
        generated: list[ObserverIntegrityEventInput] = []
        generated.extend(await check_operation_lifecycle(self.session, run_id=run_id))
        generated.extend(await check_protocol_integrity(self.session, run_id=run_id))
        generated.extend(await check_runtime_presence(self.session, state=self.state, run_id=run_id))
        generated.extend(await check_account_boundary(self.session, run_id=run_id))
        generated.extend(await check_module_toolset(self.session, run_id=run_id))
        generated.extend(await check_governance(self.session, run_id=run_id))
        generated.extend(await check_web_cabinet(self.session, run_id=run_id))

        active_dedupe_by_source: dict[str, set[str]] = {}
        event_ids: list[str] = []
        active = 0
        suppressed = 0
        for event in generated:
            active_dedupe_by_source.setdefault(event.source, set()).add(event.dedupe_key)
            contamination = await self.repo.find_contamination(event)
            suppression_reason = None
            if contamination is not None:
                suppression_reason = f"{contamination.source_phase}: {contamination.reason}"
            row = await self.repo.upsert_event(event, suppression_reason=suppression_reason)
            event_ids.append(row.event_id)
            if row.status == "suppressed":
                suppressed += 1
            else:
                active += 1

        resolved = 0
        for source in (
            OPERATION_SOURCE,
            PROTOCOL_SOURCE,
            RUNTIME_SOURCE,
            ACCOUNT_SOURCE,
            MODULE_TOOLSET_SOURCE,
            GOVERNANCE_SOURCE,
            WEB_CABINET_SOURCE,
        ):
            resolved += await self.repo.resolve_missing(
                source=source,
                active_dedupe_keys=active_dedupe_by_source.get(source, set()),
                run_id=run_id,
            )
        await self.session.flush()
        return ObserverIntegrityScanResult(
            run_id=run_id,
            generated=len(generated),
            active=active,
            suppressed=suppressed,
            resolved=resolved,
            event_ids=event_ids,
        )

    async def list_events(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        device_id: str | None = None,
        ticket_id: str | None = None,
        operation_id: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = await self.repo.list_events(
            severity=severity,
            status=status,
            device_id=device_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            event_type=event_type,
            source=source,
            since=since,
            limit=limit,
        )
        summary = await self.repo.summary()
        return {
            "summary": summary,
            "items": [serialize_observer_integrity_event(row) for row in rows],
        }
