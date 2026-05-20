from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRuntimeAudit,
    AgentToken,
    ConnectionRequest,
    Device,
    DeviceDesiredModule,
    DeviceModule,
    DeviceOutbox,
    Operation,
    ObserverTrace,
    RemoteAccessSession,
    Ticket,
)
from app.repos.devices_repo import DevicesRepo
from app.repos.remote_access_repo import ACTIVE_REMOTE_ACCESS_STATUSES
from inventory.service import DeviceInventoryService
from web_api.dto.device_operations import (
    DeviceOperationsAgent,
    DeviceOperationsBinding,
    DeviceOperationsDevice,
    DeviceOperationsInventory,
    DeviceOperationsLinks,
    DeviceOperationsModuleItem,
    DeviceOperationsModules,
    DeviceOperationsObserver,
    DeviceOperationsObserverItem,
    DeviceOperationsOperationItem,
    DeviceOperationsOperations,
    DeviceOperationsOutbox,
    DeviceOperationsOutboxItem,
    DeviceOperationsPayload,
    DeviceOperationsProvisioning,
    DeviceOperationsRefreshPolicy,
    DeviceOperationsRefreshRun,
    DeviceOperationsRemoteAssist,
    DeviceOperationsSignals,
)


ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
FAILED_OPERATION_STATUSES = {"failed", "timed_out"}
STALE_INVENTORY_AFTER = timedelta(days=7)
OFFLINE_AFTER = timedelta(minutes=15)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, int((now - value).total_seconds()))


def _error_summary(*values: Any) -> str | None:
    for value in values:
        text = _string(value)
        if text:
            return text[:500]
    return None


def _connection_state(device: Device, *, state: Any, now: datetime) -> str:
    device_id = str(getattr(device, "device_id", "") or "")
    if state is not None and hasattr(state, "is_agent_online"):
        try:
            return "online" if state.is_agent_online(device_id) else "offline"
        except Exception:
            pass
    last_seen = getattr(device, "last_seen_at", None)
    if last_seen is None:
        return "unknown"
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return "offline" if now - last_seen > OFFLINE_AFTER else "unknown"


def _device_metadata(device: Device) -> dict[str, Any]:
    return _dict(getattr(device, "device_metadata", None))


def _safe_summary(snapshot: Any) -> dict[str, Any] | str | None:
    normalized = _dict(getattr(snapshot, "normalized", None))
    summary = normalized.get("summary")
    if isinstance(summary, dict):
        return summary
    if summary:
        return str(summary)
    raw_summary = getattr(snapshot, "summary", None)
    if raw_summary:
        return str(raw_summary)
    return None


def _module_key(value: Any) -> str:
    return str(getattr(value, "module_name", "") or "").strip()


def _module_last_error(row: DeviceModule | None) -> str | None:
    if row is None:
        return None
    return _error_summary(getattr(row, "last_error_message", None), getattr(row, "last_error_code", None))


def _operation_started_at(row: Operation) -> datetime | None:
    return getattr(row, "started_at", None) or getattr(row, "accepted_at", None) or getattr(row, "queued_at", None)


def _operation_duration_ms(row: Operation) -> int | None:
    started = _operation_started_at(row)
    finished = getattr(row, "finished_at", None)
    if not started or not finished:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    return max(0, int((finished - started).total_seconds() * 1000))


class DeviceOperationsNotFound(LookupError):
    pass


