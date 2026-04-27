"""Helpers for playbook command catalog entries and manifests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _enum_from_schema(schema: dict[str, Any], path: str) -> list[str]:
    current: Any = schema
    for part in path.split("."):
        if not isinstance(current, dict):
            return []
        properties = current.get("properties")
        if isinstance(properties, dict) and part in properties:
            current = properties.get(part)
            continue
        current = current.get(part)
    enum_values = current.get("enum") if isinstance(current, dict) else None
    return _string_list(enum_values)


def normalize_output_contract(
    raw_contract: Any,
    *,
    output_schema: dict[str, Any] | None = None,
    error_codes: list[str] | None = None,
) -> dict[str, Any]:
    contract = deepcopy(raw_contract) if isinstance(raw_contract, dict) else {}
    schema = output_schema or {}
    status_values = _string_list(contract.get("status_values"))
    legacy_status = contract.get("status")
    if not status_values and isinstance(legacy_status, str) and "|" in legacy_status:
        status_values = [item.strip() for item in legacy_status.split("|") if item.strip()]
    if not status_values:
        status_values = _enum_from_schema(schema, "status") or _enum_from_schema(schema, "result.status")
    if not status_values:
        status_values = ["ok", "error"]

    success_values = _string_list(contract.get("success_values"))
    error_values = _string_list(contract.get("error_values"))
    if not success_values:
        success_values = [value for value in ("ok", "success") if value in status_values][:1]
    if not error_values:
        error_values = [value for value in ("error", "failed") if value in status_values][:1]

    compact_fields = []
    for item in _as_list(contract.get("compact_fields")):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        compact_fields.append(
            {
                "path": path,
                "label": str(item.get("label") or path).strip(),
                "type": str(item.get("type") or "string").strip() or "string",
            }
        )

    return {
        "schema_version": str(contract.get("schema_version") or "1.0").strip() or "1.0",
        "status_path": str(contract.get("status_path") or "result.status").strip(),
        "status_values": status_values,
        "success_values": success_values,
        "error_values": error_values,
        "summary_path": str(contract.get("summary_path") or "result.output.summary").strip(),
        "error_code_path": str(contract.get("error_code_path") or "result.error.code").strip(),
        "compact_fields": compact_fields,
        "error_codes": _string_list(error_codes),
    }


def build_condition_hints(output_contract: dict[str, Any], error_codes: list[str]) -> dict[str, Any]:
    status_path = str(output_contract.get("status_path") or "result.status")
    error_code_path = str(output_contract.get("error_code_path") or "result.error.code")
    templates: list[dict[str, str]] = []
    for value in _string_list(output_contract.get("status_values")):
        templates.append(
            {
                "label": f"status == {value}",
                "expression": f"{{step}}.output.{status_path} == '{value}'",
            }
        )
    for code in _string_list(error_codes):
        templates.append(
            {
                "label": f"error_code == {code}",
                "expression": f"{{step}}.output.{error_code_path} == '{code}'",
            }
        )
    return {
        "status_path": status_path,
        "status_values": _string_list(output_contract.get("status_values")),
        "success_values": _string_list(output_contract.get("success_values")),
        "error_values": _string_list(output_contract.get("error_values")),
        "summary_path": str(output_contract.get("summary_path") or "result.output.summary"),
        "error_code_path": error_code_path,
        "error_codes": _string_list(error_codes),
        "condition_templates": templates,
        "compact_fields": _as_list(output_contract.get("compact_fields")),
    }


def normalize_tool_catalog_entry(raw_tool: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Normalize an agent/server tool into the low-code playbook catalog shape."""
    spec = _as_dict(raw_tool.get("spec"))
    metadata = _first_dict(spec.get("metadata"), raw_tool.get("metadata"))
    dependencies = _first_dict(spec.get("dependencies"), raw_tool.get("dependencies"))

    tool_name = str(raw_tool.get("tool") or raw_tool.get("name") or "").strip()
    module_name = str(raw_tool.get("module") or raw_tool.get("module_name") or "").strip()
    if not module_name and "." in tool_name:
        module_name = tool_name.split(".", 1)[0]

    params_schema = _as_dict(spec.get("params_schema") or raw_tool.get("params_schema"))
    output_schema = _as_dict(spec.get("output_schema") or raw_tool.get("output_schema"))
    raw_presets = _as_list(spec.get("presets") or raw_tool.get("presets"))
    presets: list[dict[str, Any]] = []
    for raw_preset in raw_presets:
        if not isinstance(raw_preset, dict):
            continue
        preset_id = str(raw_preset.get("preset_id") or raw_preset.get("id") or raw_preset.get("key") or "").strip()
        if not preset_id:
            continue
        presets.append(
            {
                "id": preset_id,
                "preset_id": preset_id,
                "label": str(raw_preset.get("label") or raw_preset.get("title") or raw_preset.get("name") or preset_id),
                "description": str(raw_preset.get("description") or "").strip() or None,
                "params": _as_dict(raw_preset.get("params")),
            }
        )

    platforms = metadata.get("platforms") or raw_tool.get("platforms") or ["any"]
    if not isinstance(platforms, list) or not platforms:
        platforms = ["any"]

    error_codes = spec.get("error_codes") or raw_tool.get("error_codes") or []
    if not isinstance(error_codes, list):
        error_codes = []
    error_codes = [str(item) for item in error_codes]
    output_contract = normalize_output_contract(
        spec.get("output_contract") or raw_tool.get("output_contract"),
        output_schema=output_schema,
        error_codes=error_codes,
    )
    condition_hints = build_condition_hints(output_contract, error_codes)

    min_agent_version = (
        dependencies.get("min_agent_version")
        or metadata.get("min_agent_version")
        or raw_tool.get("min_agent_version")
    )
    normalized = {
        "id": tool_name,
        "label": str(raw_tool.get("label") or raw_tool.get("title") or tool_name),
        "tool": tool_name,
        "tool_name": tool_name,
        "block_type": "diagnostic",
        "module_kind": "diagnostic",
        "module_name": module_name or None,
        "description": str(raw_tool.get("description") or "").strip(),
        "default_params": _as_dict(raw_tool.get("default_params")),
        "changes_device": bool(metadata.get("changes_device", False)),
        "requires_confirmation": bool(metadata.get("requires_confirmation") or metadata.get("requires_consent")),
        "requires_consent": bool(metadata.get("requires_consent")),
        "output_contract": output_contract,
        "condition_hints": condition_hints,
        "source": source,
        "install_required": bool(raw_tool.get("install_required")),
        "install_policy": "lazy" if raw_tool.get("install_required") else "preinstalled",
        "supported_platforms": [str(item) for item in platforms],
        "platforms": [str(item) for item in platforms],
        "min_agent_version": str(min_agent_version).strip() if min_agent_version else None,
        "risk_level": str(spec.get("risk_level") or metadata.get("risk_level") or "safe_read"),
        "params_schema": params_schema,
        "output_schema": output_schema,
        "presets": presets,
        "error_codes": error_codes,
    }
    return normalized


