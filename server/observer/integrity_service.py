"""OBS1 Operational Integrity Observer orchestration."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.observer_integrity_repo import (
    ObserverIntegrityEventInput,
    ObserverIntegrityRepo,
    serialize_observer_integrity_event,
)
from domain_ports import DomainPortContainer, RegistryPort
from observer.checks.account_boundary import check_account_boundary
from observer.checks.account_boundary import SOURCE as ACCOUNT_SOURCE
from observer.checks.governance import SOURCE as GOVERNANCE_SOURCE
from observer.checks.governance import check_governance
from observer.checks.operation_lifecycle import SOURCE as OPERATION_SOURCE
from observer.checks.operation_lifecycle import check_operation_lifecycle
from observer.checks.types import ObserverIntegrityCheckResult
from observer.checks.web_cabinet import SOURCE as WEB_CABINET_SOURCE
from observer.checks.web_cabinet import check_web_cabinet


KNOWN_CONTAMINATION_MANIFEST = Path(__file__).resolve().parents[2] / "quality" / "observer_known_contamination.json"
INTEGRITY_RUNNER_SOURCE = "observer.integrity_runner"
DEFAULT_CHECKER_TIMEOUT_SECONDS = 30.0


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
class ObserverIntegrityCheckReport:
    source: str
    status: str
    complete: bool
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    generated_count: int = 0
    active_count: int = 0
    suppressed_count: int = 0
    resolved_count: int = 0
    scanned_count: int = 0
    limit: int | None = None
    window: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ObserverIntegrityScanResult:
    scan_id: str
    run_id: str | None
    status: str
    generated: int
    active: int
    suppressed: int
    resolved: int
    incomplete_sources: list[str]
    failed_sources: list[str]
    event_ids: list[str]
    checks: list[ObserverIntegrityCheckReport]
    duration_ms: int


def serialize_observer_integrity_check_report(report: ObserverIntegrityCheckReport) -> dict[str, Any]:
    return {
        "source": report.source,
        "status": report.status,
        "complete": report.complete,
        "started_at": report.started_at.isoformat(),
        "finished_at": report.finished_at.isoformat(),
        "duration_ms": report.duration_ms,
        "generated_count": report.generated_count,
        "active_count": report.active_count,
        "suppressed_count": report.suppressed_count,
        "resolved_count": report.resolved_count,
        "scanned_count": report.scanned_count,
        "limit": report.limit,
        "window": report.window,
        "error_type": report.error_type,
        "error_message": report.error_message,
    }


class ObserverIntegrityService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        state: Any = None,
        registry_port: RegistryPort | None = None,
        checker_timeout_seconds: float = DEFAULT_CHECKER_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session
        self.state = state
        self.registry_port = registry_port or DomainPortContainer.from_config(registry_session=session).registry
        self.checker_timeout_seconds = max(float(checker_timeout_seconds), 0.001)
        self.repo = ObserverIntegrityRepo(session)

    async def seed_known_contamination(self) -> int:
        return await self.repo.ensure_contamination(rows=load_known_contamination_manifest())

    async def run_scan(self, *, run_id: str | None = None) -> ObserverIntegrityScanResult:
        scan_id = str(uuid.uuid4())
        scan_started_monotonic = time.perf_counter()
        await self.seed_known_contamination()
        generated: list[ObserverIntegrityEventInput] = []
        source_complete: dict[str, bool] = {INTEGRITY_RUNNER_SOURCE: True}
        failed_sources: list[str] = []
        check_reports: list[ObserverIntegrityCheckReport] = []

        def collect(source: str, result: Any, *, started_at: datetime, finished_at: datetime, duration_ms: int) -> ObserverIntegrityCheckReport:
            if isinstance(result, ObserverIntegrityCheckResult):
                generated.extend(result.events)
                window = {
                    "scanned_count": result.scanned_count,
                    "limit": result.limit,
                    "complete": result.complete,
                }
                if result.source != source:
                    source_complete[source] = False
                    source_complete[result.source] = False
                    return ObserverIntegrityCheckReport(
                        source=source,
                        status="degraded",
                        complete=False,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        generated_count=len(result.events),
                        scanned_count=result.scanned_count,
                        limit=result.limit,
                        window=window | {"reported_source": result.source},
                        error_type="SourceMismatch",
                        error_message=f"checker returned source {result.source!r}",
                    )
                else:
                    complete = bool(result.complete)
                    source_complete[result.source] = complete
                    return ObserverIntegrityCheckReport(
                        source=source,
                        status="passed" if complete else "degraded",
                        complete=complete,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        generated_count=len(result.events),
                        scanned_count=result.scanned_count,
                        limit=result.limit,
                        window=window,
                    )
            source_complete[source] = False
            if isinstance(result, list):
                generated.extend(result)
                return ObserverIntegrityCheckReport(
                    source=source,
                    status="degraded",
                    complete=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    generated_count=len(result),
                    scanned_count=len(result),
                    window={"legacy_result": True},
                    error_type="LegacyListResult",
                    error_message="checker returned a legacy list without explicit complete coverage",
                )
            raise TypeError(
                f"Observer integrity checker {source} returned unsupported result type {type(result).__name__}"
            )

        async def run_checker(checker_call: Any) -> Any:
            begin_nested = getattr(self.session, "begin_nested", None)
            if begin_nested is None:
                return await checker_call()
            async with begin_nested():
                return await checker_call()

        def failure_report(
            source: str,
            *,
            status: str,
            exc: BaseException,
            started_at: datetime,
            finished_at: datetime,
            duration_ms: int,
        ) -> ObserverIntegrityCheckReport:
            message = str(exc)[:300]
            if not message and status == "timed_out":
                message = f"checker exceeded {self.checker_timeout_seconds:g}s"
            return ObserverIntegrityCheckReport(
                source=source,
                status=status,
                complete=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_message=message,
            )

        def append_failure_event(source: str, exc: BaseException, *, status: str) -> None:
            message = str(exc)[:300]
            if not message and status == "timed_out":
                message = f"checker exceeded {self.checker_timeout_seconds:g}s"
            generated.append(
                ObserverIntegrityEventInput(
                    event_type="observer_integrity_checker_failed",
                    severity="error",
                    source=INTEGRITY_RUNNER_SOURCE,
                    dedupe_key=f"observer_integrity_checker_failed:{source}",
                    expected="Observer integrity checker should complete without blocking independent checkers.",
                    actual=f"{type(exc).__name__}: {message}",
                    evidence={
                        "checker_source": source,
                        "checker_status": status,
                        "error_type": type(exc).__name__,
                        "error_message": message,
                    },
                    runbook="docs/runbooks/observer_integrity.md",
                    run_id=run_id,
                )
            )

        async def collect_checker(source: str, checker_call: Any) -> None:
            has_savepoint = getattr(self.session, "begin_nested", None) is not None
            started_at = datetime.now(timezone.utc)
            started_monotonic = time.perf_counter()
            try:
                result = await asyncio.wait_for(run_checker(checker_call), timeout=self.checker_timeout_seconds)
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started_monotonic) * 1000)
                check_reports.append(
                    collect(
                        source,
                        result,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                    )
                )
            except asyncio.TimeoutError as exc:
                source_complete[source] = False
                if source not in failed_sources:
                    failed_sources.append(source)
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started_monotonic) * 1000)
                check_reports.append(
                    failure_report(
                        source,
                        status="timed_out",
                        exc=exc,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                    )
                )
                if not has_savepoint:
                    with suppress(Exception):
                        rollback = getattr(self.session, "rollback", None)
                        if rollback is not None:
                            await rollback()
                append_failure_event(source, exc, status="timed_out")
            except Exception as exc:
                source_complete[source] = False
                if source not in failed_sources:
                    failed_sources.append(source)
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started_monotonic) * 1000)
                check_reports.append(
                    failure_report(
                        source,
                        status="failed",
                        exc=exc,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                    )
                )
                if not has_savepoint:
                    with suppress(Exception):
                        rollback = getattr(self.session, "rollback", None)
                        if rollback is not None:
                            await rollback()
                append_failure_event(source, exc, status="failed")

        await collect_checker(OPERATION_SOURCE, lambda: check_operation_lifecycle(self.session, run_id=run_id))
        await collect_checker(ACCOUNT_SOURCE, lambda: check_account_boundary(self.session, run_id=run_id))
        await collect_checker(GOVERNANCE_SOURCE, lambda: check_governance(self.session, run_id=run_id))
        await collect_checker(
            WEB_CABINET_SOURCE,
            lambda: check_web_cabinet(self.session, registry_port=self.registry_port, run_id=run_id),
        )

        active_dedupe_by_source: dict[str, set[str]] = {}
        reports_by_source = {report.source: report for report in check_reports}
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
            report = reports_by_source.get(event.source)
            if row.status == "suppressed":
                suppressed += 1
                if report is not None:
                    report.suppressed_count += 1
            else:
                active += 1
                if report is not None:
                    report.active_count += 1

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
            report = reports_by_source.get(source)
            if source == INTEGRITY_RUNNER_SOURCE:
                if source_complete.get(source) is not True:
                    continue
            elif report is None or report.status != "passed" or report.complete is not True:
                continue
            resolved_count = await self.repo.resolve_missing(
                source=source,
                active_dedupe_keys=active_dedupe_by_source.get(source, set()),
                run_id=run_id,
            )
            resolved += resolved_count
            if report is not None:
                report.resolved_count += resolved_count
        await self.repo.record_check_reports(
            scan_id=scan_id,
            run_id=run_id,
            reports=[serialize_observer_integrity_check_report(report) for report in check_reports],
        )
        await self.session.flush()
        scan_duration_ms = int((time.perf_counter() - scan_started_monotonic) * 1000)
        scan_status = (
            "passed"
            if check_reports and all(report.status == "passed" and report.complete for report in check_reports)
            else "degraded"
        )
        return ObserverIntegrityScanResult(
            scan_id=scan_id,
            run_id=run_id,
            status=scan_status,
            generated=len(generated),
            active=active,
            suppressed=suppressed,
            resolved=resolved,
            incomplete_sources=sorted(source for source, complete in source_complete.items() if not complete),
            failed_sources=sorted(failed_sources),
            event_ids=event_ids,
            checks=check_reports,
            duration_ms=scan_duration_ms,
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
