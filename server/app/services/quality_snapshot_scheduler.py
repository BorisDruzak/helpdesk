from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from loguru import logger

from app.db import get_session
from quality.analytics_service import ServiceQualityAnalyticsService

QUALITY_SNAPSHOT_INTERVAL_SEC = 24 * 60 * 60


class QualitySnapshotScheduler:
    """Background scheduler for service/offering quality snapshots."""

    def __init__(self, *, session_maker: Optional[Callable[..., Any]] = None, interval_seconds: int | None = None) -> None:
        self.interval_seconds = interval_seconds or QUALITY_SNAPSHOT_INTERVAL_SEC
        self._session_maker = session_maker
        self._task: asyncio.Task | None = None
        self._running = False

    async def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        effective_now = now or datetime.now(timezone.utc)
        if effective_now.tzinfo is None:
            effective_now = effective_now.replace(tzinfo=timezone.utc)
        day_start = effective_now - timedelta(days=1)
        week_start = effective_now - timedelta(days=7)
        buckets = [
            ("day", day_start, effective_now),
            ("week", week_start, effective_now),
        ]
        last_computed_at: str | None = None
        session_factory = self._session_maker or get_session
        async with session_factory() as session:
            service = ServiceQualityAnalyticsService(session)
            for bucket, period_start, period_end in buckets:
                summary = await service.service_quality(
                    period_start=period_start,
                    period_end=period_end,
                    bucket=bucket,
                    recompute_snapshot=True,
                )
                last_computed_at = summary.get("last_computed_at") or last_computed_at
            await session.commit()
        result = {
            "buckets": [bucket for bucket, _start, _end in buckets],
            "last_computed_at": last_computed_at,
            "computed_at": effective_now.isoformat(),
        }
        logger.info(f"[QualitySnapshotScheduler] recomputed quality snapshots buckets={result['buckets']}")
        return result

    async def _loop(self) -> None:
        logger.info(f"[QualitySnapshotScheduler] Started interval={self.interval_seconds}s")
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.error(f"[QualitySnapshotScheduler] Loop error: {exc}", exc_info=True)
            await asyncio.sleep(self.interval_seconds)
        logger.info("[QualitySnapshotScheduler] Stopped")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


_quality_snapshot_scheduler: QualitySnapshotScheduler | None = None


def get_quality_snapshot_scheduler() -> QualitySnapshotScheduler:
    global _quality_snapshot_scheduler
    if _quality_snapshot_scheduler is None:
        _quality_snapshot_scheduler = QualitySnapshotScheduler()
    return _quality_snapshot_scheduler
