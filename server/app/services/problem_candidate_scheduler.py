from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.db.engine import get_session_maker
from app.db.models import ProblemScannerRun
from problem.candidate_service import ProblemCandidateService
from problem.serializers import scanner_run_to_dict


class ProblemCandidateScheduler:
    def __init__(
        self,
        *,
        session_maker=None,
        enabled: bool | None = None,
        interval_seconds: int | None = None,
        initial_delay_seconds: int | None = None,
        lookback_hours: int | None = None,
        max_candidates_per_run: int | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.session_maker = session_maker or get_session_maker()
        self.enabled = _env_bool("PROBLEM_SCANNER_ENABLED", False) if enabled is None else bool(enabled)
        self.interval_seconds = interval_seconds if interval_seconds is not None else _env_int("PROBLEM_SCANNER_INTERVAL_SEC", 86400)
        self.initial_delay_seconds = initial_delay_seconds if initial_delay_seconds is not None else _env_int("PROBLEM_SCANNER_INITIAL_DELAY_SEC", 300)
        self.lookback_hours = lookback_hours if lookback_hours is not None else _env_int("PROBLEM_SCANNER_LOOKBACK_HOURS", 168)
        self.max_candidates_per_run = max_candidates_per_run if max_candidates_per_run is not None else _env_int("PROBLEM_SCANNER_MAX_CANDIDATES_PER_RUN", 100)
        self.dry_run = _env_bool("PROBLEM_SCANNER_DRY_RUN", False) if dry_run is None else bool(dry_run)
        self._task: asyncio.Task | None = None
        self._run_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self.enabled:
            logger.info("Problem candidate scheduler disabled")
            return
        if self.is_running:
            return
        self._task = asyncio.create_task(self._loop(), name="problem-candidate-scanner")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def run_once(
        self,
        *,
        triggered_by: str = "scheduler",
        actor_id: str | None = None,
        now: datetime | None = None,
        lookback_hours: int | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        if self._run_lock.locked():
            return {"status": "skipped_overlap", "candidates_created": 0, "candidates_updated": 0, "candidates_skipped": 1}
        async with self._run_lock:
            started = now or datetime.now(timezone.utc)
            run_id = str(uuid.uuid4())
            async with self.session_maker() as session:
                row = ProblemScannerRun(
                    run_id=run_id,
                    started_at=started,
                    status="running",
                    triggered_by=triggered_by,
                    lookback_hours=int(lookback_hours or self.lookback_hours),
                    metadata_json={"dry_run": self.dry_run if dry_run is None else bool(dry_run)},
                )
                session.add(row)
                await session.commit()
            try:
                async with self.session_maker() as session:
                    result = await ProblemCandidateService(session).scan(
                        actor_id=actor_id or "system",
                        now=started,
                        lookback_hours=int(lookback_hours or self.lookback_hours),
                        max_candidates=int(self.max_candidates_per_run),
                        dry_run=self.dry_run if dry_run is None else bool(dry_run),
                    )
                    finished = datetime.now(timezone.utc)
                    row = await session.get(ProblemScannerRun, run_id)
                    row.status = "completed"
                    row.finished_at = finished
                    row.duration_ms = int((finished - started).total_seconds() * 1000)
                    row.candidates_created = int(result.get("created") or 0)
                    row.candidates_updated = int(result.get("updated") or 0)
                    row.candidates_skipped = int(result.get("skipped") or 0)
                    row.rules_run = list(result.get("rules_run") or [])
                    await session.commit()
                    return scanner_run_to_dict(row)
            except Exception as exc:
                logger.exception("Problem candidate scan failed")
                async with self.session_maker() as session:
                    row = await session.get(ProblemScannerRun, run_id)
                    if row is not None:
                        finished = datetime.now(timezone.utc)
                        row.status = "failed"
                        row.finished_at = finished
                        row.duration_ms = int((finished - started).total_seconds() * 1000)
                        row.errors_json = [{"type": type(exc).__name__, "message": str(exc)[:500]}]
                        await session.commit()
                        return scanner_run_to_dict(row)
                return {"status": "failed", "errors": [{"type": type(exc).__name__, "message": str(exc)[:500]}]}

    async def status(self) -> dict[str, Any]:
        async with self.session_maker() as session:
            row = (
                await session.execute(select(ProblemScannerRun).order_by(ProblemScannerRun.started_at.desc()).limit(1))
            ).scalar_one_or_none()
            return {
                "enabled": self.enabled,
                "running": self._run_lock.locked(),
                "interval_seconds": self.interval_seconds,
                "lookback_hours": self.lookback_hours,
                "dry_run": self.dry_run,
                "last_run": scanner_run_to_dict(row) if row else None,
            }

    async def recent_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        async with self.session_maker() as session:
            rows = (
                await session.execute(select(ProblemScannerRun).order_by(ProblemScannerRun.started_at.desc()).limit(max(1, min(limit, 100))))
            ).scalars().all()
            return [scanner_run_to_dict(row) for row in rows]

    async def _loop(self) -> None:
        if self.initial_delay_seconds > 0:
            await asyncio.sleep(self.initial_delay_seconds)
        while True:
            await self.run_once(triggered_by="scheduler", actor_id="system")
            await asyncio.sleep(max(1, self.interval_seconds))


_PROBLEM_CANDIDATE_SCHEDULER: ProblemCandidateScheduler | None = None


def get_problem_candidate_scheduler() -> ProblemCandidateScheduler:
    global _PROBLEM_CANDIDATE_SCHEDULER
    if _PROBLEM_CANDIDATE_SCHEDULER is None:
        _PROBLEM_CANDIDATE_SCHEDULER = ProblemCandidateScheduler()
    return _PROBLEM_CANDIDATE_SCHEDULER


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
