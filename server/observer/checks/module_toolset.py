"""OBS1 module, toolset and artifact integrity checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Device, DeviceDesiredModule, DeviceModule, DeviceToolsetSnapshot, TicketEvent
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


SOURCE = "observer.module_toolset"


async def check_module_toolset(
    session: AsyncSession,
    *,
    run_id: str | None = None,
    drift_after: timedelta = timedelta(minutes=15),
) -> list[ObserverIntegrityEventInput]:
    events: list[ObserverIntegrityEventInput] = []
    events.extend(await _toolset_hash_drift(session, run_id=run_id, drift_after=drift_after))
    events.extend(await _desired_actual_module_drift(session, run_id=run_id, drift_after=drift_after))
    events.extend(await _missing_artifacts(session, run_id=run_id))
    return events


async def _toolset_hash_drift(
    session: AsyncSession,
    *,
    run_id: str | None,
    drift_after: timedelta,
) -> list[ObserverIntegrityEventInput]:
    now = datetime.now(timezone.utc)
    devices = (
        await session.execute(
            select(Device)
            .where(Device.deleted_at.is_(None), Device.current_toolset_hash.is_not(None))
            .limit(500)
        )
    ).scalars().all()
    events: list[ObserverIntegrityEventInput] = []
    for device in devices:
        latest = (
            await session.execute(
                select(DeviceToolsetSnapshot)
                .where(DeviceToolsetSnapshot.device_id == device.device_id)
                .order_by(DeviceToolsetSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None or latest.toolset_hash == device.current_toolset_hash:
            continue
        captured_at = latest.captured_at
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        if now - captured_at < drift_after:
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="toolset_hash_drift",
                severity="error",
                source=SOURCE,
                dedupe_key=f"toolset_hash_drift:{device.device_id}",
                device_id=device.device_id,
                expected="devices.current_toolset_hash should match the latest device_toolset_snapshots.toolset_hash beyond grace period.",
                actual=f"current_toolset_hash={device.current_toolset_hash}; latest_snapshot_hash={latest.toolset_hash}",
                evidence={
                    "current_toolset_hash": device.current_toolset_hash,
                    "latest_snapshot_id": latest.snapshot_id,
                    "latest_snapshot_hash": latest.toolset_hash,
                    "latest_snapshot_captured_at": latest.captured_at.isoformat() if latest.captured_at else None,
                },
                runbook="docs/runbooks/observer_module_toolset.md",
                run_id=run_id,
            )
        )
    return events


async def _desired_actual_module_drift(
    session: AsyncSession,
    *,
    run_id: str | None,
    drift_after: timedelta,
) -> list[ObserverIntegrityEventInput]:
    cutoff = datetime.now(timezone.utc) - drift_after
    desired_rows = (
        await session.execute(
            select(DeviceDesiredModule)
            .where(DeviceDesiredModule.state == "installed", DeviceDesiredModule.updated_at <= cutoff)
            .limit(500)
        )
    ).scalars().all()
    events: list[ObserverIntegrityEventInput] = []
    for desired in desired_rows:
        actual = (
            await session.execute(
                select(DeviceModule)
                .where(
                    DeviceModule.device_id == desired.device_id,
                    DeviceModule.module_name == desired.module_name,
                    DeviceModule.active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if actual and (not desired.desired_version or actual.version == desired.desired_version):
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="module_desired_actual_drift",
                severity="error" if actual is None else "warning",
                source=SOURCE,
                dedupe_key=f"module_desired_actual_drift:{desired.device_id}:{desired.module_name}",
                device_id=desired.device_id,
                expected="Desired installed module should be active on the device at the requested version beyond grace period.",
                actual=(
                    "actual module missing"
                    if actual is None
                    else f"actual.version={actual.version}; desired.version={desired.desired_version}"
                ),
                evidence={
                    "module_name": desired.module_name,
                    "desired_version": desired.desired_version,
                    "desired_updated_at": desired.updated_at.isoformat() if desired.updated_at else None,
                    "actual_version": getattr(actual, "version", None),
                    "actual_state": getattr(actual, "state", None),
                },
                runbook="docs/runbooks/observer_module_toolset.md",
                run_id=run_id,
            )
        )
    return events


async def _missing_artifacts(session: AsyncSession, *, run_id: str | None) -> list[ObserverIntegrityEventInput]:
    rows = (
        await session.execute(
            select(TicketEvent)
            .where(TicketEvent.event_type == "tool_call_result", TicketEvent.operation_id.is_not(None))
            .order_by(TicketEvent.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    events: list[ObserverIntegrityEventInput] = []
    for event in rows:
        payload = event.payload if isinstance(event.payload, dict) else {}
        artifacts = payload.get("artifacts") or payload.get("_artifacts") or []
        if not isinstance(artifacts, list) or not artifacts:
            continue
        count = int(
            await session.scalar(
                select(func.count())
                .select_from(Artifact)
                .where(Artifact.operation_id == event.operation_id)
            )
            or 0
        )
        if count > 0:
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="artifact_result_missing_rows",
                severity="critical",
                source=SOURCE,
                dedupe_key=f"artifact_result_missing_rows:{event.operation_id}",
                device_id=event.device_id,
                ticket_id=event.ticket_id,
                operation_id=event.operation_id,
                trace_id=event.trace_id,
                expected="Tool result that references artifacts should have artifact rows linked by operation_id.",
                actual=f"tool_call_result references {len(artifacts)} artifacts but artifacts table has 0 linked rows.",
                evidence={
                    "ticket_event_id": event.id,
                    "artifact_ref_count": len(artifacts),
                    "artifact_row_count": count,
                },
                runbook="docs/runbooks/observer_module_toolset.md",
                run_id=run_id,
            )
        )
    return events
