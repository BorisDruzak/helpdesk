"""
Helpers for normalized module manifest handling on the server side.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from shared.tool_contracts import is_reserved_namespace, normalize_risk_level
except ModuleNotFoundError:  # pragma: no cover - defensive path for nested cwd entrypoints
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from shared.tool_contracts import is_reserved_namespace, normalize_risk_level


DEFAULT_ENTRYPOINT = "module:register"
DEFAULT_PLATFORMS = ["any"]
ALLOWED_PLATFORMS = {"any", "linux", "win32", "darwin"}
ALLOWED_OWNER_SCOPES = {"core", "platform", "builtin", "vendor"}
ALLOWED_LIFECYCLES = {"experimental", "stable", "deprecated", "removed"}
MANIFEST_V2 = 2
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
TOOL_KEY_RE = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
PY_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CONTRACT_PATH_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")


def _ensure_list(value: Any, default: Optional[List[Any]] = None) -> List[Any]:
    if isinstance(value, list):
        return value
    return list(default or [])


def _normalize_platforms(value: Any) -> List[str]:
    platforms = _ensure_list(value, DEFAULT_PLATFORMS)
    normalized = [str(item).strip().lower() for item in platforms if str(item).strip()]
    return normalized or list(DEFAULT_PLATFORMS)


def _validate_platforms(platforms: List[str], field_name: str) -> List[str]:
    errors: List[str] = []
    invalid = [item for item in platforms if item not in ALLOWED_PLATFORMS]
    if invalid:
        errors.append(
            f"{field_name} contains unsupported values: {', '.join(sorted(dict.fromkeys(invalid)))}"
        )
    if "any" in platforms and len(platforms) > 1:
        errors.append(f"{field_name} cannot combine 'any' with platform-specific values")
    return errors


def _normalize_bool_field(
    raw_value: Any,
    *,
    default: bool,
    field_name: str,
    errors: List[str],
) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    errors.append(f"{field_name} must be a boolean")
    return default


def _normalize_optional_string_list(
    raw_value: Any,
    *,
    field_name: str,
    errors: List[str],
) -> Optional[List[str]]:
    if raw_value is None:
        return None
    if not isinstance(raw_value, list) or any(not isinstance(item, str) or not item.strip() for item in raw_value):
        errors.append(f"{field_name} must be a list of non-empty strings")
        return None
    return [item.strip() for item in raw_value]


def _normalize_string_list(
    raw_value: Any,
    *,
    field_name: str,
    errors: List[str],
) -> List[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list) or any(not isinstance(item, str) or not item.strip() for item in raw_value):
        errors.append(f"{field_name} must be a list of non-empty strings")
        return []
    return [item.strip() for item in raw_value]


def _normalize_optional_timeout(raw_value: Any, *, field_name: str, errors: List[str]) -> Optional[int]:
    if raw_value is None:
        return None
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        errors.append(f"{field_name} must be an integer")
        return None
    if raw_value < 1 or raw_value > 3600:
        errors.append(f"{field_name} must be between 1 and 3600")
        return None
    return raw_value


def _normalize_contract_path(raw_value: Any, *, field_name: str, errors: List[str], default: str) -> str:
    if raw_value is None:
        return default
    if not isinstance(raw_value, str) or not raw_value.strip():
        errors.append(f"{field_name} must be a non-empty dotted path")
        return default
    value = raw_value.strip()
    if not CONTRACT_PATH_RE.match(value):
        errors.append(f"{field_name} must be a dotted path like result.status")
        return default
    return value


def _normalize_output_contract(raw_value: Any, *, field_name: str, errors: List[str]) -> Dict[str, Any]:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, dict):
        errors.append(f"{field_name} must be an object")
        return {}

    raw_status_values = raw_value.get("status_values")
    if raw_status_values is None:
        errors.append(f"{field_name}.status_values is required when output_contract is declared")
        status_values: List[str] = []
    else:
        status_values = _normalize_string_list(
            raw_status_values,
            field_name=f"{field_name}.status_values",
            errors=errors,
        )
    if len(status_values) != len(set(status_values)):
        errors.append(f"{field_name}.status_values must not contain duplicates")
        status_values = list(dict.fromkeys(status_values))

    success_values = _normalize_string_list(
        raw_value.get("success_values"),
        field_name=f"{field_name}.success_values",
        errors=errors,
    )
    error_values = _normalize_string_list(
        raw_value.get("error_values"),
        field_name=f"{field_name}.error_values",
        errors=errors,
    )
    if status_values:
        if not success_values:
            success_values = [value for value in ("ok", "success") if value in status_values][:1]
        if not error_values:
            error_values = [value for value in ("error", "failed") if value in status_values][:1]
    for bucket_name, bucket_values in (("success_values", success_values), ("error_values", error_values)):
        unknown = [value for value in bucket_values if value not in status_values]
        if unknown:
            errors.append(
                f"{field_name}.{bucket_name} contains values outside status_values: {', '.join(unknown)}"
            )

    compact_fields: List[Dict[str, Any]] = []
    raw_compact_fields = raw_value.get("compact_fields")
    if raw_compact_fields is not None:
        if not isinstance(raw_compact_fields, list):
            errors.append(f"{field_name}.compact_fields must be a list")
        else:
            for index, item in enumerate(raw_compact_fields, start=1):
                if not isinstance(item, dict):
                    errors.append(f"{field_name}.compact_fields[{index}] must be an object")
                    continue
                path = _normalize_contract_path(
                    item.get("path"),
                    field_name=f"{field_name}.compact_fields[{index}].path",
                    errors=errors,
                    default="result.output",
                )
                compact_fields.append(
                    {
                        "path": path,
                        "label": str(item.get("label") or path).strip(),
                        "type": str(item.get("type") or "string").strip() or "string",
                    }
                )

    return {
        "schema_version": str(raw_value.get("schema_version") or "1.0").strip() or "1.0",
        "status_path": _normalize_contract_path(
            raw_value.get("status_path"),
            field_name=f"{field_name}.status_path",
            errors=errors,
            default="result.status",
        ),
        "status_values": status_values,
        "success_values": success_values,
        "error_values": error_values,
        "summary_path": _normalize_contract_path(
            raw_value.get("summary_path"),
            field_name=f"{field_name}.summary_path",
            errors=errors,
            default="result.output.summary",
        ),
        "error_code_path": _normalize_contract_path(
            raw_value.get("error_code_path"),
            field_name=f"{field_name}.error_code_path",
            errors=errors,
            default="result.error.code",
        ),
        "compact_fields": compact_fields,
    }


def _normalize_tool_name(module_name: str, raw_tool: Any, fallback: str) -> str:
    candidate = str(raw_tool or fallback).strip()
    if not candidate:
        candidate = fallback
    if "." not in candidate:
        candidate = f"{module_name}.{candidate}"
    return candidate


def _normalize_aliases(module_name: str, canonical_tool_name: str, raw_aliases: Any) -> List[str]:
    aliases = []
    for alias in _ensure_list(raw_aliases, []):
        alias_value = str(alias or "").strip()
        if not alias_value:
            continue
        normalized_alias = alias_value if "." in alias_value else f"{module_name}.{alias_value}"
        if normalized_alias != canonical_tool_name:
            aliases.append(normalized_alias)
    short_name = canonical_tool_name.split(".", 1)[-1]
    legacy_alias = f"{module_name}.{short_name}"
    if legacy_alias != canonical_tool_name:
        aliases.append(legacy_alias)
    return list(dict.fromkeys(aliases))


def _normalize_tool_entry(
    module_name: str,
    raw_tool: Dict[str, Any],
    *,
    compat_legacy_defaults: bool = False,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []

    tool_name = _normalize_tool_name(
        module_name,
        raw_tool.get("canonical_name") or raw_tool.get("tool") or raw_tool.get("name"),
        f"{module_name}.run",
    )
    if not TOOL_KEY_RE.match(tool_name):
        errors.append(f"Tool '{tool_name}' must use a semantic id like 'dns.resolve' or 'network.ping'")
    short_name = tool_name.split(".", 1)[1]
    method_name = str(raw_tool.get("method") or short_name or "run").strip() or "run"
    if not PY_IDENTIFIER_RE.match(method_name):
        errors.append(f"Tool '{tool_name}' has invalid method '{method_name}'")
    params_schema = raw_tool.get("params_schema")
    if params_schema is None:
        params_schema = {}
    elif not isinstance(params_schema, dict):
        errors.append(f"Tool '{tool_name}' has invalid params_schema type")
        params_schema = {}

    presets = raw_tool.get("presets")
    if presets is None:
        presets = []
    elif not isinstance(presets, list):
        errors.append(f"Tool '{tool_name}' has invalid presets type")
        presets = []

    output_schema = raw_tool.get("output_schema")
    if output_schema is None:
        output_schema = {}
    elif not isinstance(output_schema, dict):
        errors.append(f"Tool '{tool_name}' has invalid output_schema type")
        output_schema = {}
    output_contract = _normalize_output_contract(
        raw_tool.get("output_contract"),
        field_name=f"Tool '{tool_name}' output_contract",
        errors=errors,
    )

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
    errors.extend(_validate_platforms(metadata_platforms, f"Tool '{tool_name}' metadata.platforms"))
    aliases = _normalize_aliases(module_name, tool_name, raw_tool.get("aliases"))
    for alias in aliases:
        if not TOOL_KEY_RE.match(alias):
            errors.append(f"Tool '{tool_name}' has invalid alias '{alias}'")
    requires_consent = _normalize_bool_field(
        metadata.get("requires_consent"),
        default=False,
        field_name=f"Tool '{tool_name}' metadata.requires_consent",
        errors=errors,
    )
    idempotent = _normalize_bool_field(
        metadata.get("idempotent"),
        default=False,
        field_name=f"Tool '{tool_name}' metadata.idempotent",
        errors=errors,
    )
    side_effects = _normalize_bool_field(
        metadata.get("side_effects"),
        default=False,
        field_name=f"Tool '{tool_name}' metadata.side_effects",
        errors=errors,
    )
    allow_roles = _normalize_optional_string_list(
        metadata.get("allow_roles"),
        field_name=f"Tool '{tool_name}' metadata.allow_roles",
        errors=errors,
    )
    scopes = _normalize_string_list(
        metadata.get("scopes"),
        field_name=f"Tool '{tool_name}' metadata.scopes",
        errors=errors,
    )
    timeout_sec = _normalize_optional_timeout(
        metadata.get("timeout_sec"),
        field_name=f"Tool '{tool_name}' metadata.timeout_sec",
        errors=errors,
    )
    tool_kind = str(metadata.get("tool_kind") or ("remediation" if side_effects else "diagnostic")).strip().lower()
    if tool_kind not in {"diagnostic", "remediation"}:
        errors.append(f"Tool '{tool_name}' metadata.tool_kind must be diagnostic or remediation")
        tool_kind = "diagnostic"
    domain = metadata.get("domain")
    if domain is not None and not isinstance(domain, str):
        errors.append(f"Tool '{tool_name}' metadata.domain must be a string")
    origin = metadata.get("origin")
    if origin is not None and not isinstance(origin, str):
        errors.append(f"Tool '{tool_name}' metadata.origin must be a string")
    contract_version = str(raw_tool.get("contract_version") or "").strip()
    if not contract_version:
        if compat_legacy_defaults:
            warnings.append(f"Tool '{tool_name}' contract_version defaulted to 1.0.0 for legacy manifest")
        else:
            errors.append(f"Tool '{tool_name}' is missing contract_version")
        contract_version = "1.0.0"
    elif not SEMVER_RE.match(contract_version):
        errors.append(f"Tool '{tool_name}' contract_version must be semver")

    dependencies = raw_tool.get("dependencies")
    if not isinstance(dependencies, dict):
        if compat_legacy_defaults and dependencies is None:
            warnings.append(f"Tool '{tool_name}' dependencies defaulted to empty object for legacy manifest")
        else:
            errors.append(f"Tool '{tool_name}' dependencies must be an object")
        dependencies = {}
    for dep_key in ("required_binaries", "required_python_packages", "required_services", "required_permissions"):
        dep_value = dependencies.get(dep_key)
        if dep_value is not None and (
            not isinstance(dep_value, list) or any(not isinstance(item, str) or not item.strip() for item in dep_value)
        ):
            errors.append(f"Tool '{tool_name}' dependencies.{dep_key} must be a list of non-empty strings")
    min_agent_version = dependencies.get("min_agent_version")
    if min_agent_version is not None and (not isinstance(min_agent_version, str) or not SEMVER_RE.match(min_agent_version.strip())):
        errors.append(f"Tool '{tool_name}' dependencies.min_agent_version must be semver")

    lifecycle = str(raw_tool.get("lifecycle") or "").strip().lower()
    if not lifecycle:
        if compat_legacy_defaults:
            warnings.append(f"Tool '{tool_name}' lifecycle defaulted to stable for legacy manifest")
        else:
            errors.append(f"Tool '{tool_name}' is missing lifecycle")
        lifecycle = "stable"
    elif lifecycle not in ALLOWED_LIFECYCLES:
        errors.append(f"Tool '{tool_name}' lifecycle must be one of: {', '.join(sorted(ALLOWED_LIFECYCLES))}")

    error_codes = raw_tool.get("error_codes")
    if error_codes is None and compat_legacy_defaults:
        warnings.append(f"Tool '{tool_name}' error_codes defaulted to empty list for legacy manifest")
        error_codes = []
    elif not isinstance(error_codes, list) or any(not isinstance(item, str) or not item.strip() for item in error_codes):
        errors.append(f"Tool '{tool_name}' error_codes must be a list of non-empty strings")
        error_codes = []

    artifact_types = raw_tool.get("artifact_types")
    if artifact_types is None and compat_legacy_defaults:
        warnings.append(f"Tool '{tool_name}' artifact_types defaulted to empty list for legacy manifest")
        artifact_types = []
    elif not isinstance(artifact_types, list):
        errors.append(f"Tool '{tool_name}' artifact_types must be a list")
        artifact_types = []
    for index, artifact in enumerate(artifact_types, start=1):
        if not isinstance(artifact, dict):
            errors.append(f"Tool '{tool_name}' artifact_types[{index}] must be an object")
            continue
        if not isinstance(artifact.get("kind"), str) or not artifact.get("kind", "").strip():
            errors.append(f"Tool '{tool_name}' artifact_types[{index}].kind is required")

    redaction = raw_tool.get("redaction")
    if not isinstance(redaction, dict):
        if compat_legacy_defaults and redaction is None:
            warnings.append(f"Tool '{tool_name}' redaction defaults applied for legacy manifest")
        else:
            errors.append(f"Tool '{tool_name}' redaction must be an object")
        redaction = {}
    if "enabled" not in redaction:
        if compat_legacy_defaults:
            redaction["enabled"] = True
        else:
            errors.append(f"Tool '{tool_name}' redaction.enabled is required")
    if "allow_raw_sensitive_data" not in redaction:
        if compat_legacy_defaults:
            redaction["allow_raw_sensitive_data"] = False
        else:
            errors.append(f"Tool '{tool_name}' redaction.allow_raw_sensitive_data is required")
    if compat_legacy_defaults:
        redaction.setdefault("redact_headers", True)
        redaction.setdefault("redact_env", True)
        redaction.setdefault("redact_fields", [])

    resources = raw_tool.get("resources")
    if not isinstance(resources, dict):
        if compat_legacy_defaults and resources is None:
            warnings.append(f"Tool '{tool_name}' resources defaults applied for legacy manifest")
        else:
            errors.append(f"Tool '{tool_name}' resources must be an object")
        resources = {}
    for required_key in ("max_runtime_sec", "max_artifact_count", "max_artifact_bytes"):
        if required_key not in resources:
            if compat_legacy_defaults:
                if required_key == "max_runtime_sec":
                    resources[required_key] = 30
                else:
                    resources[required_key] = 0
            else:
                errors.append(f"Tool '{tool_name}' resources.{required_key} is required")
    normalized = {
        "tool": tool_name,
        "aliases": aliases,
        "method": method_name,
        "description": str(raw_tool.get("description") or "").strip(),
        "params_schema": params_schema,
        "output_schema": output_schema,
        "output_contract": output_contract,
        "presets": presets,
        "capabilities": capabilities,
        "metadata": {
            "domain": str(domain or tool_name.split(".", 1)[0]).strip() or tool_name.split(".", 1)[0],
            "platforms": metadata_platforms,
            "risk_level": normalize_risk_level(metadata.get("risk_level") or raw_tool.get("risk_level") or "safe_read"),
            "requires_consent": requires_consent,
            "timeout_sec": timeout_sec,
            "idempotent": idempotent,
            "side_effects": side_effects,
            "allow_roles": allow_roles,
            "scopes": scopes,
            "origin": str(origin or "managed"),
            "tool_kind": tool_kind,
        },
        "contract_version": contract_version,
        "dependencies": dependencies,
        "lifecycle": lifecycle,
        "error_codes": error_codes,
        "artifact_types": artifact_types,
        "redaction": redaction,
        "resources": resources,
    }

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
                "output_schema": tool.get("output_schema") or {},
                "output_contract": tool.get("output_contract") or {},
                "presets": tool.get("presets") or [],
                "capabilities": tool.get("capabilities") or [],
                "aliases": tool.get("aliases") or [],
                "metadata": tool.get("metadata") or {},
                "contract_version": tool.get("contract_version") or "1.0.0",
                "dependencies": tool.get("dependencies") or {},
                "lifecycle": tool.get("lifecycle") or "stable",
                "error_codes": tool.get("error_codes") or [],
                "artifact_types": tool.get("artifact_types") or [],
                "redaction": tool.get("redaction") or {},
                "resources": tool.get("resources") or {},
            }
        )

    return {
        "module_name": manifest_json.get("module_name"),
        "module_version": manifest_json.get("module_version"),
        "module_api_version": manifest_json.get("module_api_version"),
        "owner_scope": manifest_json.get("owner_scope"),
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
    module_api_version = str(source.get("module_api_version") or "").strip()
    owner_scope = str(source.get("owner_scope") or "").strip().lower()
    entrypoint = str(source.get("entrypoint") or DEFAULT_ENTRYPOINT).strip() or DEFAULT_ENTRYPOINT
    if not module_name:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'module_name'")
    if not module_version:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'module_version'")

    manifest_version = source.get("manifest_version")
    is_v2 = manifest_version == MANIFEST_V2
    if manifest_version not in (None, MANIFEST_V2):
        validation["errors"]["manifest"].append(f"Unsupported manifest_version: {manifest_version}")
    if is_v2 and not module_api_version:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'module_api_version'")
    if is_v2 and not owner_scope:
        validation["errors"]["manifest"].append("manifest.json: missing required field 'owner_scope'")

    normalized: Dict[str, Any] = {
        "manifest_version": MANIFEST_V2,
        "module_name": module_name,
        "module_version": module_version,
        "module_api_version": module_api_version or "1.0.0",
        "owner_scope": owner_scope or "vendor",
        "description": str(source.get("description") or "").strip(),
        "entrypoint": entrypoint,
        "platforms": _normalize_platforms(source.get("platforms")),
        "requirements": _ensure_list(source.get("requirements"), []),
        "optional_requirements": _ensure_list(source.get("optional_requirements"), []),
        "min_agent_version": source.get("min_agent_version"),
        "tools": [],
    }
    validation["errors"]["metadata"].extend(_validate_platforms(normalized["platforms"], "manifest.json platforms"))
    if normalized["owner_scope"] not in ALLOWED_OWNER_SCOPES:
        validation["errors"]["manifest"].append(
            f"manifest.json: owner_scope must be one of: {', '.join(sorted(ALLOWED_OWNER_SCOPES))}"
        )
    if normalized["module_api_version"] and not SEMVER_RE.match(normalized["module_api_version"]):
        validation["errors"]["manifest"].append("manifest.json: module_api_version must be semver")

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
        normalized_tool, warnings, errors = _normalize_tool_entry(
            module_name,
            raw_tool,
            compat_legacy_defaults=not is_v2,
        )
        validation["warnings"].extend(warnings)
        validation["errors"]["tools"].extend(errors)
        normalized["tools"].append(normalized_tool)

    if normalized["tools"]:
        canonical_index: Dict[str, int] = {}
        alias_index: Dict[str, str] = {}
        for idx, tool in enumerate(normalized["tools"], start=1):
            tool_name = tool.get("tool")
            if tool_name in canonical_index:
                validation["errors"]["tools"].append(
                    f"Duplicate tool '{tool_name}' declared in entries #{canonical_index[tool_name]} and #{idx}"
                )
            else:
                canonical_index[tool_name] = idx
            for alias in tool.get("aliases") or []:
                owner = alias_index.get(alias)
                if owner and owner != tool_name:
                    validation["errors"]["tools"].append(
                        f"Alias '{alias}' is declared by both '{owner}' and '{tool_name}'"
                    )
                    continue
                alias_index[alias] = tool_name
        for alias, owner in alias_index.items():
            if alias in canonical_index and alias != owner:
                validation["errors"]["tools"].append(
                    f"Alias '{alias}' for tool '{owner}' conflicts with canonical tool '{alias}'"
                )
        if normalized["owner_scope"] not in {"core", "platform", "builtin"}:
            for tool in normalized["tools"]:
                if is_reserved_namespace(str(tool.get("tool") or "")):
                    validation["errors"]["tools"].append(
                        f"Tool '{tool.get('tool')}' uses a reserved namespace and requires owner_scope=core|platform|builtin"
                    )

    if not normalized["tools"]:
        fallback_tool_name = f"{module_name}.run" if module_name else "unknown.run"
        normalized["tools"].append(
            {
                "tool": fallback_tool_name,
                "method": "run",
                "description": normalized["description"],
                "params_schema": {},
                "output_schema": {},
                "output_contract": {},
                "aliases": [],
                "presets": [],
                "capabilities": [],
                "metadata": {
                    "domain": module_name or "unknown",
                    "platforms": normalized["platforms"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                    "timeout_sec": None,
                    "idempotent": False,
                    "side_effects": False,
                    "allow_roles": None,
                    "scopes": [],
                    "origin": "managed" if is_v2 else "legacy",
                    "tool_kind": "diagnostic",
                },
                "contract_version": "1.0.0",
                "dependencies": {},
                "lifecycle": "stable",
                "error_codes": [],
                "artifact_types": [],
                "redaction": {
                    "enabled": True,
                    "allow_raw_sensitive_data": False,
                    "redact_headers": True,
                    "redact_env": True,
                    "redact_fields": [],
                },
                "resources": {
                    "max_runtime_sec": 30,
                    "max_artifact_count": 0,
                    "max_artifact_bytes": 0,
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
        "module_api_version": "1.0.0",
        "owner_scope": "vendor",
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
        "module_api_version": manifest_json.get("module_api_version"),
        "owner_scope": manifest_json.get("owner_scope"),
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
