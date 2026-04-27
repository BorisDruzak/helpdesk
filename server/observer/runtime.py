from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy import and_, delete, distinct, exists, func, or_, select

from app.db import get_session
from app.db.models import AgentObserverEvent, AgentRuntimeAudit, DeviceEvent, ObserverTrace, Operation, PlaybookRun, PlaybookStepRun, Ticket, TicketEvent
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.observer_settings_repo import DEFAULT_OBSERVER_SETTINGS, ObserverSettingsRepo
from observer.service import ObserverOverlayService, _playbook_run_trace_id, _runtime_audit_trace_id


OBSERVER_RUNTIME_AUDIT_DEVICE_ID = "00000000-0000-0000-0000-00000000b0b0"


@dataclass(slots=True)
class ObserverRefreshStats:
    started_at: Optional[datetime] = None
    last_scan_started_at: Optional[datetime] = None
    last_scan_completed_at: Optional[datetime] = None
    last_backfill_scan_started_at: Optional[datetime] = None
    last_backfill_scan_completed_at: Optional[datetime] = None
    last_projected_at: Optional[datetime] = None
    last_cleanup_at: Optional[datetime] = None
    last_settings_loaded_at: Optional[datetime] = None
    last_error: Optional[str] = None
    discovered_trace_count: int = 0
    discovered_backfill_trace_count: int = 0
    projected_trace_count: int = 0
    deleted_trace_count: int = 0
    sampled_out_trace_count: int = 0
    consecutive_failures: int = 0
    pending_trace_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_scan_started_at": self.last_scan_started_at.isoformat() if self.last_scan_started_at else None,
            "last_scan_completed_at": self.last_scan_completed_at.isoformat() if self.last_scan_completed_at else None,
            "last_backfill_scan_started_at": self.last_backfill_scan_started_at.isoformat() if self.last_backfill_scan_started_at else None,
            "last_backfill_scan_completed_at": self.last_backfill_scan_completed_at.isoformat() if self.last_backfill_scan_completed_at else None,
            "last_projected_at": self.last_projected_at.isoformat() if self.last_projected_at else None,
            "last_cleanup_at": self.last_cleanup_at.isoformat() if self.last_cleanup_at else None,
            "last_settings_loaded_at": self.last_settings_loaded_at.isoformat() if self.last_settings_loaded_at else None,
            "last_error": self.last_error,
            "discovered_trace_count": self.discovered_trace_count,
            "discovered_backfill_trace_count": self.discovered_backfill_trace_count,
            "projected_trace_count": self.projected_trace_count,
            "deleted_trace_count": self.deleted_trace_count,
            "sampled_out_trace_count": self.sampled_out_trace_count,
            "consecutive_failures": self.consecutive_failures,
            "pending_trace_count": self.pending_trace_count,
        }


