from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticCapability, ToolPresentationOverride
from diagnostics.capability_models import CapabilityDescriptor


SUPPORTED_BLOCK_TYPES = {
    "field_grid",
    "metric_cards",
    "table",
    "checklist",
    "timeline",
    "artifact_list",
    "raw_json",
}
DANGEROUS_KEYS = {"script", "dangerouslySetInnerHTML", "__html"}
DANGEROUS_VALUE_FRAGMENTS = ("<script", "</script", "javascript:", "dangerouslysetinnerhtml", "__html")


class PresentationSchemaValidationError(ValueError):
    def __init__(self, message: str, *, path: str = "$", code: str = "PRESENTATION_SCHEMA_INVALID") -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.code = code


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def _validate_safe_value(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in DANGEROUS_KEYS:
                raise PresentationSchemaValidationError(f"Dangerous key is not allowed: {key_text}", path=f"{path}.{key_text}")
            _validate_safe_value(child, path=f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_safe_value(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(fragment in lowered for fragment in DANGEROUS_VALUE_FRAGMENTS):
            raise PresentationSchemaValidationError("Dangerous string value is not allowed", path=path)


def validate_presentation_schema(schema: Any) -> dict[str, Any]:
    if not _is_plain_object(schema):
        raise PresentationSchemaValidationError("presentation_schema must be a JSON object", path="$")
    if "version" in schema and not isinstance(schema.get("version"), str):
        raise PresentationSchemaValidationError("version must be a string", path="$.version")
    if "kind" in schema and not isinstance(schema.get("kind"), str):
        raise PresentationSchemaValidationError("kind must be a string", path="$.kind")
    blocks = schema.get("blocks")
    if blocks is not None:
        if not isinstance(blocks, list):
            raise PresentationSchemaValidationError("blocks must be an array", path="$.blocks")
        for index, block in enumerate(blocks):
            block_path = f"$.blocks[{index}]"
            if not isinstance(block, dict):
                raise PresentationSchemaValidationError("block must be an object", path=block_path)
            block_type = block.get("type")
            if not isinstance(block_type, str):
                raise PresentationSchemaValidationError("block.type must be a string", path=f"{block_path}.type")
            if block_type not in SUPPORTED_BLOCK_TYPES:
                raise PresentationSchemaValidationError(f"Unsupported block type: {block_type}", path=f"{block_path}.type")
    _validate_safe_value(schema, path="$")
    return dict(schema)


def _schema_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def descriptor_with_effective_presentation(
    descriptor: CapabilityDescriptor,
    override: ToolPresentationOverride | None,
) -> CapabilityDescriptor:
    module_default = _schema_or_empty(descriptor.presentation_schema)
    if override is not None and override.enabled:
        effective_schema = _schema_or_empty(override.presentation_schema)
        return replace(
            descriptor,
            effective_presentation_schema=effective_schema,
            presentation_schema_source="server_override",
            has_presentation_override=True,
        )
    if module_default:
        return replace(
            descriptor,
            effective_presentation_schema=module_default,
            presentation_schema_source="module_default",
            has_presentation_override=False,
        )
    return replace(
        descriptor,
        effective_presentation_schema={},
        presentation_schema_source="none",
        has_presentation_override=False,
    )


class ToolPresentationOverrideService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_override(
        self,
        tool_id: str,
        *,
        tool_version: str | None = None,
        scope: str = "global",
        enabled_only: bool = True,
    ) -> ToolPresentationOverride | None:
        conditions = [
            ToolPresentationOverride.tool_id == tool_id,
            ToolPresentationOverride.scope == scope,
        ]
        if tool_version is None:
            conditions.append(ToolPresentationOverride.tool_version.is_(None))
        else:
            conditions.append(ToolPresentationOverride.tool_version == tool_version)
        if enabled_only:
            conditions.append(ToolPresentationOverride.enabled.is_(True))
        result = await self.session.execute(select(ToolPresentationOverride).where(and_(*conditions)).limit(1))
        return result.scalar_one_or_none()

    async def upsert_override(
        self,
        tool_id: str,
        presentation_schema: Any,
        *,
        tool_version: str | None = None,
        scope: str = "global",
        enabled: bool = True,
        actor_id: str | None = None,
    ) -> ToolPresentationOverride:
        validated_schema = validate_presentation_schema(presentation_schema)
        result = await self.session.execute(
            select(ToolPresentationOverride)
            .where(
                ToolPresentationOverride.tool_id == tool_id,
                ToolPresentationOverride.scope == scope,
                ToolPresentationOverride.tool_version.is_(None)
                if tool_version is None
                else ToolPresentationOverride.tool_version == tool_version,
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = ToolPresentationOverride(
                id=str(uuid.uuid4()),
                tool_id=tool_id,
                tool_version=tool_version,
                scope=scope,
                presentation_schema=validated_schema,
                enabled=enabled,
                created_by=actor_id,
                updated_by=actor_id,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        else:
            row.presentation_schema = validated_schema
            row.enabled = enabled
            row.updated_by = actor_id
            row.updated_at = now
        await self.session.flush()
        return row

    async def delete_or_disable_override(
        self,
        tool_id: str,
        *,
        tool_version: str | None = None,
        scope: str = "global",
        actor_id: str | None = None,
    ) -> None:
        row = await self.get_override(tool_id, tool_version=tool_version, scope=scope, enabled_only=False)
        if row is None:
            return
        await self.session.delete(row)
        await self.session.flush()

    async def get_presentation_detail(
        self,
        descriptor: CapabilityDescriptor,
        *,
        tool_version: str | None = None,
        scope: str = "global",
    ) -> dict[str, Any]:
        override = await self.get_override(descriptor.id, tool_version=tool_version, scope=scope)
        module_default = _schema_or_empty(descriptor.presentation_schema)
        effective = descriptor_with_effective_presentation(descriptor, override)
        return {
            "tool_id": descriptor.id,
            "tool_version": tool_version,
            "module_default_schema": module_default,
            "override_schema": _schema_or_empty(override.presentation_schema) if override is not None else None,
            "effective_schema": _schema_or_empty(effective.effective_presentation_schema),
            "source": effective.presentation_schema_source,
            "enabled": bool(override.enabled) if override is not None else False,
            "updated_at": _datetime_iso(override.updated_at) if override is not None else None,
            "updated_by": override.updated_by if override is not None else None,
        }

    async def apply_to_capabilities(self, capabilities: list[CapabilityDescriptor]) -> list[CapabilityDescriptor]:
        if not capabilities:
            return []
        tool_ids = [item.id for item in capabilities]
        result = await self.session.execute(
            select(ToolPresentationOverride).where(
                ToolPresentationOverride.tool_id.in_(tool_ids),
                ToolPresentationOverride.scope == "global",
                ToolPresentationOverride.tool_version.is_(None),
                ToolPresentationOverride.enabled.is_(True),
            )
        )
        overrides = {row.tool_id: row for row in result.scalars().all()}
        return [descriptor_with_effective_presentation(item, overrides.get(item.id)) for item in capabilities]

    async def descriptor_from_persisted_capability(self, tool_id: str) -> CapabilityDescriptor | None:
        result = await self.session.execute(select(DiagnosticCapability).where(DiagnosticCapability.capability_id == tool_id).limit(1))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        raw = dict(row.descriptor_json or {})
        raw.setdefault("id", row.capability_id)
        raw.setdefault("title", row.title)
        raw.setdefault("description", row.description or "")
        raw.setdefault("provider_id", row.provider_id)
        raw.setdefault("execution_target", row.execution_target)
        allowed = set(CapabilityDescriptor.__dataclass_fields__.keys())
        return CapabilityDescriptor(**{key: value for key, value in raw.items() if key in allowed})
