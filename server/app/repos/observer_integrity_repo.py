"""Repository for durable OBS1 operational integrity events."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ObserverIntegrityEvent, ObserverKnownContamination
from shared.redaction import redact_sensitive_payload


OBSERVER_INTEGRITY_NAMESPACE = uuid.UUID("94d71381-2f77-4ba1-810e-dce1fd70fb1c")
ALLOWED_SEVERITIES = {"info", "warning", "error", "critical"}
ALLOWED_STATUSES = {"active", "acknowledged", "resolved", "suppressed"}


@dataclass(slots=True)
class ObserverIntegrityEventInput:
    event_type: str
    severity: str
    source: str
    dedupe_key: str
    expected: str
    actual: str
    evidence: dict[str, Any]
    device_id: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None
    command_id: str | None = None
    device_outbox_id: int | None = None
    outbox_id: str | None = None
    trace_id: str | None = None
    actor_role: str | None = None
    runbook: str | None = None
    run_id: str | None = None
    detected_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _compact(value: Any, *, max_len: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_len] if max_len else text


def _normalize_severity(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in ALLOWED_SEVERITIES else "warning"


def stable_event_id(dedupe_key: str) -> str:
    return str(uuid.uuid5(OBSERVER_INTEGRITY_NAMESPACE, dedupe_key))


class ObserverIntegrityRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_event(
        self,
        event: ObserverIntegrityEventInput,
        *,
        suppression_reason: str | None = None,
    ) -> ObserverIntegrityEvent:
        now = _now()
        detected_at = event.detected_at or now
        status = "suppressed" if suppression_reason else "active"
        existing = await self.get_by_dedupe_key(event.dedupe_key)
        safe_evidence = redact_sensitive_payload(event.evidence if isinstance(event.evidence, dict) else {})
        if existing is None:
            row = ObserverIntegrityEvent(
                event_id=stable_event_id(event.dedupe_key),
                event_type=_compact(event.event_type, max_len=120) or "observer_integrity_unknown",
                severity=_normalize_severity(event.severity),
                source=_compact(event.source, max_len=120) or "observer.unknown",
                status=status,
                detected_at=detected_at,
                first_seen_at=now,
                last_seen_at=now,
                dedupe_key=_compact(event.dedupe_key, max_len=300) or stable_event_id(str(now)),
                occurrence_count=1,
                device_id=_compact(event.device_id, max_len=36),
                ticket_id=_compact(event.ticket_id, max_len=36),
                operation_id=_compact(event.operation_id, max_len=36),
                command_id=_compact(event.command_id, max_len=36),
                device_outbox_id=event.device_outbox_id,
                outbox_id=_compact(event.outbox_id, max_len=120),
                trace_id=_compact(event.trace_id, max_len=36),
                actor_role=_compact(event.actor_role, max_len=30),
                expected=str(event.expected or "")[:2000],
                actual=str(event.actual or "")[:2000],
                evidence_json=safe_evidence,
                runbook=_compact(event.runbook),
                suppression_reason=suppression_reason,
                run_id=_compact(event.run_id, max_len=120),
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
            await self.session.flush()
            return row

        existing.event_type = _compact(event.event_type, max_len=120) or existing.event_type
        existing.severity = _normalize_severity(event.severity)
        existing.source = _compact(event.source, max_len=120) or existing.source
        existing.status = status
        existing.detected_at = detected_at
        existing.last_seen_at = now
        existing.resolved_at = None
        existing.occurrence_count = int(existing.occurrence_count or 0) + 1
        existing.device_id = _compact(event.device_id, max_len=36)
        existing.ticket_id = _compact(event.ticket_id, max_len=36)
        existing.operation_id = _compact(event.operation_id, max_len=36)
        existing.command_id = _compact(event.command_id, max_len=36)
        existing.device_outbox_id = event.device_outbox_id
        existing.outbox_id = _compact(event.outbox_id, max_len=120)
        existing.trace_id = _compact(event.trace_id, max_len=36)
        existing.actor_role = _compact(event.actor_role, max_len=30)
        existing.expected = str(event.expected or "")[:2000]
        existing.actual = str(event.actual or "")[:2000]
        existing.evidence_json = safe_evidence
        existing.runbook = _compact(event.runbook)
        existing.suppression_reason = suppression_reason
        existing.run_id = _compact(event.run_id, max_len=120)
        existing.updated_at = now
        await self.session.flush()
        return existing

    async def get_by_dedupe_key(self, dedupe_key: str) -> ObserverIntegrityEvent | None:
        return (
            await self.session.execute(
                select(ObserverIntegrityEvent).where(ObserverIntegrityEvent.dedupe_key == dedupe_key).limit(1)
            )
        ).scalar_one_or_none()

    async def resolve_missing(
        self,
        *,
        source: str,
        active_dedupe_keys: set[str],
        run_id: str | None = None,
    ) -> int:
        now = _now()
        stmt = select(ObserverIntegrityEvent).where(
            ObserverIntegrityEvent.source == source,
            ObserverIntegrityEvent.status.in_(("active", "acknowledged")),
        )
        if active_dedupe_keys:
            stmt = stmt.where(ObserverIntegrityEvent.dedupe_key.not_in(active_dedupe_keys))
        rows = list((await self.session.execute(stmt)).scalars().all())
        for row in rows:
            row.status = "resolved"
            row.resolved_at = now
            row.updated_at = now
            if run_id and not row.run_id:
                row.run_id = run_id
        await self.session.flush()
        return len(rows)

    async def list_events(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        device_id: str | None = None,
        ticket_id: str | None = None,
        operation_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ObserverIntegrityEvent]:
        stmt = select(ObserverIntegrityEvent)
        if severity:
            stmt = stmt.where(ObserverIntegrityEvent.severity == severity)
        if status:
            stmt = stmt.where(ObserverIntegrityEvent.status == status)
        if device_id:
            stmt = stmt.where(ObserverIntegrityEvent.device_id == device_id)
        if ticket_id:
            stmt = stmt.where(ObserverIntegrityEvent.ticket_id == ticket_id)
        if operation_id:
            stmt = stmt.where(ObserverIntegrityEvent.operation_id == operation_id)
        if event_type:
            stmt = stmt.where(ObserverIntegrityEvent.event_type == event_type)
        if since:
            stmt = stmt.where(ObserverIntegrityEvent.last_seen_at >= since)
        stmt = stmt.order_by(
            ObserverIntegrityEvent.status.asc(),
            ObserverIntegrityEvent.severity.desc(),
            ObserverIntegrityEvent.last_seen_at.desc(),
        ).limit(max(1, min(int(limit or 100), 500)))
        return list((await self.session.execute(stmt)).scalars().all())

    async def summary(self, *, limit: int = 5) -> dict[str, Any]:
        counts_rows = (
            await self.session.execute(
                select(
                    ObserverIntegrityEvent.status,
                    ObserverIntegrityEvent.severity,
                    func.count(ObserverIntegrityEvent.event_id),
                ).group_by(ObserverIntegrityEvent.status, ObserverIntegrityEvent.severity)
            )
        ).all()
        counts_by_status: dict[str, dict[str, int]] = {}
        counts_by_severity = {severity: 0 for severity in ("critical", "error", "warning", "info")}
        for status, severity, count in counts_rows:
            status_key = str(status or "unknown")
            severity_key = str(severity or "unknown")
            counts_by_status.setdefault(status_key, {})[severity_key] = int(count or 0)
            if status_key == "active" and severity_key in counts_by_severity:
                counts_by_severity[severity_key] += int(count or 0)
        top = await self.list_events(status="active", limit=limit)
        suppressed = sum(count for status, values in counts_by_status.items() if status == "suppressed" for count in values.values())
        return {
            "active_by_severity": counts_by_severity,
            "by_status": counts_by_status,
            "active_total": sum(counts_by_severity.values()),
            "suppressed_total": suppressed,
            "top_active": [serialize_observer_integrity_event(row) for row in top],
        }

    async def find_contamination(self, event: ObserverIntegrityEventInput) -> ObserverKnownContamination | None:
        candidates: list[tuple[str, str | None]] = [
            ("device_outbox", str(event.device_outbox_id) if event.device_outbox_id is not None else None),
            ("operation", event.operation_id),
            ("ticket", event.ticket_id),
            ("device", event.device_id),
            ("command", event.command_id),
            ("dedupe_key", event.dedupe_key),
        ]
        now = _now()
        filters = [
            and_(
                ObserverKnownContamination.entity_type == entity_type,
                ObserverKnownContamination.entity_id == entity_id,
            )
            for entity_type, entity_id in candidates
            if entity_id
        ]
        if not filters:
            return None
        return (
            await self.session.execute(
                select(ObserverKnownContamination)
                .where(
                    ObserverKnownContamination.active.is_(True),
                    or_(
                        ObserverKnownContamination.expires_at.is_(None),
                        ObserverKnownContamination.expires_at > now,
                    ),
                    or_(*filters),
                )
                .order_by(ObserverKnownContamination.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def ensure_contamination(self, *, rows: list[dict[str, Any]]) -> int:
        created = 0
        for item in rows:
            source_phase = _compact(item.get("source_phase"), max_len=30)
            entity_type = _compact(item.get("entity_type"), max_len=80)
            entity_id = _compact(item.get("entity_id"), max_len=160)
            scope = _compact(item.get("suppression_scope"), max_len=160) or "observer_integrity"
            reason = _compact(item.get("reason")) or "historical contamination"
            if not source_phase or not entity_type or not entity_id:
                continue
            existing = (
                await self.session.execute(
                    select(ObserverKnownContamination)
                    .where(
                        ObserverKnownContamination.entity_type == entity_type,
                        ObserverKnownContamination.entity_id == entity_id,
                        ObserverKnownContamination.suppression_scope == scope,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            self.session.add(
                ObserverKnownContamination(
                    source_phase=source_phase,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    suppression_scope=scope,
                    reason=reason,
                    notes=_compact(item.get("notes")),
                    active=bool(item.get("active", True)),
                    created_at=_now(),
                    expires_at=item.get("expires_at") if isinstance(item.get("expires_at"), datetime) else None,
                )
            )
            created += 1
        await self.session.flush()
        return created


def serialize_observer_integrity_event(row: ObserverIntegrityEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "severity": row.severity,
        "source": row.source,
        "detected_at": row.detected_at.isoformat() if row.detected_at else None,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "device_id": row.device_id,
        "ticket_id": row.ticket_id,
        "operation_id": row.operation_id,
        "command_id": row.command_id,
        "device_outbox_id": row.device_outbox_id,
        "outbox_id": row.outbox_id,
        "trace_id": row.trace_id,
        "actor_role": row.actor_role,
        "expected": row.expected,
        "actual": row.actual,
        "evidence": redact_sensitive_payload(row.evidence_json or {}),
        "dedupe_key": row.dedupe_key,
        "runbook": row.runbook,
        "status": row.status,
        "suppression_reason": row.suppression_reason,
        "occurrence_count": row.occurrence_count,
        "run_id": row.run_id,
    }