class ObserverRefreshRuntime:
    """Background incremental projector for hot observer traces."""

    def __init__(
        self,
        *,
        scan_interval_sec: float = 2.0,
        scan_overlap_sec: float = 2.0,
        bootstrap_lookback_sec: float = 30.0,
        debounce_sec: float = 0.25,
        max_batch: int = 100,
        historical_backfill_enabled: bool = True,
    ) -> None:
        self.scan_interval_sec = max(scan_interval_sec, 0.05)
        self.scan_overlap_sec = max(scan_overlap_sec, 0.0)
        self.bootstrap_lookback_sec = max(bootstrap_lookback_sec, 1.0)
        self.debounce_sec = max(debounce_sec, 0.0)
        self.max_batch = max(max_batch, 1)
        self.historical_backfill_enabled = bool(historical_backfill_enabled)
        self._task: Optional[asyncio.Task[None]] = None
        self._pending: dict[str, float] = {}
        self._pending_lock = asyncio.Lock()
        self._last_scan_at: Optional[datetime] = None
        self._stats = ObserverRefreshStats()
        self._settings: dict[str, Any] = dict(DEFAULT_OBSERVER_SETTINGS)
        self._last_self_health_key: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status_snapshot(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        last_projected_age_sec = None
        if self._stats.last_projected_at:
            last_projected_age_sec = max(0, int((now - self._stats.last_projected_at).total_seconds()))
        health_status = "ok"
        issues: list[str] = []
        if self._stats.last_error:
            health_status = "degraded"
            issues.append("last_error")
        if self._stats.pending_trace_count > self.max_batch * 4:
            health_status = "degraded"
            issues.append("pending_backlog")
        if self.running and last_projected_age_sec is not None and last_projected_age_sec > int(self.scan_interval_sec * 20):
            health_status = "degraded"
            issues.append("projection_lag")
        return {
            "enabled": True,
            "running": self.running,
            "config": {
                "scan_interval_sec": self.scan_interval_sec,
                "scan_overlap_sec": self.scan_overlap_sec,
                "bootstrap_lookback_sec": self.bootstrap_lookback_sec,
                "debounce_sec": self.debounce_sec,
                "max_batch": self.max_batch,
                "historical_backfill_enabled": self.historical_backfill_enabled,
            },
            "settings": dict(self._settings),
            "health": {
                "status": health_status,
                "issues": issues,
                "pending_trace_count": self._stats.pending_trace_count,
                "last_projected_age_sec": last_projected_age_sec,
            },
            "stats": self._stats.to_dict(),
        }

    async def reload_settings(self) -> dict[str, Any]:
        async with get_session() as session:
            settings = await ObserverSettingsRepo(session).get_settings()
            await session.commit()
        self._settings = dict(settings)
        self.historical_backfill_enabled = bool(settings.get("historical_backfill_enabled", self.historical_backfill_enabled))
        self._stats.last_settings_loaded_at = datetime.now(timezone.utc)
        return dict(self._settings)

    async def start(self) -> None:
        if self.running:
            return
        await self.reload_settings()
        self._stats.started_at = datetime.now(timezone.utc)
        self._stats.last_error = None
        self._last_scan_at = self._stats.started_at - timedelta(seconds=self.bootstrap_lookback_sec)
        self._task = asyncio.create_task(self._run_loop(), name="observer-refresh-runtime")
        logger.info("[observer_refresh] runtime started")

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
            async with self._pending_lock:
                self._pending.clear()
                self._stats.pending_trace_count = 0
        logger.info("[observer_refresh] runtime stopped")

    async def enqueue_trace(self, trace_id: Optional[str], *, delay_sec: Optional[float] = None) -> bool:
        trace_value = (trace_id or "").strip()
        if not trace_value:
            return False
        due_at = asyncio.get_running_loop().time() + (self.debounce_sec if delay_sec is None else max(delay_sec, 0.0))
        async with self._pending_lock:
            current = self._pending.get(trace_value)
            if current is None or due_at < current:
                self._pending[trace_value] = due_at
            self._stats.pending_trace_count = len(self._pending)
        return True

    async def run_once(self) -> None:
        await self.reload_settings()
        discovered = await self._discover_recent_trace_ids()
        for trace_id in discovered:
            await self.enqueue_trace(trace_id)
        if self._settings.get("historical_backfill_enabled", self.historical_backfill_enabled):
            historical = await self._discover_historical_trace_ids()
            for trace_id in historical:
                await self.enqueue_trace(trace_id, delay_sec=0.0)
        await self._project_due_traces()
        await self._cleanup_expired_traces()
        await self._emit_self_health_if_degraded()

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._stats.last_error = str(exc)
                self._stats.consecutive_failures += 1
                logger.opt(exception=exc).warning("[observer_refresh] loop failed")
                await self._emit_self_health_if_degraded()
            else:
                self._stats.consecutive_failures = 0
            await asyncio.sleep(self.scan_interval_sec)

    async def _emit_self_health_if_degraded(self) -> Optional[str]:
        snapshot = self.status_snapshot()
        health = snapshot.get("health") or {}
        if health.get("status") != "degraded":
            self._last_self_health_key = None
            return None
        issues = [str(item) for item in (health.get("issues") or []) if str(item or "").strip()]
        issue_key = "|".join(sorted(issues)) or "degraded"
        if self._last_self_health_key == issue_key:
            return None
        self._last_self_health_key = issue_key
        severity = "error" if "last_error" in issues else "warning"
        async with get_session() as session:
            audit = await AgentRuntimeAuditRepo(session).add(
                device_id=OBSERVER_RUNTIME_AUDIT_DEVICE_ID,
                event_type="observer_runtime_degraded",
                severity=severity,
                source="observer_runtime",
                actor_id="system",
                actor_role="system",
                details_json={
                    "issues": issues,
                    "pending_trace_count": health.get("pending_trace_count"),
                    "last_projected_age_sec": health.get("last_projected_age_sec"),
                    "last_error": self._stats.last_error,
                    "consecutive_failures": self._stats.consecutive_failures,
                },
            )
            await session.commit()
        trace_id = _runtime_audit_trace_id(audit.id)
        await self.enqueue_trace(trace_id, delay_sec=0.0)
        return trace_id

    async def _discover_recent_trace_ids(self) -> list[str]:
        now = datetime.now(timezone.utc)
        self._stats.last_scan_started_at = now
        window_start = (self._last_scan_at or now - timedelta(seconds=self.bootstrap_lookback_sec)) - timedelta(
            seconds=self.scan_overlap_sec
        )
        discovered: list[str] = []
        seen: set[str] = set()

        def _remember(values: list[Optional[str]]) -> None:
            for value in values:
                trace_id = (value or "").strip()
                if trace_id and trace_id not in seen:
                    seen.add(trace_id)
                    discovered.append(trace_id)

        async with get_session() as session:
            recent_ticket_ids: list[str] = []

            ticket_id_rows = await session.execute(
                select(distinct(TicketEvent.ticket_id))
                .where(TicketEvent.ticket_id.isnot(None), TicketEvent.created_at >= window_start)
                .limit(self.max_batch * 2)
            )
            recent_ticket_ids.extend([value for value in ticket_id_rows.scalars().all() if value])

            op_ticket_rows = await session.execute(
                select(distinct(Operation.ticket_id))
                .where(
                    Operation.ticket_id.isnot(None),
                    or_(
                        Operation.queued_at >= window_start,
                        Operation.sent_at >= window_start,
                        Operation.accepted_at >= window_start,
                        Operation.started_at >= window_start,
                        Operation.finished_at >= window_start,
                        Operation.cancel_requested_at >= window_start,
                        Operation.canceled_at >= window_start,
                    ),
                )
                .limit(self.max_batch * 2)
            )
            recent_ticket_ids.extend([value for value in op_ticket_rows.scalars().all() if value])

            if recent_ticket_ids:
                ticket_root_rows = await session.execute(
                    select(distinct(Ticket.observer_root_trace_id))
                    .where(Ticket.ticket_id.in_(recent_ticket_ids), Ticket.observer_root_trace_id.isnot(None))
                    .limit(self.max_batch * 2)
                )
                _remember(list(ticket_root_rows.scalars().all()))

            ticket_rows = await session.execute(
                select(distinct(TicketEvent.trace_id))
                .where(TicketEvent.trace_id.isnot(None), TicketEvent.created_at >= window_start)
                .limit(self.max_batch * 2)
            )
            _remember(list(ticket_rows.scalars().all()))

            device_rows = await session.execute(
                select(distinct(DeviceEvent.trace_id))
                .where(DeviceEvent.trace_id.isnot(None), DeviceEvent.created_at >= window_start)
                .limit(self.max_batch * 2)
            )
            _remember(list(device_rows.scalars().all()))

            operation_rows = await session.execute(
                select(distinct(Operation.trace_id))
                .where(
                    Operation.trace_id.isnot(None),
                    or_(
                        Operation.queued_at >= window_start,
                        Operation.sent_at >= window_start,
                        Operation.accepted_at >= window_start,
                        Operation.started_at >= window_start,
                        Operation.finished_at >= window_start,
                        Operation.cancel_requested_at >= window_start,
                        Operation.canceled_at >= window_start,
                    ),
                )
                .limit(self.max_batch * 2)
            )
            _remember(list(operation_rows.scalars().all()))

            audit_operation_rows = await session.execute(
                select(distinct(AgentRuntimeAudit.operation_id))
                .where(AgentRuntimeAudit.created_at >= window_start, AgentRuntimeAudit.operation_id.isnot(None))
                .limit(self.max_batch * 2)
            )
            audit_operation_ids = [value for value in audit_operation_rows.scalars().all() if value]
            if audit_operation_ids:
                audit_trace_rows = await session.execute(
                    select(distinct(Operation.trace_id))
                    .where(Operation.trace_id.isnot(None), Operation.operation_id.in_(audit_operation_ids))
                    .limit(self.max_batch * 2)
                )
                _remember(list(audit_trace_rows.scalars().all()))

            agent_event_rows = await session.execute(
                select(distinct(AgentObserverEvent.trace_id))
                .where(AgentObserverEvent.trace_id.isnot(None), AgentObserverEvent.created_at >= window_start)
                .limit(self.max_batch * 2)
            )
            _remember(list(agent_event_rows.scalars().all()))

            playbook_run_rows = await session.execute(
                select(distinct(PlaybookRun.id))
                .where(
                    or_(
                        PlaybookRun.scheduled_at >= window_start,
                        PlaybookRun.started_at >= window_start,
                        PlaybookRun.finished_at >= window_start,
                    )
                )
                .limit(self.max_batch * 2)
            )
            _remember([_playbook_run_trace_id(item) for item in playbook_run_rows.scalars().all()])

            playbook_step_rows = await session.execute(
                select(distinct(PlaybookStepRun.playbook_run_id))
                .where(
                    or_(
                        PlaybookStepRun.started_at >= window_start,
                        PlaybookStepRun.finished_at >= window_start,
                    )
                )
                .limit(self.max_batch * 2)
            )
            _remember([_playbook_run_trace_id(item) for item in playbook_step_rows.scalars().all()])

        self._last_scan_at = now
        self._stats.last_scan_completed_at = datetime.now(timezone.utc)
        self._stats.discovered_trace_count = len(discovered)
        return discovered[: self.max_batch * 2]

    async def _discover_historical_trace_ids(self) -> list[str]:
        self._stats.last_backfill_scan_started_at = datetime.now(timezone.utc)
        discovered: list[str] = []
        seen: set[str] = set()

        def _remember(values: list[Optional[str]]) -> None:
            for value in values:
                trace_id = str(value or "").strip()
                if trace_id and trace_id not in seen:
                    seen.add(trace_id)
                    discovered.append(trace_id)

        async with self._pending_lock:
            if len(self._pending) >= self.max_batch * 4:
                self._stats.discovered_backfill_trace_count = 0
                self._stats.last_backfill_scan_completed_at = datetime.now(timezone.utc)
                return []

        async with get_session() as session:
            ticket_root_rows = await session.execute(
                select(Ticket.observer_root_trace_id)
                .where(
                    Ticket.observer_root_trace_id.isnot(None),
                    ~exists(select(ObserverTrace.trace_id).where(ObserverTrace.trace_id == Ticket.observer_root_trace_id)),
                )
                .order_by(Ticket.created_at.asc())
                .limit(self.max_batch * 2)
            )
            _remember(list(ticket_root_rows.scalars().all()))

            op_rows = await session.execute(
                select(Operation.trace_id)
                .where(
                    Operation.trace_id.isnot(None),
                    Operation.ticket_id.is_(None),
                    ~exists(select(ObserverTrace.trace_id).where(ObserverTrace.trace_id == Operation.trace_id)),
                )
                .group_by(Operation.trace_id)
                .order_by(func.min(Operation.queued_at).asc())
                .limit(self.max_batch * 2)
            )
            _remember(list(op_rows.scalars().all()))

            orphan_ticket_rows = await session.execute(
                select(TicketEvent.trace_id)
                .where(
                    TicketEvent.trace_id.isnot(None),
                    ~exists(select(ObserverTrace.trace_id).where(ObserverTrace.trace_id == TicketEvent.trace_id)),
                )
                .group_by(TicketEvent.trace_id)
                .order_by(func.min(TicketEvent.created_at).asc())
                .limit(self.max_batch * 2)
            )
            _remember(list(orphan_ticket_rows.scalars().all()))

            agent_event_rows = await session.execute(
                select(AgentObserverEvent.trace_id)
                .where(
                    AgentObserverEvent.trace_id.isnot(None),
                    ~exists(select(ObserverTrace.trace_id).where(ObserverTrace.trace_id == AgentObserverEvent.trace_id)),
                )
                .group_by(AgentObserverEvent.trace_id)
                .order_by(func.min(AgentObserverEvent.created_at).asc())
                .limit(self.max_batch * 2)
            )
            _remember(list(agent_event_rows.scalars().all()))

            playbook_rows = await session.execute(
                select(PlaybookRun.id)
                .order_by(PlaybookRun.scheduled_at.asc())
                .limit(self.max_batch * 2)
            )
            _remember([_playbook_run_trace_id(item) for item in playbook_rows.scalars().all()])

        self._stats.discovered_backfill_trace_count = len(discovered)
        self._stats.last_backfill_scan_completed_at = datetime.now(timezone.utc)
        return discovered[: self.max_batch * 2]

    async def _project_due_traces(self) -> None:
        now_monotonic = asyncio.get_running_loop().time()
        async with self._pending_lock:
            due_trace_ids = sorted(
                [trace_id for trace_id, due_at in self._pending.items() if due_at <= now_monotonic]
            )[: self.max_batch]
            for trace_id in due_trace_ids:
                self._pending.pop(trace_id, None)
            self._stats.pending_trace_count = len(self._pending)

        if not due_trace_ids:
            return

        projected = 0
        for trace_id in due_trace_ids:
            try:
                async with get_session() as session:
                    service = ObserverOverlayService(session)
                    trace = await service.project_trace(trace_id, force=False)
                    if trace is not None and self._should_sample_out_trace(trace):
                        await session.execute(delete(ObserverTrace).where(ObserverTrace.trace_id == trace_id))
                        self._stats.sampled_out_trace_count += 1
                    else:
                        projected += 1
                    await session.commit()
            except Exception as exc:
                self._stats.last_error = str(exc)
                logger.opt(exception=exc).warning(
                    "[observer_refresh] failed to project trace_id={}",
                    trace_id,
                )
                await self.enqueue_trace(trace_id, delay_sec=max(self.scan_interval_sec, 0.25))

        if projected:
            self._stats.projected_trace_count += projected
            self._stats.last_projected_at = datetime.now(timezone.utc)

    def _should_sample_out_trace(self, trace: ObserverTrace) -> bool:
        sample_rate = float(self._settings.get("success_trace_sample_rate", 1.0) or 0.0)
        if sample_rate >= 1.0:
            return False
        if trace.status != "ok" or int(trace.error_count or 0) > 0:
            return False
        keep_root_kinds = {
            str(item).strip()
            for item in (self._settings.get("always_keep_root_kinds") or [])
            if str(item or "").strip()
        }
        if str(trace.root_kind or "").strip() in keep_root_kinds:
            return False
        if sample_rate <= 0:
            return True
        bucket = int.from_bytes(hashlib.blake2b(trace.trace_id.encode("utf-8"), digest_size=8).digest(), "big") / float(2**64)
        return bucket > sample_rate

    async def _cleanup_expired_traces(self) -> None:
        ok_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=int(self._settings.get("ok_trace_retention_hours", DEFAULT_OBSERVER_SETTINGS["ok_trace_retention_hours"]))
        )
        error_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=int(self._settings.get("error_trace_retention_hours", DEFAULT_OBSERVER_SETTINGS["error_trace_retention_hours"]))
        )
        async with get_session() as session:
            delete_result = await session.execute(
                delete(ObserverTrace).where(
                    or_(
                        and_(ObserverTrace.status.in_(["ok", "canceled"]), ObserverTrace.started_at < ok_cutoff),
                        and_(ObserverTrace.status == "error", ObserverTrace.started_at < error_cutoff),
                    )
                )
            )
            await session.commit()
        deleted_count = int(delete_result.rowcount or 0)
        if deleted_count:
            self._stats.deleted_trace_count += deleted_count
        self._stats.last_cleanup_at = datetime.now(timezone.utc)
