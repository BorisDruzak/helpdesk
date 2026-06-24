"""OBS1 Operational Integrity Observer orchestration."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
from observer.checks.types import ObserverIntegrityCheckResult
from observer.checks.web_cabinet import SOURCE as WEB_CABINET_SOURCE
from observer.checks.web_cabinet import check_web_cabinet


KNOWN_CONTAMINATION_MANIFEST = Path(__file__).resolve().parents[2] / "quality" / "observer_known_contamination.json"
INTEGRITY_RUNNER_SOURCE = "observer.integrity_runner"


def _parse_manifest_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _manifest_notes(item: dict[str, Any]) -> str | None:
    notes = str(item.get("notes") or "").strip()
    review = " ".join(
        part
        for part in (
            f"owner={item.get('owner_zone')}" if item.get("owner_zone") else "",
            f"issue={item.get('linked_issue')}" if item.get("linked_issue") else "",
            f"review={item.get('review_status')}" if item.get("review_status") else "",
            f"evidence={item.get('evidence_path')}" if item.get("evidence_path") else "",
        )
        if part
    )
    if notes and review:
        return f"{notes} {review}"
    return notes or review or None


def load_known_contamination_manifest(path: Path = KNOWN_CONTAMINATION_MANIFEST) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("contaminations") if isinstance(payload.get("contaminations"), list) else []:
        if not isinstance(item, dict) or item.get("status") != "active":
            continue
        expires_at = _parse_manifest_datetime(item.get("expires_at"))
        if expires_at is None:
            continue
        rows.append(
            {
                "source_phase": item.get("source_phase"),
                "entity_type": item.get("entity_type"),
                "entity_id": item.get("entity_id"),
                "suppression_scope": item.get("suppression_scope") or "observer_integrity",
                "reason": item.get("reason"),
                "notes": _manifest_notes(item),
                "active": True,
                "expires_at": expires_at,
            }
        )
    return rows


DEFAULT_KNOWN_CONTAMINATION: list[dict[str, Any]] = load_known_contamination_manifest()


@dataclass(slots=True)
class ObserverIntegrityScanResult:
    run_id: str | None
    generated: int
    active: int
    suppressed: int
    resolved: int
    incomplete_sources: list[str]
    failed_sources: list[str]
    event_ids: list[str]


class ObserverIntegrityService:
    def __init__(self, session: AsyncSession, *, state: Any = None) -> None:
        self.session = session
        self.state = state
        self.repo = ObserverIntegrityRepo(session)

    async def seed_known_contamination(self) -> int:
        return await self.repo.ensure_contamination(rows=load_known_contamination_manifest())

    async def run_scan(self, *, run_id: str | None = None) -> ObserverIntegrityScanResult:
        await self.seed_known_contamination()
        generated: list[ObserverIntegrityEventInput] = []
        source_complete: dict[str, bool] = {}
        failed_sources: list[str] = []

        def collect(result: list[ObserverIntegrityEventInput] | ObserverIntegrityCheckResult) -> None:
            if isinstance(result, ObserverIntegrityCheckResult):
                source_complete[result.source] = source_complete.get(result.source, True) and result.complete
                generated.extend(result.events)
                return
            generated.extend(result)

        async def collect_checker(source: str, checker_call: Any) -> None:
            try:
                collect(await checker_call())
            except Exception as exc:
                source_complete[source] = False
                failed_sources.append(source)
                generated.append(
                    ObserverIntegrityEventInput(
                        event_type="observer_integrity_checker_failed",
                        severity="error",
                        source=INTEGRITY_RUNNER_SOURCE,
                        dedupe_key=f"observer_integrity_checker_failed:{source}",
                        expected="Observer integrity checker should complete without blocking independent checkers.",
                        actual=f"{type(exc).__name__}: {str(exc)[:300]}",
                        evidence={
                            "checker_source": source,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                        },
                        runbook="docs/runbooks/observer_integrity.md",
                        run_id=run_id,
                    )
                )

        await collect_checker(OPERATION_SOURCE, lambda: check_operation_lifecycle(self.session, run_id=run_id))
        await collect_checker(PROTOCOL_SOURCE, lambda: check_protocol_integrity(self.session, run_id=run_id))
        await collect_checker(RUNTIME_SOURCE, lambda: check_runtime_presence(self.session, state=self.state, run_id=run_id))
        await collect_checker(ACCOUNT_SOURCE, lambda: check_account_boundary(self.session, run_id=run_id))
        await collect_checker(MODULE_TOOLSET_SOURCE, lambda: check_module_toolset(self.session, run_id=run_id))
        await collect_checker(GOVERNANCE_SOURCE, lambda: check_governance(self.session, run_id=run_id))
        await collect_checker(WEB_CABINET_SOURCE, lambda: check_web_cabinet(self.session, run_id=run_id))

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
            INTEGRITY_RUNNER_SOURCE,
        ):
            if source_complete.get(source, True) is False:
                continue
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
            incomplete_sources=sorted(source for source, complete in source_complete.items() if not complete),
            failed_sources=sorted(failed_sources),
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
