from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceInventoryBinding, DeviceInventoryRefreshPolicy, DeviceInventorySnapshot
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.presentation_overrides import ToolPresentationOverrideService
from shared.builtin_tool_descriptors import INVENTORY_COLLECT_TOOL_ID, get_builtin_tool_descriptor


INVENTORY_TOOL_ID = INVENTORY_COLLECT_TOOL_ID
_BINDING_LIMITS = {
    "building": 120,
    "floor": 64,
    "room": 120,
    "department": 160,
    "responsible_user": 160,
    "responsible_user_login": 160,
    "inventory_number": 120,
    "notes": 2000,
}


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


def normalize_binding_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for key, limit in _BINDING_LIMITS.items():
        result[key] = _clean_binding_text(payload.get(key), max_length=limit)
    return result


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
    ) -> DeviceInventoryBinding:
        normalized = normalize_binding_payload(payload)
        row = await self.get_binding(device_id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = DeviceInventoryBinding(device_id=str(device_id), updated_at=now)
            self.session.add(row)
        for key, value in normalized.items():
            setattr(row, key, value)
        row.updated_by = updated_by
        row.updated_at = now
        await self.session.flush()
        return row

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