class DeviceOperationsService:
    def __init__(self, session: AsyncSession, *, state: Any = None):
        self.session = session
        self.state = state

    async def build_payload(
        self,
        device_id: str,
        *,
        include_traces: bool = True,
        include_outbox: bool = True,
        include_history: bool = False,
        trace_limit: int = 10,
        outbox_limit: int = 20,
        operation_limit: int = 20,
    ) -> DeviceOperationsPayload:
        now = datetime.now(timezone.utc)
        device = await DevicesRepo(self.session).get_by_device_id(device_id, include_deleted=False)
        if device is None:
            raise DeviceOperationsNotFound(device_id)

        connection_state = _connection_state(device, state=self.state, now=now)
        metadata = _device_metadata(device)
        inventory_service = DeviceInventoryService(self.session)
        latest_inventory = await inventory_service.get_latest(device_id)
        binding_row = await inventory_service.get_binding(device_id)
        refresh_policy = await inventory_service.get_effective_refresh_policy(device_id)
        refresh_runs = await inventory_service.list_refresh_runs(device_id=device_id, limit=1)
        modules = await self._build_modules(device_id)
        outbox = await self._build_outbox(device_id, include_outbox=include_outbox, limit=outbox_limit)
        operations = await self._build_operations(device_id, limit=operation_limit)
        observer = await self._build_observer(device_id, include_traces=include_traces, limit=trace_limit)
        remote_assist = await self._build_remote_assist(device_id, connection_state=connection_state)
        provisioning = await self._build_provisioning(device_id)
        inventory = self._build_inventory(
            latest_inventory,
            refresh_policy=refresh_policy,
            refresh_run=refresh_runs[0] if refresh_runs else None,
            connection_state=connection_state,
            now=now,
        )
        agent = DeviceOperationsAgent(
            connection_state=connection_state,
            last_seen_at=_iso(getattr(device, "last_seen_at", None)),
            version=_string(getattr(device, "agent_version", None) or metadata.get("agent_version") or metadata.get("version")),
            protocol=_string(getattr(device, "protocol_version", None)),
            capabilities_count=len(_dict(getattr(device, "capabilities", None))),
            toolset_hash=_string(getattr(device, "current_toolset_hash", None)),
            desired_revision=_string(metadata.get("desired_revision") or metadata.get("desired_config_revision")),
            current_revision=_string(metadata.get("current_revision") or metadata.get("config_revision")),
            config_status=_string(metadata.get("config_status")),
            update_status=_string(metadata.get("update_status") or metadata.get("pending_update_status")),
            update_available=bool(metadata.get("update_available")) if "update_available" in metadata else None,
            pending_restart=bool(metadata.get("pending_restart")) if "pending_restart" in metadata else None,
        )
        signals = DeviceOperationsSignals(
            agent_offline=connection_state == "offline",
            stale_inventory=inventory.freshness == "stale",
            missing_inventory=inventory.freshness == "missing",
            update_available=bool(agent.update_available),
            provisioning_error=bool(provisioning and provisioning.last_error and provisioning.state not in {"pending", "approved"}),
            auth_error=bool(provisioning and provisioning.auth_state == "error"),
            module_reconcile_failed=bool((modules.failed_count or 0) > 0),
            outbox_backlog=outbox.pending_count > 0,
            failed_recent_operation=operations.recent_failed_count > 0,
            observer_errors=any((item.status or "").lower() in {"failed", "error"} or item.error_summary for item in observer.items),
            remote_assist_unavailable=remote_assist.availability in {"unavailable", "offline", "unknown"},
        )
        return DeviceOperationsPayload(
            generated_at=now.isoformat(),
            device=DeviceOperationsDevice(
                device_id=device_id,
                hostname=_string(getattr(device, "hostname", None)),
                display_name=_string(getattr(device, "hostname", None) or device_id),
                platform=_string(metadata.get("platform") or metadata.get("os_type") or getattr(device, "os", None)),
                os_name=_string(getattr(device, "os", None) or metadata.get("os_name")),
                os_version=_string(metadata.get("os_version")),
                arch=_string(metadata.get("arch") or metadata.get("architecture")),
                first_seen_at=_iso(getattr(device, "first_seen_at", None)),
                last_seen_at=_iso(getattr(device, "last_seen_at", None)),
                source=_string(metadata.get("source") or metadata.get("machine_id_source")),
                status="archived" if getattr(device, "is_deleted", False) else "active",
            ),
            binding=self._build_binding(binding_row),
            agent=agent,
            provisioning=provisioning,
            inventory=inventory,
            modules=modules,
            outbox=outbox,
            operations=operations,
            observer=observer,
            remote_assist=remote_assist,
            signals=signals,
            links=DeviceOperationsLinks(
                inventory=f"/app/admin/inventory?device={quote(device_id)}",
                device_card=f"/app/admin/device?device={quote(device_id)}",
                agent_updates=f"/app/admin/agent-updates?device={quote(device_id)}",
                modules=f"/app/admin/modules?device={quote(device_id)}",
                observer=f"/app/admin/observer?device_id={quote(device_id)}",
                tickets=f"/app/tickets?search={quote(device_id)}",
                remote_assist=f"/app/tickets?search={quote(device_id)}",
            ),
        )

    def _build_inventory(
        self,
        snapshot: Any,
        *,
        refresh_policy: Any,
        refresh_run: Any,
        connection_state: str,
        now: datetime,
    ) -> DeviceOperationsInventory:
        if snapshot is None:
            return DeviceOperationsInventory(
                freshness="missing",
                can_request_refresh=connection_state == "online",
                refresh_policy=self._build_refresh_policy(refresh_policy),
                latest_refresh_run=self._build_refresh_run(refresh_run),
            )
        collected_at = getattr(snapshot, "collected_at", None)
        age = _age_seconds(now, collected_at)
        freshness = "unknown"
        if age is not None:
            freshness = "stale" if age > int(STALE_INVENTORY_AFTER.total_seconds()) else "fresh"
        return DeviceOperationsInventory(
            latest_snapshot_id=_string(getattr(snapshot, "id", None)),
            collected_at=_iso(collected_at),
            age_seconds=age,
            freshness=freshness,
            summary=_safe_summary(snapshot),
            presentation={"source_tool": _string(getattr(snapshot, "source_tool", None)), "status": _string(getattr(snapshot, "status", None))},
            refresh_policy=self._build_refresh_policy(refresh_policy),
            latest_refresh_run=self._build_refresh_run(refresh_run),
            can_request_refresh=connection_state == "online",
        )

    @staticmethod
    def _build_refresh_policy(row: Any) -> DeviceOperationsRefreshPolicy | None:
        if row is None:
            return None
        return DeviceOperationsRefreshPolicy(
            enabled=bool(getattr(row, "enabled", False)),
            interval_minutes=getattr(row, "interval_minutes", None),
            next_due_at=_iso(getattr(row, "next_due_at", None)),
        )

    @staticmethod
    def _build_refresh_run(row: Any) -> DeviceOperationsRefreshRun | None:
        if row is None:
            return None
        return DeviceOperationsRefreshRun(
            id=_string(getattr(row, "id", None)),
            status=_string(getattr(row, "status", None)),
            requested_at=_iso(getattr(row, "requested_at", None)),
            completed_at=_iso(getattr(row, "completed_at", None)),
            error_summary=_error_summary(getattr(row, "error", None)),
        )

    @staticmethod
    def _build_binding(row: Any) -> DeviceOperationsBinding | None:
        if row is None:
            return None
        return DeviceOperationsBinding(
            responsible_person=_string(getattr(row, "responsible_user", None) or getattr(row, "responsible_user_login", None)),
            department=_string(getattr(row, "department", None)),
            building=_string(getattr(row, "building", None)),
            room=_string(getattr(row, "room", None)),
            inventory_number=_string(getattr(row, "inventory_number", None)),
            status=_string(getattr(row, "status", None)),
            tags=[str(item) for item in (getattr(row, "tags", None) or [])],
            updated_at=_iso(getattr(row, "updated_at", None)),
            updated_by=_string(getattr(row, "updated_by", None)),
        )

    async def _build_modules(self, device_id: str) -> DeviceOperationsModules:
        actual_result = await self.session.execute(select(DeviceModule).where(DeviceModule.device_id == device_id))
        actual_rows = list(actual_result.scalars().all())
        desired_result = await self.session.execute(select(DeviceDesiredModule).where(DeviceDesiredModule.device_id == device_id))
        desired_rows = list(desired_result.scalars().all())
        actual_by_name: dict[str, DeviceModule] = {}
        for row in actual_rows:
            name = _module_key(row)
            if name and (name not in actual_by_name or str(getattr(row, "version", "")) > str(getattr(actual_by_name[name], "version", ""))):
                actual_by_name[name] = row
        desired_by_name = {_module_key(row): row for row in desired_rows if _module_key(row)}
        names = sorted(set(actual_by_name) | set(desired_by_name))
        items: list[DeviceOperationsModuleItem] = []
        missing_count = 0
        outdated_count = 0
        failed_count = 0
        for name in names:
            actual = actual_by_name.get(name)
            desired = desired_by_name.get(name)
            desired_version = _string(getattr(desired, "desired_version", None)) if desired else None
            installed_version = _string(getattr(actual, "version", None)) if actual else None
            actual_state = _string(getattr(actual, "state", None)) if actual else None
            if desired and getattr(desired, "state", None) == "installed" and actual is None:
                missing_count += 1
                state = "missing"
            elif actual_state == "failed":
                failed_count += 1
                state = "failed"
            elif desired_version and installed_version and desired_version != installed_version:
                outdated_count += 1
                state = "outdated"
            else:
                state = actual_state or _string(getattr(desired, "state", None)) or "unknown"
            items.append(
                DeviceOperationsModuleItem(
                    module_id=name,
                    name=name,
                    installed_version=installed_version,
                    desired_version=desired_version,
                    state=state,
                    last_error=_module_last_error(actual),
                    last_seen_at=_iso(getattr(actual, "last_seen_at", None)) if actual else None,
                )
            )
        reconcile_state = "unknown"
        if items:
            reconcile_state = "failed" if failed_count else "warning" if missing_count or outdated_count else "ok"
        return DeviceOperationsModules(
            reconcile_state=reconcile_state,
            module_count=len(actual_rows),
            missing_count=missing_count,
            outdated_count=outdated_count,
            failed_count=failed_count,
            items=items[:50],
        )

    async def _build_outbox(self, device_id: str, *, include_outbox: bool, limit: int) -> DeviceOperationsOutbox:
        pending_count = int(
            await self.session.scalar(
                select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.device_id == device_id, DeviceOutbox.status == "pending")
            )
            or 0
        )
        failed_count = int(
            await self.session.scalar(
                select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.device_id == device_id, DeviceOutbox.status == "failed")
            )
            or 0
        )
        last_ack_at = await self.session.scalar(
            select(func.max(DeviceOutbox.delivered_at)).where(DeviceOutbox.device_id == device_id, DeviceOutbox.delivered_at.isnot(None))
        )
        rows: list[DeviceOutbox] = []
        if include_outbox:
            result = await self.session.execute(
                select(DeviceOutbox)
                .where(DeviceOutbox.device_id == device_id)
                .order_by(DeviceOutbox.created_at.desc(), DeviceOutbox.id.desc())
                .limit(max(1, min(limit, 100)))
            )
            rows = list(result.scalars().all())
        ticket_by_operation = await self._ticket_ids_for_operations([_string(getattr(row, "operation_id", None)) for row in rows])
        return DeviceOperationsOutbox(
            pending_count=pending_count,
            failed_count=failed_count,
            last_ack_at=_iso(last_ack_at),
            items=[
                DeviceOperationsOutboxItem(
                    id=str(row.id),
                    command_type=_string(row.command),
                    status=_string(row.status),
                    created_at=_iso(row.created_at),
                    sent_at=_iso(row.sent_at),
                    ack_at=_iso(row.delivered_at),
                    error_summary=_error_summary(row.error_message, row.error_code),
                    ticket_id=ticket_by_operation.get(str(row.operation_id)) if row.operation_id else None,
                    operation_id=_string(row.operation_id),
                )
                for row in rows
            ],
        )

    async def _ticket_ids_for_operations(self, operation_ids: list[str | None]) -> dict[str, str | None]:
        ids = [item for item in operation_ids if item]
        if not ids:
            return {}
        result = await self.session.execute(select(Operation.operation_id, Operation.ticket_id).where(Operation.operation_id.in_(ids)))
        return {str(operation_id): ticket_id for operation_id, ticket_id in result.all()}

    async def _build_operations(self, device_id: str, *, limit: int) -> DeviceOperationsOperations:
        failed_count = int(
            await self.session.scalar(
                select(func.count()).select_from(Operation).where(Operation.device_id == device_id, Operation.status.in_(tuple(FAILED_OPERATION_STATUSES)))
            )
            or 0
        )
        running_count = int(
            await self.session.scalar(
                select(func.count()).select_from(Operation).where(Operation.device_id == device_id, Operation.status.in_(tuple(ACTIVE_OPERATION_STATUSES)))
            )
            or 0
        )
        result = await self.session.execute(
            select(Operation)
            .where(Operation.device_id == device_id)
            .order_by(Operation.queued_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        rows = list(result.scalars().all())
        return DeviceOperationsOperations(
            recent_failed_count=failed_count,
            recent_running_count=running_count,
            items=[
                DeviceOperationsOperationItem(
                    id=row.operation_id,
                    ticket_id=_string(row.ticket_id),
                    tool_name=_string(row.tool_name or row.command_name or row.kind),
                    status=_string(row.status),
                    started_at=_iso(_operation_started_at(row)),
                    finished_at=_iso(row.finished_at),
                    duration_ms=_operation_duration_ms(row),
                    error_summary=_error_summary(row.error_message, row.error_code, row.result_summary),
                    trace_id=_string(row.trace_id),
                )
                for row in rows
            ],
        )

    async def _build_observer(self, device_id: str, *, include_traces: bool, limit: int) -> DeviceOperationsObserver:
        count = int(
            await self.session.scalar(select(func.count()).select_from(ObserverTrace).where(ObserverTrace.device_id == device_id))
            or 0
        )
        latest = await self.session.scalar(select(func.max(ObserverTrace.started_at)).where(ObserverTrace.device_id == device_id))
        rows: list[ObserverTrace] = []
        if include_traces:
            result = await self.session.execute(
                select(ObserverTrace)
                .where(ObserverTrace.device_id == device_id)
                .order_by(ObserverTrace.started_at.desc())
                .limit(max(1, min(limit, 100)))
            )
            rows = list(result.scalars().all())
        return DeviceOperationsObserver(
            trace_count=count,
            latest_trace_at=_iso(latest),
            items=[
                DeviceOperationsObserverItem(
                    trace_id=row.trace_id,
                    title=_string(_dict(row.attrs_json).get("title") or _dict(row.attrs_json).get("display_title") or row.root_kind),
                    status=_string(row.status),
                    started_at=_iso(row.started_at),
                    finished_at=_iso(row.finished_at),
                    ticket_id=_string(row.ticket_id),
                    operation_id=_string(row.operation_id),
                    root_span=_string(row.root_span_id),
                    error_summary=_error_summary(_dict(row.attrs_json).get("latest_error"), _dict(row.attrs_json).get("error_summary")),
                )
                for row in rows
            ],
        )

    async def _build_remote_assist(self, device_id: str, *, connection_state: str) -> DeviceOperationsRemoteAssist:
        result = await self.session.execute(
            select(RemoteAccessSession)
            .where(RemoteAccessSession.device_id == device_id)
            .order_by(RemoteAccessSession.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        active = None
        if latest and latest.status in ACTIVE_REMOTE_ACCESS_STATUSES:
            active = latest
        if active and active.consent_status == "pending":
            availability = "requires_consent"
            reason = "Ожидается согласие пользователя."
        elif connection_state == "offline":
            availability = "offline"
            reason = "Агент устройства offline."
        elif active:
            availability = "available"
            reason = "Есть активная или запускаемая сессия."
        elif connection_state == "online":
            availability = "available"
            reason = "Агент online; запуск доступен из тикета с consent workflow."
        else:
            availability = "unknown"
            reason = "Статус агента неизвестен."
        return DeviceOperationsRemoteAssist(
            availability=availability,
            reason=reason,
            active_session_id=active.id if active and active.status == "active" else None,
            pending_consent_id=active.id if active and active.consent_status == "pending" else None,
            last_session_at=_iso(getattr(latest, "created_at", None)),
            can_request=False,
        )

    async def _build_provisioning(self, device_id: str) -> DeviceOperationsProvisioning:
        connection_result = await self.session.execute(
            select(ConnectionRequest)
            .where(ConnectionRequest.device_id == device_id)
            .order_by(ConnectionRequest.last_request_at.desc())
            .limit(1)
        )
        connection_request = connection_result.scalar_one_or_none()
        active_token = await self.session.scalar(
            select(AgentToken.token_hash)
            .where(AgentToken.device_id == device_id, AgentToken.revoked_at.is_(None))
            .limit(1)
        )
        audit_result = await self.session.execute(
            select(AgentRuntimeAudit)
            .where(
                AgentRuntimeAudit.device_id == device_id,
                AgentRuntimeAudit.severity.in_(("warning", "error", "critical")),
            )
            .order_by(AgentRuntimeAudit.created_at.desc())
            .limit(1)
        )
        audit = audit_result.scalar_one_or_none()
        details = _dict(getattr(audit, "details_json", None))
        last_error = _error_summary(details.get("error"), details.get("message"), getattr(audit, "event_type", None)) if audit else None
        if connection_request and _dict(connection_request.request_metadata).get("last_error"):
            last_error = _error_summary(_dict(connection_request.request_metadata).get("last_error"), last_error)
        auth_state = "error" if audit and str(getattr(audit, "source", "")).startswith("agent_auth") else ("active" if active_token else "missing")
        state = _string(getattr(connection_request, "status", None)) if connection_request else None
        return DeviceOperationsProvisioning(
            state=state,
            auth_state=auth_state,
            last_error=last_error,
            last_error_at=_iso(getattr(audit, "created_at", None) or getattr(connection_request, "last_request_at", None) if (audit or connection_request) else None),
            token_status="active" if active_token else "missing",
            connection_request_id=str(getattr(connection_request, "id", "")) if connection_request else None,
            can_approve=bool(connection_request and connection_request.status == "pending"),
            can_reject=bool(connection_request and connection_request.status == "pending"),
        )
