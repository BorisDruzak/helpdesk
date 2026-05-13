from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceModule,
    Module,
    RunnerRolloutEvent,
    RunnerRolloutPlan,
    RunnerRolloutTarget,
    RunnerRolloutWave,
)
from modules.reconcile import reconcile_device, set_desired_installed
from utils.module_manifest import get_module_manifest


RUNNER_MODULE_NAME = "agent_recipe_runner"
PLAN_ACTIVE_STATUSES = {"draft", "active", "paused", "rolling_back"}
TARGET_STARTED_STATUSES = {
    "desired_set",
    "installing",
    "succeeded",
    "failed",
    "rollback_desired",
    "rolling_back",
    "rolled_back",
}


class RunnerRolloutError(ValueError):
    pass


class RunnerRolloutStateError(RunnerRolloutError):
    pass


class RunnerRolloutService:
    """Admin-controlled fleet rollout workflow for the protected Agent Recipe Runner module."""

    def __init__(self, session: AsyncSession, *, state: Any = None):
        self.session = session
        self.state = state

    async def summary(self) -> dict[str, Any]:
        latest_plan = await self.session.scalar(
            select(RunnerRolloutPlan)
            .where(RunnerRolloutPlan.module_name == RUNNER_MODULE_NAME)
            .order_by(RunnerRolloutPlan.created_at.desc())
            .limit(1)
        )
        active_count = await self.session.scalar(
            select(func.count(DeviceModule.id)).where(
                DeviceModule.module_name == RUNNER_MODULE_NAME,
                DeviceModule.installed.is_(True),
                DeviceModule.active.is_(True),
            )
        )
        versions = await self.session.execute(
            select(DeviceModule.version, func.count(DeviceModule.id))
            .where(
                DeviceModule.module_name == RUNNER_MODULE_NAME,
                DeviceModule.installed.is_(True),
                DeviceModule.active.is_(True),
            )
            .group_by(DeviceModule.version)
            .order_by(DeviceModule.version.asc())
        )
        target_count = await self._discover_target_count()
        return {
            "provider_id": RUNNER_MODULE_NAME,
            "module_name": RUNNER_MODULE_NAME,
            "installed_active_devices": int(active_count or 0),
            "rollout_targets": target_count,
            "versions": [{"version": version, "count": int(count)} for version, count in versions.all()],
            "latest_plan": await self._serialize_plan(latest_plan) if latest_plan is not None else None,
        }

    async def create_plan(
        self,
        *,
        target_version: str,
        rollback_version: Optional[str] = None,
        target_device_ids: Optional[Iterable[str]] = None,
        canary_size: int = 1,
        wave_size: int = 10,
        max_concurrency: int = 10,
        actor: Optional[str] = None,
    ) -> dict[str, Any]:
        target_version = str(target_version or "").strip()
        rollback_version = str(rollback_version or "").strip() or None
        if not target_version:
            raise RunnerRolloutError("target_version is required")
        await self._validate_runner_module(target_version)
        if rollback_version:
            await self._validate_runner_module(rollback_version)

        devices = await self._normalize_target_devices(target_device_ids)
        if not devices:
            raise RunnerRolloutError("at least one target device is required")

        now = datetime.now(timezone.utc)
        plan = RunnerRolloutPlan(
            id=str(uuid.uuid4()),
            module_name=RUNNER_MODULE_NAME,
            target_version=target_version,
            rollback_version=rollback_version,
            status="draft",
            strategy="canary_waves",
            canary_size=max(1, int(canary_size or 1)),
            wave_size=max(1, int(wave_size or 1)),
            max_concurrency=max(1, int(max_concurrency or 1)),
            created_by=actor,
            created_at=now,
            updated_at=now,
            metadata_json={},
        )
        self.session.add(plan)
        await self.session.flush()
        for device_id in devices:
            current = await self._active_runner_version(device_id)
            self.session.add(
                RunnerRolloutTarget(
                    id=str(uuid.uuid4()),
                    plan_id=plan.id,
                    device_id=device_id,
                    module_name=RUNNER_MODULE_NAME,
                    target_version=target_version,
                    rollback_version=rollback_version or current,
                    current_version=current,
                    status="pending",
                )
            )
        await self._add_event(plan.id, "plan.created", f"Runner rollout plan created for {target_version}.", actor=actor)
        await self.session.flush()
        return await self._serialize_plan(plan)

    async def start_canary(self, plan_id: str, *, actor: Optional[str] = None) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        if plan.status not in {"draft", "paused"}:
            raise RunnerRolloutStateError(f"Cannot start canary while plan is {plan.status}.")
        pending = await self._pending_targets(plan.id)
        if not pending:
            raise RunnerRolloutStateError("No pending targets for canary.")
        count = min(plan.canary_size, plan.max_concurrency, len(pending))
        wave = await self._create_wave(plan, 1, pending[:count], actor=actor)
        now = datetime.now(timezone.utc)
        plan.status = "active"
        plan.started_at = plan.started_at or now
        plan.paused_at = None
        await self._start_wave_targets(plan, wave, actor=actor)
        await self._add_event(plan.id, "plan.canary_started", "Canary wave started.", wave_id=wave.id, actor=actor)
        await self.session.flush()
        return await self.refresh_plan(plan.id)

    async def promote_next_wave(self, plan_id: str, *, actor: Optional[str] = None) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        if plan.status != "active":
            raise RunnerRolloutStateError(f"Cannot promote wave while plan is {plan.status}.")
        await self.refresh_plan(plan.id)
        current_wave = await self._current_wave(plan.id)
        if current_wave is None:
            raise RunnerRolloutStateError("Canary must be started before promotion.")
        if current_wave.status != "completed":
            raise RunnerRolloutStateError("Current wave must complete before promotion.")
        pending = await self._pending_targets(plan.id)
        if not pending:
            plan.status = "completed"
            plan.completed_at = datetime.now(timezone.utc)
            await self._add_event(plan.id, "plan.completed", "Runner rollout completed.", actor=actor)
            await self.session.flush()
            return await self._serialize_plan(plan)
        count = min(plan.wave_size, plan.max_concurrency, len(pending))
        wave = await self._create_wave(plan, current_wave.wave_index + 1, pending[:count], actor=actor)
        await self._start_wave_targets(plan, wave, actor=actor)
        await self._add_event(plan.id, "plan.wave_promoted", f"Wave {wave.wave_index} started.", wave_id=wave.id, actor=actor)
        await self.session.flush()
        return await self.refresh_plan(plan.id)

    async def pause_plan(self, plan_id: str, *, actor: Optional[str] = None) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        if plan.status != "active":
            raise RunnerRolloutStateError(f"Cannot pause plan while it is {plan.status}.")
        plan.status = "paused"
        plan.paused_at = datetime.now(timezone.utc)
        await self._add_event(plan.id, "plan.paused", "Runner rollout paused.", actor=actor)
        await self.session.flush()
        return await self._serialize_plan(plan)

    async def resume_plan(self, plan_id: str, *, actor: Optional[str] = None) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        if plan.status != "paused":
            raise RunnerRolloutStateError(f"Cannot resume plan while it is {plan.status}.")
        plan.status = "active"
        plan.paused_at = None
        await self._add_event(plan.id, "plan.resumed", "Runner rollout resumed.", actor=actor)
        await self.session.flush()
        return await self.refresh_plan(plan.id)

    async def rollback_plan(self, plan_id: str, *, actor: Optional[str] = None, reason: Optional[str] = None) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        if plan.status not in {"active", "paused", "completed", "failed"}:
            raise RunnerRolloutStateError(f"Cannot rollback plan while it is {plan.status}.")
        started = await self._started_targets(plan.id)
        if not started:
            raise RunnerRolloutStateError("No started targets to roll back.")
        now = datetime.now(timezone.utc)
        plan.status = "rolling_back"
        plan.rolled_back_at = now
        for target in started:
            rollback_version = target.rollback_version or plan.rollback_version
            if not rollback_version:
                target.status = "failed"
                target.failed_at = now
                target.last_error_code = "ROLLBACK_VERSION_MISSING"
                target.last_error_message = "Rollback version is not recorded for target."
                continue
            await set_desired_installed(
                device_id=target.device_id,
                module_name=RUNNER_MODULE_NAME,
                desired_version=rollback_version,
                reason="runner_rollback",
                updated_by=actor,
                session=self.session,
            )
            stats = await reconcile_device(target.device_id, self.state, session=self.session, reason="runner_rollback")
            target.status = "rollback_desired"
            target.rolled_back_at = now
            target.operation_id = self._operation_id_from_reconcile(stats) or target.operation_id
            target.metadata_json = {**(target.metadata_json or {}), "rollback_reconcile": stats, "rollback_reason": reason}
        await self._add_event(plan.id, "plan.rollback_started", reason or "Runner rollout rollback started.", actor=actor)
        await self.session.flush()
        return await self._serialize_plan(plan)

    async def refresh_plan(self, plan_id: str) -> dict[str, Any]:
        plan = await self._require_plan(plan_id)
        targets = await self._targets(plan.id)
        now = datetime.now(timezone.utc)
        for target in targets:
            active = await self._active_runner_row(target.device_id)
            if active is None:
                continue
            target.current_version = active.version
            if plan.status == "rolling_back" and target.status in {"rollback_desired", "rolling_back"}:
                if target.rollback_version and active.version == target.rollback_version and active.installed and active.active:
                    target.status = "rolled_back"
                    target.completed_at = now
                continue
            if active.version == target.target_version and active.installed and active.active:
                target.status = "succeeded"
                target.completed_at = target.completed_at or now
                target.last_error_code = None
                target.last_error_message = None
            elif active.state == "failed" and active.version == target.target_version:
                target.status = "failed"
                target.failed_at = target.failed_at or now
                target.last_error_code = active.last_error_code
                target.last_error_message = active.last_error_message

        waves = await self._waves(plan.id)
        for wave in waves:
            wave_targets = [target for target in targets if target.wave_id == wave.id]
            if not wave_targets:
                continue
            statuses = {target.status for target in wave_targets}
            if statuses <= {"succeeded"}:
                wave.status = "completed"
                wave.completed_at = wave.completed_at or now
            elif "failed" in statuses:
                wave.status = "failed"
                wave.completed_at = wave.completed_at or now
            elif any(status in {"desired_set", "installing"} for status in statuses):
                wave.status = "running"

        if plan.status == "active":
            target_statuses = {target.status for target in targets}
            if target_statuses and target_statuses <= {"succeeded"}:
                plan.status = "completed"
                plan.completed_at = plan.completed_at or now
            elif "failed" in target_statuses:
                plan.status = "failed"
                plan.completed_at = plan.completed_at or now
        elif plan.status == "rolling_back":
            started = [target for target in targets if target.status in {"rollback_desired", "rolled_back", "failed"}]
            if started and all(target.status in {"rolled_back", "failed"} for target in started):
                plan.status = "rolled_back"
                plan.completed_at = plan.completed_at or now
        await self.session.flush()
        return await self._serialize_plan(plan)

    async def list_plans(self) -> list[dict[str, Any]]:
        rows = await self.session.execute(
            select(RunnerRolloutPlan)
            .where(RunnerRolloutPlan.module_name == RUNNER_MODULE_NAME)
            .order_by(RunnerRolloutPlan.created_at.desc())
        )
        return [await self._serialize_plan(row) for row in rows.scalars().all()]

    async def get_plan(self, plan_id: str) -> dict[str, Any]:
        return await self._serialize_plan(await self._require_plan(plan_id))

    async def _validate_runner_module(self, version: str) -> Module:
        module = await self.session.get(Module, (RUNNER_MODULE_NAME, version))
        if module is None:
            raise RunnerRolloutError(f"Runner module {RUNNER_MODULE_NAME}@{version} is not present in the module registry.")
        manifest = get_module_manifest(module)
        owner_scope = str(manifest.get("owner_scope") or "").lower()
        if owner_scope not in {"core", "platform"}:
            raise RunnerRolloutError("Agent Recipe Runner rollout requires owner_scope core/platform.")
        if not (manifest.get("system_module") is True or manifest.get("protected") is True):
            raise RunnerRolloutError("Agent Recipe Runner rollout requires protected/system module manifest.")
        return module

    async def _normalize_target_devices(self, device_ids: Optional[Iterable[str]]) -> list[str]:
        if device_ids is None:
            rows = await self.session.execute(
                select(DeviceModule.device_id)
                .where(DeviceModule.module_name == RUNNER_MODULE_NAME, DeviceModule.installed.is_(True))
                .distinct()
                .order_by(DeviceModule.device_id.asc())
            )
            return [str(item) for item in rows.scalars().all()]
        unique = []
        seen = set()
        for raw in device_ids:
            device_id = str(raw or "").strip()
            if device_id and device_id not in seen:
                seen.add(device_id)
                unique.append(device_id)
        if not unique:
            return []
        existing = await self.session.execute(select(Device.device_id).where(Device.device_id.in_(unique)))
        existing_ids = {str(item) for item in existing.scalars().all()}
        missing = [device_id for device_id in unique if device_id not in existing_ids]
        if missing:
            raise RunnerRolloutError(f"Unknown rollout target devices: {', '.join(missing)}")
        return unique

    async def _discover_target_count(self) -> int:
        value = await self.session.scalar(
            select(func.count(func.distinct(DeviceModule.device_id))).where(
                DeviceModule.module_name == RUNNER_MODULE_NAME,
                DeviceModule.installed.is_(True),
            )
        )
        return int(value or 0)

    async def _require_plan(self, plan_id: str) -> RunnerRolloutPlan:
        plan = await self.session.get(RunnerRolloutPlan, str(plan_id))
        if plan is None:
            raise RunnerRolloutError("Runner rollout plan not found.")
        return plan

    async def _create_wave(
        self,
        plan: RunnerRolloutPlan,
        wave_index: int,
        targets: list[RunnerRolloutTarget],
        *,
        actor: Optional[str],
    ) -> RunnerRolloutWave:
        wave = RunnerRolloutWave(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            wave_index=wave_index,
            status="pending",
        )
        self.session.add(wave)
        await self.session.flush()
        for target in targets:
            target.wave_id = wave.id
        await self._add_event(plan.id, "wave.created", f"Wave {wave_index} created.", wave_id=wave.id, actor=actor)
        return wave

    async def _start_wave_targets(self, plan: RunnerRolloutPlan, wave: RunnerRolloutWave, *, actor: Optional[str]) -> None:
        targets = await self._targets(plan.id, wave_id=wave.id)
        target_module = await self._validate_runner_module(plan.target_version)
        now = datetime.now(timezone.utc)
        wave.status = "running"
        wave.started_at = wave.started_at or now
        for target in targets:
            await set_desired_installed(
                device_id=target.device_id,
                module_name=RUNNER_MODULE_NAME,
                desired_version=plan.target_version,
                desired_sha256=target_module.sha256,
                reason="runner_rollout",
                updated_by=actor,
                session=self.session,
            )
            stats = await reconcile_device(target.device_id, self.state, session=self.session, reason="runner_rollout")
            target.status = "desired_set"
            target.desired_set_at = now
            target.started_at = target.started_at or now
            target.operation_id = self._operation_id_from_reconcile(stats)
            target.metadata_json = {**(target.metadata_json or {}), "reconcile": stats}

    def _operation_id_from_reconcile(self, stats: object) -> Optional[str]:
        if not isinstance(stats, dict):
            return None
        for item in stats.get("operations") or []:
            if isinstance(item, dict) and item.get("command") == "install_module_package":
                operation_id = str(item.get("operation_id") or "").strip()
                if operation_id:
                    return operation_id
        return None

    async def _pending_targets(self, plan_id: str) -> list[RunnerRolloutTarget]:
        rows = await self.session.execute(
            select(RunnerRolloutTarget)
            .where(RunnerRolloutTarget.plan_id == plan_id, RunnerRolloutTarget.status == "pending")
            .order_by(RunnerRolloutTarget.created_at.asc())
        )
        return list(rows.scalars().all())

    async def _started_targets(self, plan_id: str) -> list[RunnerRolloutTarget]:
        rows = await self.session.execute(
            select(RunnerRolloutTarget)
            .where(RunnerRolloutTarget.plan_id == plan_id, RunnerRolloutTarget.status.in_(TARGET_STARTED_STATUSES))
            .order_by(RunnerRolloutTarget.created_at.asc())
        )
        return list(rows.scalars().all())

    async def _targets(self, plan_id: str, *, wave_id: Optional[str] = None) -> list[RunnerRolloutTarget]:
        stmt = select(RunnerRolloutTarget).where(RunnerRolloutTarget.plan_id == plan_id)
        if wave_id is not None:
            stmt = stmt.where(RunnerRolloutTarget.wave_id == wave_id)
        stmt = stmt.order_by(RunnerRolloutTarget.created_at.asc())
        rows = await self.session.execute(stmt)
        return list(rows.scalars().all())

    async def _waves(self, plan_id: str) -> list[RunnerRolloutWave]:
        rows = await self.session.execute(
            select(RunnerRolloutWave).where(RunnerRolloutWave.plan_id == plan_id).order_by(RunnerRolloutWave.wave_index.asc())
        )
        return list(rows.scalars().all())

    async def _current_wave(self, plan_id: str) -> Optional[RunnerRolloutWave]:
        return await self.session.scalar(
            select(RunnerRolloutWave)
            .where(RunnerRolloutWave.plan_id == plan_id)
            .order_by(RunnerRolloutWave.wave_index.desc())
            .limit(1)
        )

    async def _active_runner_version(self, device_id: str) -> Optional[str]:
        row = await self._active_runner_row(device_id)
        return row.version if row is not None else None

    async def _active_runner_row(self, device_id: str) -> Optional[DeviceModule]:
        return await self.session.scalar(
            select(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == RUNNER_MODULE_NAME,
                DeviceModule.installed.is_(True),
                DeviceModule.active.is_(True),
            )
            .order_by(DeviceModule.last_updated_at.desc())
            .limit(1)
        )

    async def _add_event(
        self,
        plan_id: str,
        event_type: str,
        message: Optional[str] = None,
        *,
        wave_id: Optional[str] = None,
        target_id: Optional[str] = None,
        actor: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.session.add(
            RunnerRolloutEvent(
                plan_id=plan_id,
                wave_id=wave_id,
                target_id=target_id,
                event_type=event_type,
                message=message,
                actor=actor,
                metadata_json=dict(metadata or {}),
            )
        )

    async def _serialize_plan(self, plan: RunnerRolloutPlan) -> dict[str, Any]:
        waves = await self._waves(plan.id)
        targets = await self._targets(plan.id)
        targets_by_wave: dict[Optional[str], list[RunnerRolloutTarget]] = {}
        for target in targets:
            targets_by_wave.setdefault(target.wave_id, []).append(target)
        wave_payloads = [self._serialize_wave(wave, targets_by_wave.get(wave.id, [])) for wave in waves]
        current_wave = next((item for item in reversed(wave_payloads) if item["status"] in {"pending", "running", "completed", "failed"}), None)
        return {
            "plan_id": plan.id,
            "module_name": plan.module_name,
            "target_version": plan.target_version,
            "rollback_version": plan.rollback_version,
            "status": plan.status,
            "strategy": plan.strategy,
            "canary_size": plan.canary_size,
            "wave_size": plan.wave_size,
            "max_concurrency": plan.max_concurrency,
            "target_count": len(targets),
            "created_by": plan.created_by,
            "created_at": self._iso(plan.created_at),
            "started_at": self._iso(plan.started_at),
            "completed_at": self._iso(plan.completed_at),
            "rolled_back_at": self._iso(plan.rolled_back_at),
            "waves": wave_payloads,
            "targets": [self._serialize_target(target) for target in targets],
            "current_wave": current_wave,
            "summary": self._summary(targets),
            "metadata": plan.metadata_json or {},
        }

    def _serialize_wave(self, wave: RunnerRolloutWave, targets: list[RunnerRolloutTarget]) -> dict[str, Any]:
        return {
            "wave_id": wave.id,
            "wave_index": wave.wave_index,
            "status": wave.status,
            "target_count": len(targets),
            "started_at": self._iso(wave.started_at),
            "completed_at": self._iso(wave.completed_at),
            "targets": [self._serialize_target(target) for target in targets],
        }

    def _serialize_target(self, target: RunnerRolloutTarget) -> dict[str, Any]:
        return {
            "target_id": target.id,
            "device_id": target.device_id,
            "wave_id": target.wave_id,
            "module_name": target.module_name,
            "target_version": target.target_version,
            "rollback_version": target.rollback_version,
            "status": target.status,
            "current_version": target.current_version,
            "operation_id": target.operation_id,
            "last_error_code": target.last_error_code,
            "last_error_message": target.last_error_message,
            "desired_set_at": self._iso(target.desired_set_at),
            "completed_at": self._iso(target.completed_at),
        }

    def _summary(self, targets: list[RunnerRolloutTarget]) -> dict[str, int]:
        result: dict[str, int] = {}
        for target in targets:
            result[target.status] = result.get(target.status, 0) + 1
        return result

    def _iso(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value is not None else None
