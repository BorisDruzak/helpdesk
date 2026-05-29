"""OBS1 Protocol V3 ACK/persistence integrity checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRuntimeAudit
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


SOURCE = "observer.protocol_integrity"
ACK_AUDIT_EVENTS = {"outbox_ack_emitted", "outbox_ack_persisted", "protocol_ack_persisted"}
NACK_CODES = {"UNKNOWN_TICKET", "DEVICE_MISMATCH", "VALIDATION_ERROR"}


async def check_protocol_integrity(
    session: AsyncSession,
    *,
    run_id: str | None = None,
    lookback: timedelta = timedelta(hours=24),
    nack_threshold: int = 5,
) -> list[ObserverIntegrityEventInput]:
    now = datetime.now(timezone.utc)
    cutoff = now - lookback
    events: list[ObserverIntegrityEventInput] = []

    ack_audits = (
        await session.execute(
            select(AgentRuntimeAudit)
            .where(AgentRuntimeAudit.event_type.in_(ACK_AUDIT_EVENTS), AgentRuntimeAudit.created_at >= cutoff)
            .order_by(AgentRuntimeAudit.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    ack_contract_v2 = [
        row
        for row in ack_audits
        if isinstance(row.details_json, dict) and int(row.details_json.get("audit_contract_version") or 0) >= 2
    ]
    if not ack_contract_v2:
        events.append(
            ObserverIntegrityEventInput(
                event_type="protocol_ack_audit_gap",
                severity="warning",
                source=SOURCE,
                dedupe_key="protocol_ack_audit_gap:global",
                expected="Protocol V3 ACK emission should have durable v2 persistence audit for ACK/persistence correlation.",
                actual=(
                    f"No v2 ACK persistence audit event was found in the last "
                    f"{int(lookback.total_seconds() // 3600)} hours."
                ),
                evidence={
                    "lookback_seconds": int(lookback.total_seconds()),
                    "required_audit_events": sorted(ACK_AUDIT_EVENTS),
                    "legacy_ack_audit_rows": len(ack_audits),
                    "required_audit_contract_version": 2,
                    "telemetry_gap": True,
                },
                runbook="docs/runbooks/observer_protocol_v3.md",
                run_id=run_id,
            )
        )
    for row in ack_contract_v2:
        details = row.details_json if isinstance(row.details_json, dict) else {}
        persisted_event_id = details.get("persisted_event_id")
        duplicate = bool(details.get("duplicate"))
        duplicate_proof = str(details.get("duplicate_proof") or "").strip()
        documented_noop = bool(details.get("documented_noop"))
        if persisted_event_id or (duplicate and duplicate_proof) or documented_noop:
            continue
        outbox_id = str(details.get("outbox_id") or "").strip() or f"audit-{row.id}"
        trace_id = str(details.get("trace_id") or "").strip() or None
        events.append(
            ObserverIntegrityEventInput(
                event_type="protocol_ack_without_persistence",
                severity="critical",
                source=SOURCE,
                dedupe_key=f"protocol_ack_without_persistence:{row.device_id}:{outbox_id}:{trace_id or row.id}",
                device_id=row.device_id,
                ticket_id=row.ticket_id,
                operation_id=row.operation_id,
                outbox_id=outbox_id,
                trace_id=trace_id,
                expected="Every Protocol V3 ACK must be backed by a persisted event id, duplicate proof, or documented no-op.",
                actual="ACK audit row has no persisted_event_id, no duplicate proof and no documented no-op.",
                evidence={
                    "audit_id": row.id,
                    "audit_contract_version": details.get("audit_contract_version"),
                    "outbox_id": outbox_id,
                    "event_type": details.get("event_type"),
                    "persistence_kind": details.get("persistence_kind"),
                    "db_persistence_enabled": details.get("db_persistence_enabled"),
                    "duplicate": duplicate,
                    "duplicate_proof": duplicate_proof or None,
                    "documented_noop": documented_noop,
                },
                runbook="docs/runbooks/observer_protocol_v3.md",
                run_id=run_id,
            )
        )

    rows = (
        await session.execute(
            select(AgentRuntimeAudit)
            .where(
                AgentRuntimeAudit.created_at >= cutoff,
                AgentRuntimeAudit.severity.in_(("warning", "error", "critical")),
            )
            .order_by(AgentRuntimeAudit.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    nack_by_device: dict[tuple[str, str], int] = {}
    for row in rows:
        details = row.details_json if isinstance(row.details_json, dict) else {}
        code = str(details.get("error_code") or details.get("nack_error_code") or "").strip().upper()
        if code not in NACK_CODES:
            continue
        key = (str(row.device_id or ""), code)
        nack_by_device[key] = nack_by_device.get(key, 0) + 1
    for (device_id, code), count in nack_by_device.items():
        if count < nack_threshold:
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="protocol_repeated_nack",
                severity="error" if code in {"DEVICE_MISMATCH", "UNKNOWN_TICKET"} else "warning",
                source=SOURCE,
                dedupe_key=f"protocol_repeated_nack:{device_id}:{code}",
                device_id=device_id,
                expected="Repeated Protocol V3 NACKs should stay below the configured rate threshold.",
                actual=f"{count} {code} NACK-related audit events in lookback window.",
                evidence={"error_code": code, "count": count, "threshold": nack_threshold},
                runbook="docs/runbooks/observer_protocol_v3.md",
                run_id=run_id,
            )
        )
    return events
