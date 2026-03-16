"""
Playbook Scheduler (Этап 6): фоновый запуск отложенных run (pending, scheduled_at <= now).

Интервал опроса 2–5 сек (config), batch 100, max active runs per device — из конфига.
FOR UPDATE SKIP LOCKED для конкурентной безопасности.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.db import get_session
from app.repos.playbook_repo import PlaybookRepo
from app.services.playbook_engine import start_first_step_for_run
import config


class PlaybookScheduler:
    """Планировщик: выбирает due pending runs и ставит первый шаг в outbox."""

    def __init__(self, interval: Optional[int] = None, app=None):
        self.interval = interval or config.PLAYBOOK_SCHEDULER_INTERVAL
        self.app = app
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def set_app(self, app) -> None:
        self.app = app

    async def _tick(self) -> None:
        if not config.PLAYBOOK_SCHEDULER_ENABLED:
            return
        if not self.app or "state" not in self.app:
            return
        state = self.app["state"]
        try:
            async with get_session() as session:
                repo = PlaybookRepo(session)
                now = datetime.now(timezone.utc)
                due_runs = await repo.get_due_pending_runs(limit=100, now=now)
                if not due_runs:
                    return
                logger.debug(f"[PlaybookScheduler] {len(due_runs)} due pending runs")
                max_active = config.PLAYBOOK_MAX_ACTIVE_RUNS_PER_DEVICE
                started = 0
                for run in due_runs:
                    if started >= 100:
                        break
                    active = await repo.count_running_runs_by_device(run.device_id)
                    if active >= max_active:
                        logger.warning(
                            f"[PlaybookScheduler] Skip run_id={run.id} device_id={run.device_id}: "
                            f"active={active} >= max={max_active}"
                        )
                        continue
                    try:
                        await start_first_step_for_run(session, state, run.id)
                        started += 1
                    except Exception as e:
                        logger.error(
                            f"[PlaybookScheduler] Failed to start run_id={run.id}: {e}",
                            exc_info=True,
                        )
                if started:
                    await session.commit()
                    logger.info(f"[PlaybookScheduler] Started {started} runs")
        except Exception as e:
            logger.error(f"[PlaybookScheduler] Tick error: {e}", exc_info=True)

    async def _loop(self) -> None:
        logger.info(f"[PlaybookScheduler] Started interval={self.interval}s")
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"[PlaybookScheduler] Loop error: {e}", exc_info=True)
            await asyncio.sleep(self.interval)
        logger.info("[PlaybookScheduler] Stopped")

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


_scheduler: Optional[PlaybookScheduler] = None


def get_playbook_scheduler(interval: Optional[int] = None) -> PlaybookScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = PlaybookScheduler(interval=interval)
    return _scheduler