def expand_preset_params(
    tool_entry: dict[str, Any],
    *,
    preset_id: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return concrete params for a selected preset plus explicit overrides."""
    params: dict[str, Any] = {}
    wanted = str(preset_id or "").strip()
    if wanted:
        for preset in tool_entry.get("presets") or []:
            if not isinstance(preset, dict):
                continue
            current_id = str(preset.get("preset_id") or preset.get("id") or preset.get("key") or "").strip()
            if current_id == wanted:
                params.update(_as_dict(preset.get("params")))
                break
    if overrides:
        params.update(deepcopy(overrides))
    return params


def build_required_tools_manifest(
    blocks: list[dict[str, Any]],
    catalog_by_tool: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the playbook-level command requirements used by preflight/reporting."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in blocks:
        tool_name = str(block.get("tool") or "").strip()
        if not tool_name or tool_name in seen:
            continue
        seen.add(tool_name)
        entry = catalog_by_tool.get(tool_name) or _as_dict(block.get("tool_manifest"))
        result.append(
            {
                "tool": tool_name,
                "module_name": entry.get("module_name"),
                "source": entry.get("source"),
                "install_required": bool(entry.get("install_required")),
                "install_policy": str(block.get("install_policy") or entry.get("install_policy") or "preinstalled"),
                "supported_platforms": _as_list(entry.get("supported_platforms") or entry.get("platforms") or ["any"]),
                "min_agent_version": entry.get("min_agent_version"),
                "risk_level": entry.get("risk_level"),
                "requires_consent": bool(entry.get("requires_consent") or entry.get("requires_confirmation")),
                "params_schema": _as_dict(entry.get("params_schema")),
                "output_schema": _as_dict(entry.get("output_schema")),
                "output_contract": _as_dict(entry.get("output_contract")),
                "condition_hints": _as_dict(entry.get("condition_hints")),
                "presets": _as_list(entry.get("presets")),
                "error_codes": _as_list(entry.get("error_codes")),
            }
        )
    return result
