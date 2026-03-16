"""
Репозиторий для Playbook Engine: run, step_run, выборка по operation_id.
Этап 6: pending/scheduled_at, idempotency_key, due runs для планировщика.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Playbook,
    PlaybookVersion,
    PlaybookStep,
    PlaybookRun,
    PlaybookStepRun,
)


class PlaybookRepo:
    """Операции с плейбуками, версиями, шагами, запусками и step_run."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_version_with_steps(
        self, playbook_version_id: int
    ) -> Optional[Tuple[PlaybookVersion, List[PlaybookStep]]]:
        """Возвращает версию и её шаги по order_no."""
        version = await self.session.get(PlaybookVersion, playbook_version_id)
        if not version:
            return None
        result = await self.session.execute(
            select(PlaybookStep)
            .where(PlaybookStep.playbook_version_id == playbook_version_id)
            .order_by(PlaybookStep.order_no)
        )
        steps = list(result.scalars().all())
        return (version, steps)

    async def create_run(
        self,
        playbook_version_id: int,
        device_id: str,
        trigger_type: Optional[str] = None,
        context_json: Optional[dict] = None,
        status: str = "running",
        scheduled_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
    ) -> PlaybookRun:
        """Создаёт playbook_run. По умолчанию status=running, started_at=now, scheduled_at=now."""
        now = datetime.now(timezone.utc)
        if scheduled_at is None:
            scheduled_at = now
        if status == "running" and started_at is None:
            started_at = now
        run = PlaybookRun(
            playbook_version_id=playbook_version_id,
            device_id=device_id,
            status=status,
            scheduled_at=scheduled_at,
            started_at=started_at,
            trigger_type=trigger_type,
            context_json=context_json,
            idempotency_key=idempotency_key,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[PlaybookRun]:
        """Возвращает существующий run по idempotency_key или None."""
        result = await self.session.execute(
            select(PlaybookRun).where(PlaybookRun.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_due_pending_runs(
        self, limit: int = 100, now: Optional[datetime] = None
    ) -> List[PlaybookRun]:
        """Выборка pending runs с scheduled_at <= now для планировщика (FOR UPDATE SKIP LOCKED)."""
        if now is None:
            now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PlaybookRun)
            .where(
                and_(
                    PlaybookRun.status == "pending",
                    PlaybookRun.scheduled_at <= now,
                )
            )
            .order_by(PlaybookRun.scheduled_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def count_running_runs_by_device(self, device_id: str) -> int:
        """Количество активных (running) runs по устройству."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(PlaybookRun.id)).where(
                and_(
                    PlaybookRun.device_id == device_id,
                    PlaybookRun.status == "running",
                )
            )
        )
        return result.scalar() or 0

    async def set_run_running(self, run_id: int, started_at: Optional[datetime] = None) -> None:
        """Переводит run в status=running и устанавливает started_at."""
        if started_at is None:
            started_at = datetime.now(timezone.utc)
        await self.session.execute(
            update(PlaybookRun)
            .where(PlaybookRun.id == run_id, PlaybookRun.status == "pending")
            .values(status="running", started_at=started_at)
        )
        await self.session.flush()

    async def create_step_run(
        self,
        playbook_run_id: int,
        playbook_step_id: int,
        operation_id: str,
        attempt: int = 1,
        input_json: Optional[dict] = None,
    ) -> PlaybookStepRun:
        """Создаёт playbook_step_run со статусом running, started_at=now."""
        step_run = PlaybookStepRun(
            playbook_run_id=playbook_run_id,
            playbook_step_id=playbook_step_id,
            attempt=attempt,
            status="running",
            operation_id=operation_id,
            started_at=datetime.now(timezone.utc),
            input_json=input_json,
        )
        self.session.add(step_run)
        await self.session.flush()
        return step_run

    async def create_step_run_skipped(
        self,
        playbook_run_id: int,
        playbook_step_id: int,
        reason: Optional[str] = None,
    ) -> PlaybookStepRun:
        """Этап 7: Создаёт step_run со статусом skipped (if_expr=False), без operation_id."""
        now = datetime.now(timezone.utc)
        step_run = PlaybookStepRun(
            playbook_run_id=playbook_run_id,
            playbook_step_id=playbook_step_id,
            attempt=1,
            status="skipped",
            operation_id=None,
            started_at=now,
            finished_at=now,
            input_json={"reason": reason or "if_expr=false"},
        )
        self.session.add(step_run)
        await self.session.flush()
        return step_run

    async def create_step_run_failed(
        self,
        playbook_run_id: int,
        playbook_step_id: int,
        error_code: str,
        error_message: str,
        attempt: int = 1,
    ) -> PlaybookStepRun:
        """Этап 9: Создаёт step_run со статусом failed до отправки команды (capability gate и т.п.)."""
        now = datetime.now(timezone.utc)
        step_run = PlaybookStepRun(
            playbook_run_id=playbook_run_id,
            playbook_step_id=playbook_step_id,
            attempt=attempt,
            status="failed",
            operation_id=None,
            started_at=now,
            finished_at=now,
            error_json={"code": error_code, "message": error_message},
        )
        self.session.add(step_run)
        await self.session.flush()
        return step_run

    async def get_step_run_with_step_and_run(
        self, step_run_id: int
    ) -> Optional[Tuple[PlaybookStepRun, PlaybookStep, PlaybookRun]]:
        """Этап 9: Возвращает (step_run, step, run) по step_run_id для advance без operation_id."""
        result = await self.session.execute(
            select(PlaybookStepRun, PlaybookStep, PlaybookRun)
            .join(
                PlaybookStep,
                PlaybookStepRun.playbook_step_id == PlaybookStep.id,
            )
            .join(
                PlaybookRun,
                PlaybookStepRun.playbook_run_id == PlaybookRun.id,
            )
            .where(
                PlaybookStepRun.id == step_run_id,
                PlaybookRun.status == "running",
            )
        )
        row = result.first()
        if not row:
            return None
        return (row[0], row[1], row[2])

    async def get_step_run_by_operation_id(
        self, operation_id: str
    ) -> Optional[Tuple[PlaybookStepRun, PlaybookStep, PlaybookRun]]:
        """Находит step_run по operation_id и возвращает step_run, step, run."""
        result = await self.session.execute(
            select(PlaybookStepRun, PlaybookStep, PlaybookRun)
            .join(
                PlaybookStep,
                PlaybookStepRun.playbook_step_id == PlaybookStep.id,
            )
            .join(
                PlaybookRun,
                PlaybookStepRun.playbook_run_id == PlaybookRun.id,
            )
            .where(
                and_(
                    PlaybookStepRun.operation_id == operation_id,
                    PlaybookRun.status == "running",
                )
            )
        )
        row = result.first()
        if not row:
            return None
        return (row[0], row[1], row[2])

    async def update_step_run_terminal(
        self,
        step_run_id: int,
        status: str,
        output_json: Optional[dict] = None,
        error_json: Optional[dict] = None,
    ) -> None:
        """Помечает step_run как завершённый (success/failed)."""
        step_run = await self.session.get(PlaybookStepRun, step_run_id)
        if not step_run:
            return
        step_run.status = status
        step_run.finished_at = datetime.now(timezone.utc)
        if output_json is not None:
            step_run.output_json = output_json
        if error_json is not None:
            step_run.error_json = error_json
        await self.session.flush()

    async def get_run_with_step_runs(
        self, playbook_run_id: int
    ) -> Optional[Tuple[PlaybookRun, List[PlaybookStepRun]]]:
        """Возвращает run и все его step_run, упорядоченные по id (порядок создания)."""
        run = await self.session.get(PlaybookRun, playbook_run_id)
        if not run:
            return None
        result = await self.session.execute(
            select(PlaybookStepRun)
            .where(PlaybookStepRun.playbook_run_id == playbook_run_id)
            .order_by(PlaybookStepRun.id)
        )
        step_runs = list(result.scalars().all())
        return (run, step_runs)

    async def get_prev_steps_for_run(
        self, playbook_run_id: int
    ) -> dict:
        """
        Этап 7: Возвращает завершённые шаги run для контекста if_expr/params_template.
        { step_key: { "output": {...}, "error": {...}, "status": "success"|"failed"|"skipped" } }
        skipped не маппится в failed — if_expr различает skipped и failed.
        Только step_run в терминальном состоянии (finished_at IS NOT NULL).
        """
        result = await self.session.execute(
            select(PlaybookStepRun, PlaybookStep.step_key)
            .join(
                PlaybookStep,
                PlaybookStepRun.playbook_step_id == PlaybookStep.id,
            )
            .where(
                PlaybookStepRun.playbook_run_id == playbook_run_id,
                PlaybookStepRun.finished_at.isnot(None),
            )
            .order_by(PlaybookStepRun.id)
        )
        prev = {}
        for step_run, step_key in result.all():
            # Не маппить skipped в failed — if_expr должен различать skipped и failed
            status = step_run.status if step_run.status in ("success", "failed", "skipped") else "failed"
            prev[step_key] = {
                "output": step_run.output_json,
                "error": step_run.error_json,
                "status": status,
            }
        return prev

    async def count_running_step_runs_for_run(self, playbook_run_id: int) -> int:
        """Этап 8: Количество step_run со статусом running для run (лимит параллелизма)."""
        result = await self.session.execute(
            select(func.count(PlaybookStepRun.id)).where(
                and_(
                    PlaybookStepRun.playbook_run_id == playbook_run_id,
                    PlaybookStepRun.status == "running",
                )
            )
        )
        return result.scalar() or 0

    async def get_step_runs_for_run_by_step_ids(
        self, playbook_run_id: int, playbook_step_ids: list
    ) -> List[PlaybookStepRun]:
        """Этап 8: Все step_run для run с playbook_step_id в заданном списке."""
        if not playbook_step_ids:
            return []
        result = await self.session.execute(
            select(PlaybookStepRun).where(
                and_(
                    PlaybookStepRun.playbook_run_id == playbook_run_id,
                    PlaybookStepRun.playbook_step_id.in_(playbook_step_ids),
                )
            )
        )
        return list(result.scalars().all())

    async def finish_run(
        self,
        playbook_run_id: int,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Устанавливает run в terminal (success/failed)."""
        run = await self.session.get(PlaybookRun, playbook_run_id)
        if not run:
            return
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.error_code = error_code
        run.error_message = error_message
        await self.session.flush()
