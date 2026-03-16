"""
Helpers for normalized module manifest handling on the server side.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_ENTRYPOINT = "module:register"
DEFAULT_PLATFORMS = ["any"]
MANIFEST_V2 = 2
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


def _ensure_list(value: Any, default: Optional[List[Any]] = None) -> List[Any]:
    if isinstance(value, list):
        return value
    return list(default or [])


def _normalize_platforms(value: Any) -> List[str]:
    platforms = _ensure_list(value, DEFAULT_PLATFORMS)
    normalized = [str(item).strip().lower() for item in platforms if str(item).strip()]
    return normalized or list(DEFAULT_PLATFORMS)


def _normalize_tool_name(module_name: str, raw_tool: Any, fallback: str) -> str:
    candidate = str(raw_tool or fallback).strip()
    if not candidate:
        candidate = fallback
    if "." not in candidate:
        candidate = f"{module_name}.{candidate}"
    return candidate


def _normalize_tool_entry(module_name: str, raw_tool: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []

    tool_name = _normalize_tool_name(
        module_name,
        raw_tool.get("tool") or raw_tool.get("name"),
        f"{module_name}.run",
    )
    short_name = tool_name.split(".", 1)[1]
    method_name = str(raw_tool.get("method") or short_name or "run").strip() or "run"
    params_schema = raw_tool.get("params_schema")
    if params_schema is None:
        params_schema = {}
    elif not isinstance(params_schema, (dict, list)):
        errors.append(f"Tool '{tool_name}' has invalid params_schema type")
        params_schema = {}

    presets = raw_tool.get("presets")
    if presets is None:
        presets = []
    elif not isinstance(presets, list):
        errors.append(f"Tool '{tool_name}' has invalid presets type")
        presets = []

    capabilities = raw_tool.get("capabilities")
    if capabilities is None:
        capabilities = []
    elif not isinstance(capabilities, list):
        warnings.append(f"Tool '{tool_name}' capabilities normalized to empty list")
        capabilities = []

    metadata = raw_tool.get("metadata") or {}
    if not isinstance(metadata, dict):
        errors.append(f"Tool '{tool_name}' has invalid metadata type")
        metadata = {}

    metadata_platforms = _normalize_platforms(metadata.get("platforms") or DEFAULT_PLATFORMS)
    normalized = {
        "tool": tool_name,
        "method": method_name,
        "description": str(raw_tool.get("description") or "").strip(),
        "params_schema": params_schema,
        "presets": presets,
        "capabilities": capabilities,
        "metadata": {
            "domain": str(metadata.get("domain") or module_name).strip() or module_name,
            "platforms": metadata_platforms,
            "risk_level": str(metadata.get("risk_level") or raw_tool.get("risk_level") or "safe_readonly").strip() or "safe_readonly",
            "requires_consent": bool(metadata.get("requires_consent", False)),
            "timeout_sec": metadata.get("timeout_sec"),
            "idempotent": bool(metadata.get("idempotent", False)),
            "allow_roles": metadata.get("allow_roles"),
            "scopes": _ensure_list(metadata.get("scopes"), []),
            "origin": str(metadata.get("origin") or "managed"),
        },
    }

    if not tool_name.startswith(f"{module_name}."):
        errors.append(f"Tool '{tool_name}' must belong to module '{module_name}'")

    return normalized, warnings, errors


def manifest_summary_from_manifest(manifest_json: Dict[str, Any]) -> Dict[str, Any]:
    tools_summary: List[Dict[str, Any]] = []
    for tool in manifest_json.get("tools", []):
        tools_summary.append(
            {
                "name": tool.get("tool"),
                "tool": tool.get("tool"),
                "method": tool.get("method"),
                "description": tool.get("description") or "",
                "params_schema": tool.get("params_schema") or {},
                "presets": tool.get("presets") or [],
                "capabilities": tool.get("capabilities") or [],
                "metadata": tool.get("metadata") or {},
            }
        )

    return {
        "module_name": manifest_json.get("module_name"),
        "module_version": manifest_json.get("module_version"),
        "entrypoint": manifest_json.get("entrypoint") or DEFAULT_ENTRYPOINT,
        "description": manifest_json.get("description") or "",
        "platforms": manifest_json.get("platforms") or list(DEFAULT_PLATFORMS),
        "requirements": manifest_json.get("requirements") or [],
        "optional_requirements": manifest_json.get("optional_requirements") or [],
        "tools": tools_summary,
    }


def normalize_manifest(manifest: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Normalize manifest v2 or legacy v1 to a single v2-shaped contract.
    """
    validation = {
        "preflight_status": "failed",
        "validation_status": "invalid",
        "legacy_manifest": False,
        "warnings": [],
        "errors": {
            "manifest": [],
            "tools": [],
            "metadata": [],
            "smoke": [],
        },
    }

    if not isinstance(manifest, dict):
        validation["errors"]["manifest"].append("manifest.json must be a JSON object")
        return None, validation, None

    source = copy.deepcopy(manifest)
    module_name = str(source.get("module_name") or "").strip()
    module_version = str(source.get("module_version") or "").strip()
    entrypoint = str(source.get("entrypoint") or DEFAULT_ENTRYPOINT).strip() or DEFAULT_ENTRYPOINT
    if not module_name:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'module_name'")
    if not module_version:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'module_version'")

    manifest_version = source.get("manifest_version")
    is_v2 = manifest_version == MANIFEST_V2
    if manifest_version not in (None, MANIFEST_V2):
        validation["errors"]["manifest"].append(f"Unsupported manifest_version: {manifest_version}")

    normalized: Dict[str, Any] = {
        "manifest_version": MANIFEST_V2,
        "module_name": module_name,
        "module_version": module_version,
        "description": str(source.get("description") or "").strip(),
        "entrypoint": entrypoint,
        "platforms": _normalize_platforms(source.get("platforms")),
        "requirements": _ensure_list(source.get("requirements"), []),
        "optional_requirements": _ensure_list(source.get("optional_requirements"), []),
        "min_agent_version": source.get("min_agent_version"),
        "tools": [],
    }

    tools_raw = source.get("tools")
    if tools_raw is None:
        tools_raw = []
    if not isinstance(tools_raw, list):
        validation["errors"]["tools"].append("manifest.json: 'tools' must be a list")
        tools_raw = []

    if not is_v2:
        validation["legacy_manifest"] = True
        validation["validation_status"] = "compat"
        validation["warnings"].append("Legacy manifest normalized to v2-compat contract")

    for raw_tool in tools_raw:
        if not isinstance(raw_tool, dict):
            validation["errors"]["tools"].append("Tool entry must be a JSON object")
            continue
        normalized_tool, warnings, errors = _normalize_tool_entry(module_name, raw_tool)
        validation["warnings"].extend(warnings)
        validation["errors"]["tools"].extend(errors)
        normalized["tools"].append(normalized_tool)

    if not normalized["tools"]:
        fallback_tool_name = f"{module_name}.run" if module_name else "unknown.run"
        normalized["tools"].append(
            {
                "tool": fallback_tool_name,
                "method": "run",
                "description": normalized["description"],
                "params_schema": {},
                "presets": [],
                "capabilities": [],
                "metadata": {
                    "domain": module_name or "unknown",
                    "platforms": normalized["platforms"],
                    "risk_level": "safe_readonly",
                    "requires_consent": False,
                    "timeout_sec": None,
                    "idempotent": False,
                    "allow_roles": None,
                    "scopes": [],
                    "origin": "managed" if is_v2 else "legacy",
                },
            }
        )
        validation["warnings"].append("Manifest did not declare tools; fallback tool contract was generated")

    if is_v2 and not SEMVER_RE.match(module_version):
        validation["errors"]["manifest"].append("manifest.json: module_version must be semver for manifest v2")

    errors_total = sum(len(items) for items in validation["errors"].values())
    if errors_total == 0:
        validation["preflight_status"] = "passed"
        if validation["validation_status"] != "compat":
            validation["validation_status"] = "passed"
        manifest_summary = manifest_summary_from_manifest(normalized)
        return normalized, validation, manifest_summary

    return None, validation, None


