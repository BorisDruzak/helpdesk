"""OBS1 runtime presence/projection integrity checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


SOURCE = "observer.runtime_presence"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def check_runtime_presence(
    session: AsyncSession,
    *,
    state: Any = None,
    run_id: str | None = None,
    stale_after: timedelta = timedelta(minutes=15),
) -> list[ObserverIntegrityEventInput]:
    if state is None or not hasattr(state, "is_agent_online"):
        return []
    now = datetime.now(timezone.utc)
    result = await session.execute(select(Device).where(Device.is_deleted.is_(False)).limit(500))
    events: list[ObserverIntegrityEventInput] = []
    for device in result.scalars().all():
        device_id = str(device.device_id or "")
        if not device_id:
            continue
        try:
            online = bool(state.is_agent_online(device_id))
        except Exception:
            continue
        last_seen = _as_utc(getattr(device, "last_seen_at", None))
        if online and last_seen and now - last_seen > stale_after:
            events.append(
                ObserverIntegrityEventInput(
                    event_type="runtime_online_db_last_seen_stale",
                    severity="warning",
                    source=SOURCE,
                    dedupe_key=f"runtime_online_db_last_seen_stale:{device_id}",
                    device_id=device_id,
                    expected="Runtime-online devices should not be projected offline solely from stale DB last_seen.",
                    actual=f"runtime_online=true; db_last_seen_age_seconds={int((now - last_seen).total_seconds())}",
                    evidence={
                        "runtime_online": True,
                        "last_seen_at": last_seen.isoformat(),
                        "stale_after_seconds": int(stale_after.total_seconds()),
                    },
                    runbook="docs/runbooks/observer_runtime_presence.md",
                    run_id=run_id,
                )
            )
    return events
