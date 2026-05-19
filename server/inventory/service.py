from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceInventoryBinding,
    DeviceInventoryBindingHistory,
    DeviceInventoryRefreshPolicy,
    DeviceInventoryRefreshRun,
    DeviceInventorySnapshot,
)
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.presentation_overrides import ToolPresentationOverrideService
from shared.builtin_tool_descriptors import INVENTORY_COLLECT_TOOL_ID, get_builtin_tool_descriptor


INVENTORY_TOOL_ID = INVENTORY_COLLECT_TOOL_ID
_BINDING_FIELDS = [
    "building",
    "floor",
    "room",
    "department",
    "responsible_user",
    "responsible_user_login",
    "inventory_number",
    "status",
    "tags",
    "notes",
]
_BINDING_TEXT_LIMITS = {
    "building": 120,
    "floor": 64,
    "room": 120,
    "department": 160,
    "responsible_user": 160,
    "responsible_user_login": 160,
    "inventory_number": 120,
    "status": 32,
    "notes": 2000,
}
_BINDING_STATUS_VALUES = {"active", "spare", "repair", "retired"}
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _json_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean_binding_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"value exceeds {max_length} characters")
    lowered = cleaned.lower()
    if any(marker in lowered for marker in ("<script", "javascript:", "dangerouslysetinnerhtml", "__html")):
        raise ValueError("HTML/script content is not allowed")
    return cleaned


def _clean_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        raw_items = [str(item).strip() for item in value]
    else:
        raw_items = [str(value).strip()]
    tags: list[str] = []
    for raw in raw_items:
        if not raw:
            continue
        cleaned = _clean_binding_text(raw, max_length=64)
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
        if len(tags) >= 20:
            break
    return tags


def normalize_binding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, limit in _BINDING_TEXT_LIMITS.items():
        result[key] = _clean_binding_text(payload.get(key), max_length=limit)
    status = result.get("status")
    if status and str(status) not in _BINDING_STATUS_VALUES:
        raise ValueError("status must be one of: active, spare, repair, retired")
    result["tags"] = _clean_tags(payload.get("tags"))
    return result


def binding_to_dict(row: DeviceInventoryBinding | None) -> dict[str, Any]:
    if row is None:
        return {key: ([] if key == "tags" else None) for key in _BINDING_FIELDS}
    return {
        "building": row.building,
        "floor": row.floor,
        "room": row.room,
        "department": row.department,
        "responsible_user": row.responsible_user,
        "responsible_user_login": row.responsible_user_login,
        "inventory_number": row.inventory_number,
        "status": row.status,
        "tags": list(row.tags or []),
        "notes": row.notes,
    }


def _escape_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


def _snapshot_collected_at(row: DeviceInventorySnapshot | None) -> datetime | None:
    if row is None:
        return None
    return _parse_datetime(getattr(row, "collected_at", None))


def _latest_snapshot_by_device(rows: list[DeviceInventorySnapshot]) -> dict[str, DeviceInventorySnapshot]:
    latest: dict[str, DeviceInventorySnapshot] = {}
    for row in sorted(rows, key=lambda item: (item.collected_at, item.created_at), reverse=True):
        device_id = str(row.device_id)
        if device_id not in latest:
            latest[device_id] = row
    return latest


def _nested_dict(value: Any, key: str) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get(key), dict):
        return value[key]
    return {}


def _worst_disk_percent(snapshot: dict[str, Any]) -> float | None:
    resources = _nested_dict(snapshot, "resources")
    disks = resources.get("disks") if isinstance(resources.get("disks"), list) else []
    values = [
        float(item.get("used_percent"))
        for item in disks
        if isinstance(item, dict) and isinstance(item.get("used_percent"), (int, float))
    ]
    return max(values) if values else None


def _key_apps_summary(snapshot: dict[str, Any]) -> str:
    software = _nested_dict(snapshot, "software")
    apps = software.get("key_apps") if isinstance(software.get("key_apps"), list) else []
    names: list[str] = []
    for app in apps:
        if not isinstance(app, dict) or not app.get("present"):
            continue
        label = str(app.get("name") or app.get("id") or "").strip()
        version = str(app.get("version") or "").strip()
        if label:
            names.append(f"{label} {version}".strip())
    return "; ".join(names)