def attach_smoke_result(
    manifest_json: Optional[Dict[str, Any]],
    validation_json: Dict[str, Any],
    smoke_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    updated = copy.deepcopy(validation_json)
    updated["smoke"] = smoke_result or {}
    if not manifest_json or not smoke_result:
        return updated

    runtime_tools = smoke_result.get("tools") or []
    runtime_tool_names = {tool.get("tool") for tool in runtime_tools if tool.get("tool")}
    runtime_methods = {tool.get("tool"): tool.get("method_name") for tool in runtime_tools if tool.get("tool")}

    for declared in manifest_json.get("tools", []):
        declared_name = declared.get("tool")
        if declared_name not in runtime_tool_names:
            updated["errors"]["smoke"].append(f"Declared tool '{declared_name}' was not registered at runtime")
            continue
        runtime_method = runtime_methods.get(declared_name)
        declared_method = declared.get("method")
        if declared_method and runtime_method and declared_method != runtime_method:
            updated["errors"]["smoke"].append(
                f"Tool '{declared_name}' runtime method mismatch: manifest={declared_method} runtime={runtime_method}"
            )

    if updated["errors"]["smoke"]:
        updated["preflight_status"] = "failed"
        updated["validation_status"] = "failed"
    elif updated.get("preflight_status") == "passed":
        updated["validation_status"] = "compat" if updated.get("legacy_manifest") else "passed"

    return updated


def get_module_manifest(module: Any) -> Dict[str, Any]:
    manifest_json = getattr(module, "manifest_json", None)
    if isinstance(manifest_json, dict) and manifest_json:
        return manifest_json

    summary = getattr(module, "manifest_summary", None) or {}
    normalized, validation, _ = normalize_manifest(summary if isinstance(summary, dict) else {})
    if normalized:
        return normalized
    return {
        "manifest_version": 1,
        "module_name": getattr(module, "module_name", None),
        "module_version": getattr(module, "version", None),
        "entrypoint": DEFAULT_ENTRYPOINT,
        "description": "",
        "platforms": list(DEFAULT_PLATFORMS),
        "requirements": [],
        "optional_requirements": [],
        "tools": [],
    }


def get_module_validation(module: Any) -> Dict[str, Any]:
    validation_json = getattr(module, "validation_json", None)
    if isinstance(validation_json, dict) and validation_json:
        return validation_json
    legacy = not bool(getattr(module, "manifest_json", None))
    return {
        "preflight_status": "passed",
        "validation_status": "compat" if legacy else "passed",
        "legacy_manifest": legacy,
        "warnings": ["Validation report reconstructed from legacy module record"] if legacy else [],
        "errors": {"manifest": [], "tools": [], "metadata": [], "smoke": []},
    }


def module_to_api_record(module: Any, include_detail: bool = False) -> Dict[str, Any]:
    manifest_json = get_module_manifest(module)
    validation_json = get_module_validation(module)
    tools = manifest_json.get("tools") or []
    record = {
        "module_name": module.module_name,
        "version": module.version,
        "sha256": module.sha256,
        "size": module.size,
        "created_at": module.created_at.isoformat() if getattr(module, "created_at", None) else None,
        "uploaded_by": getattr(module, "uploaded_by", None),
        "manifest_version": 1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version", MANIFEST_V2),
        "legacy_manifest": bool(validation_json.get("legacy_manifest")),
        "validation_status": validation_json.get("validation_status", "unknown"),
        "preflight_status": validation_json.get("preflight_status", "unknown"),
        "warnings": validation_json.get("warnings") or [],
        "platforms": manifest_json.get("platforms") or list(DEFAULT_PLATFORMS),
        "tools_count": len(tools),
        "has_full_metadata": all(isinstance(tool.get("metadata"), dict) and tool.get("metadata") for tool in tools),
    }
    if include_detail:
        record.update(
            {
                "manifest_json": manifest_json,
                "validation_json": validation_json,
                "tools": tools,
                "requirements": manifest_json.get("requirements") or [],
                "optional_requirements": manifest_json.get("optional_requirements") or [],
            }
        )
    return record

