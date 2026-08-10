from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from typing import Any
import uuid
import zipfile
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceBindingSuggestion,
    DeviceInventoryBulkOperation,
    DeviceInventoryBulkOperationItem,
    DeviceInventoryBinding,
    DeviceInventoryBindingHistory,
    DeviceInventoryRefreshPolicy,
    DeviceInventoryRefreshRun,
    DeviceInventorySnapshot,
)
from domain_ports import (
    ActiveBindingProjection,
    DeviceRef,
    DomainPortContainer,
    RegistryPort,
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
_BULK_MODES = {"selected", "stale", "missing", "department", "building"}


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


def _escape_xlsx_cell(value: Any) -> str:
    return _escape_csv_cell(value)


def _build_simple_xlsx(sheets: dict[str, list[list[Any]]]) -> bytes:
    """Create a small XLSX workbook with inline strings only.

    This intentionally avoids a new runtime dependency and is sufficient for
    operational exports. Values are escaped as text to avoid formula execution.
    """
    def sheet_xml(rows: list[list[Any]]) -> str:
        xml_rows: list[str] = []
        for row_index, row in enumerate(rows, start=1):
            cells: list[str] = []
            for col_index, value in enumerate(row, start=1):
                col = ""
                n = col_index
                while n:
                    n, rem = divmod(n - 1, 26)
                    col = chr(65 + rem) + col
                text = xml_escape(_escape_xlsx_cell(value))
                cells.append(f'<c r="{col}{row_index}" t="inlineStr"><is><t>{text}</t></is></c>')
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
        )

    sheet_names = list(sheets.keys())
    workbook_sheets = "".join(
        f'<sheet name="{xml_escape(name[:31])}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    workbook_rels = "".join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        for idx in range(1, len(sheet_names) + 1)
    )
    content_types = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, len(sheet_names) + 1)
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f"{content_types}</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets}</sheets></workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_rels}</Relationships>",
        )
        for idx, name in enumerate(sheet_names, start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml(sheets[name]))
    return output.getvalue()


def _bool_query(value: str | None) -> bool | None:
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
        title=str(descriptor.get("title") or tool_id),
        description=str(descriptor.get("description") or ""),
        provider_id=str(descriptor.get("provider_id") or tool_id.split(".", 1)[0]),
        provider_type=str(descriptor.get("provider_type") or "agent_builtin"),
        execution_target=str(descriptor.get("execution_target") or "agent_builtin"),
        tool_kind=str(descriptor.get("tool_kind") or tool_id.split(".", 1)[0]),
        risk_level=str(descriptor.get("risk_level") or "low"),
        side_effects=bool(descriptor.get("side_effects", False)),
        requires_device=bool(descriptor.get("requires_device", True)),
        requires_agent_online=bool(descriptor.get("requires_agent_online", True)),
        platforms=[str(item) for item in descriptor.get("platforms", [])] or ["win32", "linux"],
        params_schema=_safe_dict(descriptor.get("params_schema")) or {"type": "object", "additionalProperties": False, "properties": {}},
        output_schema=_safe_dict(descriptor.get("output_schema")),
        output_contract=_safe_dict(descriptor.get("output_contract")),
        presentation_schema=_safe_dict(descriptor.get("presentation_schema")),
        source=str(descriptor.get("source") or "agent_builtin"),
    )


class DeviceInventoryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry_port: RegistryPort | None = None,
    ):
        self.session = session
        self.registry_port = registry_port or DomainPortContainer.from_config(
            registry_session=session
        ).registry

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
        bulk_operation_id: str | None = None,
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
            bulk_operation_id=str(bulk_operation_id) if bulk_operation_id else None,
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

    async def list_attention_items(self, *, stale_days: int = 7, now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
        now = now or datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=max(1, int(stale_days or 7)))
        devices, latest, bindings = await self._fleet_rows()
        groups = {
            "missing_inventory": [],
            "stale_inventory": [],
            "missing_room": [],
            "missing_department": [],
            "missing_inventory_number": [],
            "high_disk_usage": [],
            "missing_key_apps": [],
        }
        for device in devices:
            device_id = str(device.device_id)
            binding = binding_to_dict(bindings.get(device_id))
            base = {"device_id": device_id, "hostname": device.hostname}
            snapshot_row = latest.get(device_id)
            if snapshot_row is None:
                groups["missing_inventory"].append(base)
            else:
                collected_at = _snapshot_collected_at(snapshot_row)
                if not collected_at or collected_at < stale_cutoff:
                    groups["stale_inventory"].append({**base, "collected_at": collected_at.isoformat() if collected_at else None})
                snapshot = dict(snapshot_row.snapshot or {})
                worst_disk = _worst_disk_percent(snapshot)
                if worst_disk is not None and worst_disk >= 90:
                    groups["high_disk_usage"].append({**base, "worst_disk_percent": worst_disk})
                for app in _missing_key_apps(snapshot):
                    groups["missing_key_apps"].append({**base, **app})
            if not binding.get("room"):
                groups["missing_room"].append(base)
            if not binding.get("department"):
                groups["missing_department"].append(base)
            if not binding.get("inventory_number"):
                groups["missing_inventory_number"].append(base)
        return {key: value[:200] for key, value in groups.items()}

    async def build_report(self, *, report_type: str, stale_days: int = 7) -> dict[str, Any]:
        report_type = str(report_type or "attention").strip().lower()
        dashboard = await self.build_dashboard(stale_days=stale_days)
        if report_type == "department":
            return {"type": "department", "items": dashboard.get("by_department", [])}
        if report_type == "building":
            return {"type": "building", "items": dashboard.get("by_building", [])}
        attention = await self.list_attention_items(stale_days=stale_days)
        return {
            "type": "attention",
            "items": [
                {"group": key, "count": len(value), "items": value[:50]}
                for key, value in attention.items()
            ],
        }

    async def export_inventory_xlsx(self, *, stale_days: int = 7) -> bytes:
        devices, latest, bindings = await self._fleet_rows()
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=max(1, int(stale_days or 7)))
        inventory_rows = [[
            "device_id", "hostname", "current_user", "building", "floor", "room", "department",
            "responsible_user", "inventory_number", "os_name", "os_version", "primary_ip",
            "agent_version", "collected_at", "stale_status", "cpu_percent", "memory_percent",
            "worst_disk_percent", "default_printer", "key_apps_summary",
        ]]
        binding_gap_rows = [["device_id", "hostname", "missing_room", "missing_department", "missing_responsible_user", "missing_inventory_number"]]
        stale_rows = [["device_id", "hostname", "stale_status", "collected_at"]]
        key_app_rows = [["device_id", "hostname", "app_id", "app_name", "present", "version", "status"]]
        high_disk_rows = [["device_id", "hostname", "worst_disk_percent"]]
        for device in devices:
            device_id = str(device.device_id)
            binding = binding_to_dict(bindings.get(device_id))
            snapshot_row = latest.get(device_id)
            snapshot = dict(getattr(snapshot_row, "snapshot", None) or {})
            identity = _nested_dict(snapshot, "identity")
            platform = _nested_dict(snapshot, "platform")
            network = _nested_dict(snapshot, "network")
            agent = _nested_dict(snapshot, "agent")
            printers = _nested_dict(snapshot, "printers")
            collected_at = _snapshot_collected_at(snapshot_row)
            stale_status = "missing" if snapshot_row is None else ("stale" if collected_at and collected_at < stale_cutoff else "fresh")
            hostname = identity.get("hostname") or device.hostname or ""
            worst_disk = _worst_disk_percent(snapshot)
            inventory_rows.append([
                device_id, hostname, identity.get("current_user") or "", binding.get("building"),
                binding.get("floor"), binding.get("room"), binding.get("department"),
                binding.get("responsible_user"), binding.get("inventory_number"),
                platform.get("os_name") or "", platform.get("os_version") or "",
                network.get("primary_ip") or "", agent.get("version") or getattr(device, "agent_version", "") or "",
                collected_at.isoformat() if collected_at else "", stale_status,
                _nested_dict(snapshot, "resources").get("cpu_percent"),
                _nested_dict(snapshot, "resources").get("memory_percent"),
                worst_disk, printers.get("default_printer") or "", _key_apps_summary(snapshot),
            ])
            if stale_status != "fresh":
                stale_rows.append([device_id, hostname, stale_status, collected_at.isoformat() if collected_at else ""])
            gaps = [
                not bool(binding.get("room")),
                not bool(binding.get("department")),
                not bool(binding.get("responsible_user")),
                not bool(binding.get("inventory_number")),
            ]
            if any(gaps):
                binding_gap_rows.append([device_id, hostname, *gaps])
            if worst_disk is not None and worst_disk >= 90:
                high_disk_rows.append([device_id, hostname, worst_disk])
            software = _nested_dict(snapshot, "software")
            apps = software.get("key_apps") if isinstance(software.get("key_apps"), list) else []
            for app in apps:
                if isinstance(app, dict):
                    key_app_rows.append([
                        device_id, hostname, app.get("id"), app.get("name"), app.get("present"),
                        app.get("version"), app.get("status"),
                    ])
        return _build_simple_xlsx(
            {
                "Inventory": inventory_rows,
                "Binding gaps": binding_gap_rows,
                "Stale missing": stale_rows,
                "Key apps": key_app_rows,
                "High disk": high_disk_rows,
            }
        )

    async def bulk_refresh_preview(
        self,
        *,
        device_ids: list[str] | None = None,
        mode: str = "selected",
        filters: dict[str, Any] | None = None,
        wave: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        filters = filters or {}
        wave = wave or {}
        mode = str(mode or "selected").strip().lower()
        if mode not in _BULK_MODES:
            raise ValueError("invalid bulk refresh mode")
        stale_days = int(filters.get("stale_days") or 7)
        stale_cutoff = now - timedelta(days=max(1, stale_days))
        online_only = bool(filters.get("online_only", False))
        online_cutoff = now - timedelta(minutes=10)
        batch_size = max(1, min(int(wave.get("batch_size") or 10), 100))
        devices, latest, bindings = await self._fleet_rows()
        explicit_ids = {str(item) for item in (device_ids or []) if str(item).strip()}
        items: list[dict[str, Any]] = []
        for device in devices:
            device_id = str(device.device_id)
            binding = binding_to_dict(bindings.get(device_id))
            snapshot_row = latest.get(device_id)
            collected_at = _snapshot_collected_at(snapshot_row)
            include = False
            if mode == "selected":
                include = device_id in explicit_ids
            elif mode == "stale":
                include = snapshot_row is not None and (not collected_at or collected_at < stale_cutoff)
            elif mode == "missing":
                include = snapshot_row is None
            elif mode == "department":
                include = bool(filters.get("department")) and binding.get("department") == filters.get("department")
            elif mode == "building":
                include = bool(filters.get("building")) and binding.get("building") == filters.get("building")
            if not include:
                continue
            online = bool(getattr(device, "last_seen_at", None) and device.last_seen_at >= online_cutoff)
            status = "ready"
            reason = None
            if online_only and not online:
                status = "skipped"
                reason = "online_only"
            elif not online and bool(wave.get("skip_offline", True)):
                status = "offline"
                reason = "device offline"
            items.append(
                {
                    "device_id": device_id,
                    "hostname": device.hostname,
                    "online": online,
                    "status": status,
                    "reason": reason,
                }
            )
        ready_count = sum(1 for item in items if item["status"] == "ready")
        online_count = sum(1 for item in items if item.get("online"))
        return {
            "dry_run": True,
            "selected_count": len(items),
            "online_count": online_count,
            "offline_count": max(0, len(items) - online_count),
            "estimated_waves": (ready_count + batch_size - 1) // batch_size if ready_count else 0,
            "items": items,
        }

    async def create_bulk_refresh_operation(
        self,
        *,
        preview: dict[str, Any],
        mode: str,
        filters: dict[str, Any] | None,
        wave: dict[str, Any] | None,
        requested_by: str | None = None,
    ) -> DeviceInventoryBulkOperation:
        wave = wave or {}
        batch_size = max(1, min(int(wave.get("batch_size") or 10), 100))
        operation = DeviceInventoryBulkOperation(
            id=str(uuid.uuid4()),
            operation_type="inventory_refresh",
            status="planned",
            requested_by=requested_by,
            requested_at=datetime.now(timezone.utc),
            filters={"mode": mode, **(filters or {})},
            wave=dict(wave),
            total_count=int(preview.get("selected_count") or 0),
        )
        self.session.add(operation)
        for index, item in enumerate(preview.get("items") or []):
            if not isinstance(item, dict):
                continue
            status = "pending" if item.get("status") == "ready" else "skipped_offline"
            if status == "skipped_offline":
                operation.skipped_count += 1
            self.session.add(
                DeviceInventoryBulkOperationItem(
                    id=str(uuid.uuid4()),
                    operation_id=operation.id,
                    device_id=str(item.get("device_id")),
                    wave_index=index // batch_size,
                    status=status,
                    error=str(item.get("reason") or "") or None,
                )
            )
        await self.session.flush()
        return operation

    async def list_bulk_operations(self, *, limit: int = 20) -> list[DeviceInventoryBulkOperation]:
        result = await self.session.execute(
            select(DeviceInventoryBulkOperation)
            .order_by(desc(DeviceInventoryBulkOperation.requested_at))
            .limit(max(1, min(int(limit or 20), 100)))
        )
        return list(result.scalars().all())

    async def list_bulk_operation_items(self, operation_id: str) -> list[DeviceInventoryBulkOperationItem]:
        result = await self.session.execute(
            select(DeviceInventoryBulkOperationItem)
            .where(DeviceInventoryBulkOperationItem.operation_id == str(operation_id))
            .order_by(DeviceInventoryBulkOperationItem.wave_index, DeviceInventoryBulkOperationItem.device_id)
        )
        return list(result.scalars().all())

    async def list_device_profiles(self, device_id: str) -> list[dict[str, Any]]:
        suggestions = await self.list_binding_suggestions(device_id, include_reviewed=True)
        profiles: dict[str, dict[str, Any]] = {}
        for suggestion in suggestions:
            profile = dict(suggestion.profile_snapshot or {})
            key = str(profile.get("requester_id") or suggestion.source_ref or suggestion.id)
            profiles[key] = {
                "requester_id": profile.get("requester_id") or suggestion.source_ref,
                "display_name": profile.get("display_name"),
                "full_name": profile.get("full_name"),
                "department": profile.get("department"),
                "building": profile.get("building"),
                "floor": profile.get("floor"),
                "room": profile.get("room"),
                "phone": profile.get("phone"),
                "email": profile.get("email"),
                "active": bool(profile.get("active", False)),
                "last_seen_at": profile.get("last_seen_at") or profile.get("submitted_at"),
                "source": "agent_profile",
                "status": suggestion.status,
            }
        requested_device_id = str(device_id)
        binding = await self.registry_port.active_binding(
            DeviceRef(external_id=requested_device_id)
        )
        if (
            isinstance(binding, ActiveBindingProjection)
            and binding.device.external_id == requested_device_id
            and binding.requester.external_id
            == binding.requester_snapshot.person.external_id
        ):
            requester_id = binding.requester.external_id
            profiles.setdefault(
                requester_id,
                {
                    "requester_id": requester_id,
                    "display_name": binding.requester_snapshot.display_name,
                    "full_name": None,
                    "department": None,
                    "building": None,
                    "floor": None,
                    "room": None,
                    "phone": None,
                    "email": None,
                    "active": False,
                    "last_seen_at": None,
                    "source": "registry_port",
                    "status": binding.status,
                },
            )
        return sorted(profiles.values(), key=lambda item: (not bool(item.get("active")), str(item.get("last_seen_at") or "")), reverse=False)

    def build_suggested_binding_from_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return normalize_binding_payload(
            {
                "building": profile.get("building"),
                "floor": profile.get("floor"),
                "room": profile.get("room"),
                "department": profile.get("department"),
                "responsible_user": profile.get("full_name") or profile.get("display_name"),
                "responsible_user_login": profile.get("login") or profile.get("email") or profile.get("requester_id"),
                "notes": None,
            }
        )

    async def create_or_update_binding_suggestion_from_profile(
        self,
        *,
        device_id: str,
        requester_id: str | None,
        display_name: str | None,
        profile: dict[str, Any],
    ) -> DeviceBindingSuggestion | None:
        if not device_id:
            return None
        profile_snapshot = {
            "requester_id": requester_id,
            "display_name": display_name,
            "full_name": profile.get("full_name") or display_name,
            "department": profile.get("department"),
            "building": profile.get("building"),
            "floor": profile.get("floor"),
            "room": profile.get("room"),
            "phone": profile.get("phone"),
            "email": profile.get("email"),
            "login": profile.get("login"),
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "source": "agent_profile",
        }
        suggested = self.build_suggested_binding_from_profile(profile_snapshot)
        if not any(suggested.get(key) for key in ("building", "room", "department", "responsible_user")):
            return None
        current = binding_to_dict(await self.get_binding(device_id))
        differs = [key for key, value in suggested.items() if value not in (None, [], "") and current.get(key) != value]
        if not differs:
            return None
        source_ref = str(requester_id or display_name or "agent_profile")
        result = await self.session.execute(
            select(DeviceBindingSuggestion)
            .where(
                DeviceBindingSuggestion.device_id == str(device_id),
                DeviceBindingSuggestion.source == "agent_profile",
                DeviceBindingSuggestion.source_ref == source_ref,
                DeviceBindingSuggestion.status == "pending",
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = DeviceBindingSuggestion(
                id=str(uuid.uuid4()),
                device_id=str(device_id),
                source="agent_profile",
                source_ref=source_ref,
                created_at=now,
            )
            self.session.add(row)
        row.suggested_binding = suggested
        row.profile_snapshot = profile_snapshot
        row.status = "pending"
        row.confidence = "medium" if len(differs) <= 2 else "low"
        row.updated_at = now
        await self.session.flush()
        return row

    async def list_binding_suggestions(
        self,
        device_id: str,
        *,
        include_reviewed: bool = False,
        limit: int = 50,
    ) -> list[DeviceBindingSuggestion]:
        stmt = select(DeviceBindingSuggestion).where(DeviceBindingSuggestion.device_id == str(device_id))
        if not include_reviewed:
            stmt = stmt.where(DeviceBindingSuggestion.status == "pending")
        result = await self.session.execute(
            stmt.order_by(desc(DeviceBindingSuggestion.updated_at)).limit(max(1, min(int(limit or 50), 200)))
        )
        return list(result.scalars().all())

    async def apply_binding_suggestion(
        self,
        *,
        device_id: str,
        suggestion_id: str,
        fields: list[str],
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> DeviceBindingSuggestion:
        result = await self.session.execute(
            select(DeviceBindingSuggestion)
            .where(DeviceBindingSuggestion.device_id == str(device_id), DeviceBindingSuggestion.id == str(suggestion_id))
            .limit(1)
        )
        suggestion = result.scalar_one_or_none()
        if suggestion is None:
            raise ValueError("suggestion not found")
        allowed = set(_BINDING_FIELDS)
        selected = [field for field in fields if field in allowed]
        if not selected:
            raise ValueError("no allowed fields selected")
        current = binding_to_dict(await self.get_binding(device_id))
        suggested = dict(suggestion.suggested_binding or {})
        payload = {**current, **{field: suggested.get(field) for field in selected}}
        await self.upsert_binding(
            device_id,
            payload,
            updated_by=reviewed_by,
            reason=reason or "Applied agent profile binding suggestion",
        )
        now = datetime.now(timezone.utc)
        suggestion.status = "applied"
        suggestion.reviewed_by = reviewed_by
        suggestion.reviewed_at = now
        suggestion.review_note = _clean_binding_text(reason, max_length=1000) if reason else None
        suggestion.updated_at = now
        await self.session.flush()
        return suggestion

    async def ignore_binding_suggestion(
        self,
        *,
        device_id: str,
        suggestion_id: str,
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> DeviceBindingSuggestion:
        result = await self.session.execute(
            select(DeviceBindingSuggestion)
            .where(DeviceBindingSuggestion.device_id == str(device_id), DeviceBindingSuggestion.id == str(suggestion_id))
            .limit(1)
        )
        suggestion = result.scalar_one_or_none()
        if suggestion is None:
            raise ValueError("suggestion not found")
        now = datetime.now(timezone.utc)
        suggestion.status = "ignored"
        suggestion.reviewed_by = reviewed_by
        suggestion.reviewed_at = now
        suggestion.review_note = _clean_binding_text(reason, max_length=1000) if reason else None
        suggestion.updated_at = now
        await self.session.flush()
        return suggestion

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