def _missing_key_apps(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    software = _nested_dict(snapshot, "software")
    apps = software.get("key_apps") if isinstance(software.get("key_apps"), list) else []
    missing: list[dict[str, Any]] = []
    for app in apps:
        if isinstance(app, dict) and app.get("present") is False:
            missing.append(
                {
                    "id": str(app.get("id") or ""),
                    "name": str(app.get("name") or app.get("id") or ""),
                    "status": str(app.get("status") or "missing"),
                }
            )
    return missing


def extract_tool_result_payload(payload: Any) -> dict[str, Any] | None:
    """Return the structured inventory result from a command_result payload."""
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if isinstance(result, dict) and isinstance(result.get("output"), dict):
        return dict(result["output"])
    if isinstance(result, dict):
        return dict(result)
    output = payload.get("output")
    if isinstance(output, dict):
        return dict(output)
    return None


def _inventory_builtin_descriptor(tool_id: str) -> CapabilityDescriptor | None:
    descriptor = get_builtin_tool_descriptor(tool_id)
    if descriptor is None:
        return None
    return CapabilityDescriptor(
        id=str(descriptor.get("id") or tool_id),
        title="Inventory collect",
        description="Privacy-safe endpoint inventory snapshot",
        provider_id="inventory",
        provider_type="agent_builtin",
        execution_target="agent_builtin",
        tool_kind="inventory",
        risk_level="low",
        side_effects=False,
        requires_device=True,
        requires_agent_online=True,
        platforms=["win32", "linux"],
        params_schema={"type": "object", "additionalProperties": False, "properties": {}},
        output_schema=_safe_dict(descriptor.get("output_schema")),
        output_contract=_safe_dict(descriptor.get("output_contract")),
        presentation_schema=_safe_dict(descriptor.get("presentation_schema")),
        source="agent_builtin",
    )


class DeviceInventoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def normalize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        identity = _safe_dict(snapshot.get("identity"))
        platform = _safe_dict(snapshot.get("platform"))
        resources = _safe_dict(snapshot.get("resources"))
        network = _safe_dict(snapshot.get("network"))
        disks = resources.get("disks") if isinstance(resources.get("disks"), list) else []
        disk_percents = [
            float(item.get("used_percent"))
            for item in disks
            if isinstance(item, dict) and isinstance(item.get("used_percent"), (int, float))
        ]
        return {
            "hostname": str(identity.get("hostname") or ""),
            "current_user": str(identity.get("current_user") or ""),
            "primary_ip": str(network.get("primary_ip") or ""),
            "os": " ".join(str(part) for part in (platform.get("os_name"), platform.get("os_version")) if part).strip(),
            "agent_version": str(_safe_dict(snapshot.get("agent")).get("version") or ""),
            "cpu_percent": resources.get("cpu_percent"),
            "memory_percent": resources.get("memory_percent"),
            "disk_worst_used_percent": max(disk_percents) if disk_percents else None,
        }

    def summarize_snapshot(self, snapshot: dict[str, Any], normalized: dict[str, Any]) -> str:
        parts = [
            str(normalized.get("hostname") or "unknown-host"),
            str(normalized.get("primary_ip") or "").strip(),
            str(normalized.get("os") or "").strip(),
        ]
        return " · ".join(part for part in parts if part)

    async def persist_snapshot(
        self,
        device_id: str,
        snapshot: dict[str, Any],
        *,
        source_tool: str = INVENTORY_TOOL_ID,
        source_version: str | None = None,
        status: str = "ok",
    ) -> DeviceInventorySnapshot:
        normalized = self.normalize_snapshot(snapshot)
        collected_at = _parse_datetime(snapshot.get("collected_at")) or datetime.now(timezone.utc)
        row = DeviceInventorySnapshot(
            id=str(uuid.uuid4()),
            device_id=str(device_id),
            source_tool=source_tool,
            source_version=source_version,
            snapshot=dict(snapshot),
            normalized=normalized,
            status=status,
            summary=self.summarize_snapshot(snapshot, normalized),
            collected_at=collected_at,
            received_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            snapshot_hash=_json_hash(snapshot),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_latest(self, device_id: str) -> DeviceInventorySnapshot | None:
        result = await self.session.execute(
            select(DeviceInventorySnapshot)
            .where(DeviceInventorySnapshot.device_id == str(device_id))
            .order_by(desc(DeviceInventorySnapshot.collected_at), desc(DeviceInventorySnapshot.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_history(self, device_id: str, *, limit: int = 20) -> list[DeviceInventorySnapshot]:
        result = await self.session.execute(
            select(DeviceInventorySnapshot)
            .where(DeviceInventorySnapshot.device_id == str(device_id))
            .order_by(desc(DeviceInventorySnapshot.collected_at), desc(DeviceInventorySnapshot.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_binding(self, device_id: str) -> DeviceInventoryBinding | None:
        result = await self.session.execute(
            select(DeviceInventoryBinding).where(DeviceInventoryBinding.device_id == str(device_id)).limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_binding(
        self,
        device_id: str,
        payload: dict[str, Any],
        *,
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> DeviceInventoryBinding:
        normalized = normalize_binding_payload(payload)
        row = await self.get_binding(device_id)
        old_binding = None if row is None else binding_to_dict(row)
        now = datetime.now(timezone.utc)
        if row is None:
            row = DeviceInventoryBinding(device_id=str(device_id), updated_at=now)
            self.session.add(row)
        changed_fields = [
            key
            for key in _BINDING_FIELDS
            if (old_binding or {key: None}).get(key) != normalized.get(key)
        ]
        if not changed_fields:
            return row
        for key, value in normalized.items():
            setattr(row, key, value)
        row.updated_by = updated_by
        row.updated_at = now
        history = DeviceInventoryBindingHistory(
            id=str(uuid.uuid4()),
            device_id=str(device_id),
            changed_by=updated_by,
            changed_at=now,
            old_binding=old_binding,
            new_binding=dict(normalized),
            changed_fields=changed_fields,
            reason=_clean_binding_text(reason, max_length=1000) if reason else None,
        )
        self.session.add(history)
        await self.session.flush()
        return row

    async def list_binding_history(self, device_id: str, *, limit: int = 50) -> list[DeviceInventoryBindingHistory]:
        result = await self.session.execute(
            select(DeviceInventoryBindingHistory)
            .where(DeviceInventoryBindingHistory.device_id == str(device_id))
            .order_by(desc(DeviceInventoryBindingHistory.changed_at))
            .limit(max(1, min(int(limit or 50), 200)))
        )
        return list(result.scalars().all())

    async def record_refresh_run(
        self,
        *,
        device_id: str | None = None,
        policy_id: str | None = None,
        requested_at: datetime | None = None,
        requested_by: str | None = None,
        status: str = "requested",
        job_id: str | None = None,
        error: str | None = None,
        completed_at: datetime | None = None,
    ) -> DeviceInventoryRefreshRun:
        if status not in {"requested", "skipped_offline", "dispatched", "failed"}:
            raise ValueError("invalid refresh run status")
        row = DeviceInventoryRefreshRun(
            id=str(uuid.uuid4()),
            device_id=str(device_id) if device_id else None,
            policy_id=str(policy_id) if policy_id else None,
            requested_at=requested_at or datetime.now(timezone.utc),
            requested_by=requested_by,
            status=status,
            job_id=job_id,
            error=_clean_binding_text(error, max_length=1000) if error else None,
            completed_at=completed_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_refresh_runs(
        self,
        *,
        device_id: str | None = None,
        limit: int = 50,
    ) -> list[DeviceInventoryRefreshRun]:
        stmt = select(DeviceInventoryRefreshRun)
        if device_id:
            stmt = stmt.where(DeviceInventoryRefreshRun.device_id == str(device_id))
        result = await self.session.execute(
            stmt.order_by(desc(DeviceInventoryRefreshRun.requested_at)).limit(max(1, min(int(limit or 50), 200)))
        )
        return list(result.scalars().all())

    async def import_bindings_csv(
        self,
        csv_text: str,
        *,
        dry_run: bool = True,
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if len(csv_text or "") > 2_000_000:
            raise ValueError("CSV file is too large")
        reader = csv.DictReader(io.StringIO(csv_text or ""))
        if not reader.fieldnames:
            raise ValueError("CSV header is required")
        changes: list[dict[str, Any]] = []
        total_rows = 0
        valid_rows = 0
        error_rows = 0
        allowed = {"device_id", "hostname", *_BINDING_FIELDS}
        for row_number, row in enumerate(reader, start=2):
            total_rows += 1
            errors: list[str] = []
            device_id = str(row.get("device_id") or "").strip()
            hostname = str(row.get("hostname") or "").strip()
            device = None
            if device_id:
                result = await self.session.execute(
                    select(Device).where(Device.device_id == device_id, Device.deleted_at.is_(None)).limit(1)
                )
                device = result.scalar_one_or_none()
            elif hostname:
                result = await self.session.execute(
                    select(Device).where(Device.hostname == hostname, Device.deleted_at.is_(None)).limit(2)
                )
                matches = list(result.scalars().all())
                if len(matches) == 1:
                    device = matches[0]
                    device_id = str(device.device_id)
                elif len(matches) > 1:
                    errors.append("hostname is not unique")
            else:
                errors.append("device_id or hostname is required")
            if device is None and not errors:
                errors.append("device not found")
            raw_payload = {key: row.get(key) for key in allowed if key in row}
            try:
                normalized = normalize_binding_payload(raw_payload)
            except ValueError as exc:
                errors.append(str(exc))
                normalized = {}
            if errors:
                error_rows += 1
                changes.append(
                    {
                        "row": row_number,
                        "device_id": device_id or None,
                        "hostname": hostname or None,
                        "action": "error",
                        "changed_fields": [],
                        "errors": errors,
                    }
                )
                continue
            current = binding_to_dict(await self.get_binding(device_id))
            changed_fields = [key for key in _BINDING_FIELDS if current.get(key) != normalized.get(key)]
            action = "skip" if not changed_fields else "update"
            if action == "update" and not dry_run:
                await self.upsert_binding(device_id, normalized, updated_by=updated_by, reason=reason)
            valid_rows += 1
            changes.append(
                {
                    "row": row_number,
                    "device_id": device_id,
                    "hostname": hostname or getattr(device, "hostname", None),
                    "action": action,
                    "changed_fields": changed_fields,
                    "errors": [],
                }
            )
        return {
            "dry_run": bool(dry_run),
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "error_rows": error_rows,
            "changes": changes,
        }

    async def export_bindings_csv(self) -> str:
        devices_result = await self.session.execute(
            select(Device).where(Device.deleted_at.is_(None)).order_by(Device.hostname, Device.device_id)
        )
        devices = list(devices_result.scalars().all())
        bindings_result = await self.session.execute(select(DeviceInventoryBinding))
        bindings = {str(row.device_id): row for row in bindings_result.scalars().all()}
        output = io.StringIO()
        columns = [
            "device_id",
            "hostname",
            "building",
            "floor",
            "room",
            "department",
            "responsible_user",
            "responsible_user_login",
            "inventory_number",
            "status",
            "tags",
            "notes",
        ]
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for device in devices:
            binding = binding_to_dict(bindings.get(str(device.device_id)))
            row = {
                "device_id": str(device.device_id),
                "hostname": device.hostname or "",
                **binding,
                "tags": ";".join(binding.get("tags") or []),
            }
            writer.writerow({key: _escape_csv_cell(row.get(key)) for key in columns})
        return output.getvalue()

    async def _fleet_rows(self) -> tuple[list[Device], dict[str, DeviceInventorySnapshot], dict[str, DeviceInventoryBinding]]:
        devices_result = await self.session.execute(
            select(Device).where(Device.deleted_at.is_(None)).order_by(Device.hostname, Device.device_id)
        )
        devices = list(devices_result.scalars().all())
        snapshots_result = await self.session.execute(select(DeviceInventorySnapshot))
        latest = _latest_snapshot_by_device(list(snapshots_result.scalars().all()))
        bindings_result = await self.session.execute(select(DeviceInventoryBinding))
        bindings = {str(row.device_id): row for row in bindings_result.scalars().all()}
        return devices, latest, bindings

    async def export_inventory_csv(
        self,
        *,
        stale_days: int = 7,
        building: str | None = None,
        department: str | None = None,
        missing_binding: bool | None = None,
        has_snapshot: bool | None = None,
        now: datetime | None = None,
    ) -> str:
        now = now or datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=max(1, int(stale_days or 7)))
        devices, latest, bindings = await self._fleet_rows()
        columns = [
            "device_id",
            "hostname",
            "current_user",
            "building",
            "floor",
            "room",
            "department",
            "responsible_user",
            "inventory_number",
            "os_name",
            "os_version",
            "primary_ip",
            "agent_version",
            "collected_at",
            "stale_status",
            "cpu_percent",
            "memory_percent",
            "worst_disk_percent",
            "default_printer",
            "key_apps_summary",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for device in devices:
            binding = binding_to_dict(bindings.get(str(device.device_id)))
            if building and (binding.get("building") or "") != building:
                continue
            if department and (binding.get("department") or "") != department:
                continue
            missing_binding_value = not any(binding.get(key) for key in ("room", "department", "responsible_user", "inventory_number"))
            if missing_binding is not None and missing_binding_value != missing_binding:
                continue
            snapshot_row = latest.get(str(device.device_id))
            if has_snapshot is not None and (snapshot_row is not None) != has_snapshot:
                continue
            snapshot = dict(getattr(snapshot_row, "snapshot", None) or {})
            identity = _nested_dict(snapshot, "identity")
            platform = _nested_dict(snapshot, "platform")
            network = _nested_dict(snapshot, "network")
            agent = _nested_dict(snapshot, "agent")
            printers = _nested_dict(snapshot, "printers")
            collected_at = _snapshot_collected_at(snapshot_row)
            stale_status = "missing" if snapshot_row is None else ("stale" if collected_at and collected_at < stale_cutoff else "fresh")
            row = {
                "device_id": str(device.device_id),
                "hostname": identity.get("hostname") or device.hostname or "",
                "current_user": identity.get("current_user") or "",
                "building": binding.get("building"),
                "floor": binding.get("floor"),
                "room": binding.get("room"),
                "department": binding.get("department"),
                "responsible_user": binding.get("responsible_user"),
                "inventory_number": binding.get("inventory_number"),
                "os_name": platform.get("os_name") or "",
                "os_version": platform.get("os_version") or "",
                "primary_ip": network.get("primary_ip") or "",
                "agent_version": agent.get("version") or getattr(device, "agent_version", "") or "",
                "collected_at": collected_at.isoformat() if collected_at else "",
                "stale_status": stale_status,
                "cpu_percent": _nested_dict(snapshot, "resources").get("cpu_percent"),
                "memory_percent": _nested_dict(snapshot, "resources").get("memory_percent"),
                "worst_disk_percent": _worst_disk_percent(snapshot),
                "default_printer": printers.get("default_printer") or "",
                "key_apps_summary": _key_apps_summary(snapshot),
            }
            writer.writerow({key: _escape_csv_cell(row.get(key)) for key in columns})
        return output.getvalue()

    async def build_dashboard(self, *, stale_days: int = 7, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=max(1, int(stale_days or 7)))
        online_cutoff = now - timedelta(minutes=10)
        devices, latest, bindings = await self._fleet_rows()
        with_inventory = 0
        fresh_inventory = 0
        stale_inventory = 0
        high_disk_usage = 0
        missing_key_apps: list[dict[str, Any]] = []
        by_os: dict[str, int] = {}
        by_building: dict[str, int] = {}
        by_department: dict[str, int] = {}
        binding_gaps = {
            "missing_room": 0,
            "missing_department": 0,
            "missing_responsible_user": 0,
            "missing_inventory_number": 0,
        }
        online_count = 0
        for device in devices:
            device_id = str(device.device_id)
            if getattr(device, "last_seen_at", None) and device.last_seen_at >= online_cutoff:
                online_count += 1
            binding = binding_to_dict(bindings.get(device_id))
            building = str(binding.get("building") or "Не указано")
            department = str(binding.get("department") or "Не указано")
            by_building[building] = by_building.get(building, 0) + 1
            by_department[department] = by_department.get(department, 0) + 1
            if not binding.get("room"):
                binding_gaps["missing_room"] += 1
            if not binding.get("department"):
                binding_gaps["missing_department"] += 1
            if not binding.get("responsible_user"):
                binding_gaps["missing_responsible_user"] += 1
            if not binding.get("inventory_number"):
                binding_gaps["missing_inventory_number"] += 1
            snapshot_row = latest.get(device_id)
            if snapshot_row is None:
                continue
            with_inventory += 1
            collected_at = _snapshot_collected_at(snapshot_row)
            if collected_at and collected_at >= stale_cutoff:
                fresh_inventory += 1
            else:
                stale_inventory += 1
            snapshot = dict(snapshot_row.snapshot or {})
            platform = _nested_dict(snapshot, "platform")
            os_label = " ".join(str(part) for part in (platform.get("os_name"), platform.get("os_version")) if part).strip() or "Не указано"
            by_os[os_label] = by_os.get(os_label, 0) + 1
            worst_disk = _worst_disk_percent(snapshot)
            if worst_disk is not None and worst_disk >= 90:
                high_disk_usage += 1
            for app in _missing_key_apps(snapshot):
                missing_key_apps.append({"device_id": device_id, "hostname": device.hostname, **app})
        policies_result = await self.session.execute(select(DeviceInventoryRefreshPolicy))
        policies = list(policies_result.scalars().all())
        runs = await self.list_refresh_runs(limit=100)
        last_requested_at = max((policy.last_requested_at for policy in policies if policy.last_requested_at), default=None)
        return {
            "totals": {
                "devices": len(devices),
                "online": online_count,
                "offline": max(0, len(devices) - online_count),
                "with_inventory": with_inventory,
                "missing_inventory": max(0, len(devices) - with_inventory),
                "fresh_inventory": fresh_inventory,
                "stale_inventory": stale_inventory,
                "missing_binding": sum(1 for device in devices if str(device.device_id) not in bindings),
            },
            "freshness": {
                "fresh_days": max(1, int(stale_days or 7)),
                "stale_count": stale_inventory,
                "missing_count": max(0, len(devices) - with_inventory),
            },
            "by_os": [{"label": key, "count": value} for key, value in sorted(by_os.items())],
            "by_building": [{"label": key, "count": value} for key, value in sorted(by_building.items())],
            "by_department": [{"label": key, "count": value} for key, value in sorted(by_department.items())],
            "binding_gaps": binding_gaps,
            "health": {
                "high_disk_usage": high_disk_usage,
                "missing_key_apps": missing_key_apps[:100],
            },
            "refresh": {
                "enabled": any(bool(policy.enabled) for policy in policies),
                "due_devices": len(await self.list_due_refresh_policies(now=now, limit=1000)),
                "last_requested_at": last_requested_at.isoformat() if last_requested_at else None,
                "last_run_status": runs[0].status if runs else None,
                "last_run_at": runs[0].requested_at.isoformat() if runs else None,
            },
        }

    async def get_refresh_policy(
        self,
        *,
        scope: str = "global",
        device_id: str | None = None,
    ) -> DeviceInventoryRefreshPolicy | None:
        scope = str(scope or "global").strip().lower() or "global"
        stmt = select(DeviceInventoryRefreshPolicy).where(DeviceInventoryRefreshPolicy.scope == scope)
        if scope == "device":
            stmt = stmt.where(DeviceInventoryRefreshPolicy.device_id == str(device_id or ""))
        else:
            stmt = stmt.where(DeviceInventoryRefreshPolicy.device_id.is_(None))
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_effective_refresh_policy(self, device_id: str) -> DeviceInventoryRefreshPolicy | None:
        device_policy = await self.get_refresh_policy(scope="device", device_id=device_id)
        if device_policy is not None:
            return device_policy
        return await self.get_refresh_policy(scope="global")

    async def upsert_refresh_policy(
        self,
        *,
        scope: str = "global",
        device_id: str | None = None,
        enabled: bool = False,
        interval_minutes: int = 1440,
        jitter_minutes: int = 30,
        updated_by: str | None = None,
    ) -> DeviceInventoryRefreshPolicy:
        scope = str(scope or "global").strip().lower() or "global"
        if scope not in {"global", "device"}:
            raise ValueError("scope must be global or device")
        if scope == "device" and not str(device_id or "").strip():
            raise ValueError("device_id is required for device scope")
        interval_minutes = max(15, min(int(interval_minutes or 1440), 60 * 24 * 30))
        jitter_minutes = max(0, min(int(jitter_minutes or 0), interval_minutes))
        row = await self.get_refresh_policy(scope=scope, device_id=device_id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = DeviceInventoryRefreshPolicy(
                id=str(uuid.uuid4()),
                scope=scope,
                device_id=str(device_id) if scope == "device" else None,
            )
            self.session.add(row)
        row.enabled = bool(enabled)
        row.interval_minutes = interval_minutes
        row.jitter_minutes = jitter_minutes
        row.updated_by = updated_by
        row.updated_at = now
        if row.next_due_at is None:
            row.next_due_at = now + timedelta(minutes=interval_minutes)
        await self.session.flush()
        return row

    async def list_due_refresh_policies(self, *, now: datetime | None = None, limit: int = 100) -> list[DeviceInventoryRefreshPolicy]:
        now = now or datetime.now(timezone.utc)
        result = await self.session.execute(
            select(DeviceInventoryRefreshPolicy)
            .where(DeviceInventoryRefreshPolicy.enabled.is_(True))
            .where(
                (DeviceInventoryRefreshPolicy.next_due_at.is_(None))
                | (DeviceInventoryRefreshPolicy.next_due_at <= now)
            )
            .order_by(DeviceInventoryRefreshPolicy.next_due_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_refresh_requested(
        self,
        policy: DeviceInventoryRefreshPolicy,
        *,
        requested_at: datetime | None = None,
    ) -> DeviceInventoryRefreshPolicy:
        requested_at = requested_at or datetime.now(timezone.utc)
        policy.last_requested_at = requested_at
        policy.next_due_at = requested_at + timedelta(minutes=max(15, int(policy.interval_minutes or 1440)))
        policy.updated_at = requested_at
        await self.session.flush()
        return policy

    async def resolve_inventory_presentation(self, *, tool_id: str = INVENTORY_TOOL_ID) -> dict[str, Any]:
        presentation_service = ToolPresentationOverrideService(self.session)
        descriptor = await presentation_service.descriptor_from_persisted_capability(tool_id)
        if descriptor is None:
            descriptor = _inventory_builtin_descriptor(tool_id)
        if descriptor is None:
            descriptor = CapabilityDescriptor(id=tool_id, title=tool_id, execution_target="agent_builtin")
        detail = await presentation_service.get_presentation_detail(descriptor)
        output_contract = _safe_dict(descriptor.output_contract)
        device_card = _safe_dict(output_contract.get("device_card"))
        slots = device_card.get("slots") if isinstance(device_card.get("slots"), list) else []
        return {
            "presentation_schema": _safe_dict(descriptor.presentation_schema),
            "effective_presentation_schema": _safe_dict(detail.get("effective_schema")),
            "presentation_schema_source": str(detail.get("source") or "none"),
            "device_card_slots": [str(item) for item in slots],
        }
