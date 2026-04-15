"""
Atomic module builder used by POST /api/modules/create.
"""

from __future__ import annotations

import io
import json
import re
import textwrap
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from utils.module_manifest import manifest_summary_from_manifest

MODULE_PY_TEMPLATE = """# Generated from admin create-module flow. Module: {module_name}
from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool

class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return {module_name_literal}

    async def collect(self) -> Dict[str, Any]:
        return {{}}

{tool_methods}

def register():
    return _Collector()
"""

TOOL_METHOD_TEMPLATE = """    @exposed_tool(
        name={tool_name_literal},
        aliases={aliases_literal},
        description={description_literal},
        risk_level={risk_level_literal},
        params_schema={params_schema_literal},
        output_schema={output_schema_literal},
        presets={presets_literal},
        metadata_risk_level={metadata_risk_level_literal},
        metadata_scopes={metadata_scopes_literal},
        metadata_requires_consent={metadata_requires_consent_literal},
        metadata_allow_roles={metadata_allow_roles_literal},
        metadata_domain={metadata_domain_literal},
        metadata_platforms={metadata_platforms_literal},
        metadata_timeout_sec={metadata_timeout_sec_literal},
        metadata_idempotent={metadata_idempotent_literal},
        metadata_origin={metadata_origin_literal},
        metadata_side_effects={metadata_side_effects_literal},
    )
    async def {method_name}(self, **kwargs) -> Dict[str, Any]:
        params = {{**{defaults_literal}, **kwargs}}
        # user code begins
{user_function_body}
        # user code ends
"""

ALLOWED_RISK_LEVELS = ("safe_readonly", "safe_write", "dangerous")
DEFAULT_RISK_LEVEL = "safe_readonly"
ALLOWED_PLATFORMS = ("linux", "win32", "darwin", "any")


def _sanitize_identifier(value: str, default: str = "tool") -> str:
    if not value or not value.strip():
        return default
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip())
    return cleaned or default


def _params_schema_to_json_schema(params_schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not params_schema:
        return {"type": "object", "properties": {}, "additionalProperties": True}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    type_map = {"string": "string", "integer": "integer", "number": "number", "boolean": "boolean"}
    for item in params_schema:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        json_type = type_map.get(str(item.get("type") or "string").strip().lower(), "string")
        prop: Dict[str, Any] = {"type": json_type}
        if "default" in item:
            prop["default"] = item["default"]
        properties[name] = prop
        if item.get("required", "default" not in item):
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
        "required": required,
    }


def _params_schema_to_defaults(params_schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    for item in params_schema:
        name = str(item.get("name") or "").strip()
        if name and "default" in item:
            defaults[name] = item["default"]
    return defaults


def _normalize_platforms(platforms: Optional[List[str]]) -> List[str]:
    if platforms is None or "any" in platforms:
        return ["any"]
    normalized = [str(item).lower() for item in platforms if item]
    return normalized or ["any"]


def _tool_domain_from_name(tool_name: str, module_name: str) -> str:
    if "." in tool_name:
        return tool_name.split(".", 1)[0]
    return module_name


def _normalize_tool_aliases(module_name: str, canonical_tool_name: str, raw_aliases: Any) -> List[str]:
    if not isinstance(raw_aliases, list):
        raw_aliases = []
    aliases: List[str] = []
    for alias in raw_aliases:
        alias_value = str(alias or "").strip()
        if alias_value:
            normalized_alias = alias_value if "." in alias_value else f"{module_name}.{alias_value}"
            if normalized_alias != canonical_tool_name:
                aliases.append(normalized_alias)
    legacy_alias = f"{module_name}.{canonical_tool_name.split('.', 1)[-1]}"
    if legacy_alias != canonical_tool_name:
        aliases.append(legacy_alias)
    return list(dict.fromkeys(aliases))


def _coerce_tools_payload(
    *,
    tool_name: str,
    description: str,
    user_function_body: str,
    risk_level: str,
    params_schema: Optional[List[Dict[str, Any]]],
    presets: Optional[List[Dict[str, Any]]],
    method_name: Optional[str],
    capabilities: Optional[List[Dict[str, Any]]],
    metadata: Optional[Dict[str, Any]],
    output_schema: Optional[Dict[str, Any]],
    aliases: Optional[List[str]],
    tools: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if isinstance(tools, list) and tools:
        return tools
    return [
        {
            "tool_name": tool_name,
            "description": description,
            "user_function_body": user_function_body,
            "risk_level": risk_level,
            "params_schema": params_schema or [],
            "presets": presets or [],
            "method_name": method_name,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
            "output_schema": output_schema or {},
            "aliases": aliases or [],
        }
    ]


def _normalize_tool_specs(
    *,
    module_name: str,
    module_platforms: List[str],
    tools_payload: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized_tools: List[Dict[str, Any]] = []
    seen_tool_names: set[str] = set()
    seen_method_names: set[str] = set()

    for index, raw_tool in enumerate(tools_payload, start=1):
        if not isinstance(raw_tool, dict):
            raise ValueError(f"tools[{index}] must be an object")

        canonical_tool_name = str(
            raw_tool.get("canonical_name")
            or raw_tool.get("tool_name")
            or raw_tool.get("tool")
            or raw_tool.get("name")
            or ""
        ).strip()
        if not canonical_tool_name:
            raise ValueError(f"tools[{index}].tool_name is required")
        if canonical_tool_name in seen_tool_names:
            raise ValueError(f"Duplicate tool_name '{canonical_tool_name}' in module '{module_name}'")
        seen_tool_names.add(canonical_tool_name)

        tool_description = str(raw_tool.get("description") or "").strip()
        if not tool_description:
            raise ValueError(f"tools[{index}].description is required")

        body = raw_tool.get("user_function_body")
        if body is None:
            body = ""
        body_lines = str(body).strip().splitlines()
        body_text = "\n".join("        " + line for line in body_lines) if body_lines else "        return {}"

        raw_method_name = str(
            raw_tool.get("method_name")
            or raw_tool.get("method")
            or canonical_tool_name.split(".", 1)[-1]
            or f"tool_{index}"
        ).strip()
        method_name = _sanitize_identifier(raw_method_name, f"tool_{index}")
        if method_name in seen_method_names:
            raise ValueError(f"Duplicate method_name '{method_name}' in module '{module_name}'")
        seen_method_names.add(method_name)

        tool_risk_level = str(raw_tool.get("risk_level") or DEFAULT_RISK_LEVEL).strip()
        if tool_risk_level not in ALLOWED_RISK_LEVELS:
            tool_risk_level = DEFAULT_RISK_LEVEL

        tool_params_schema = raw_tool.get("params_schema") if isinstance(raw_tool.get("params_schema"), list) else []
        tool_presets = raw_tool.get("presets") if isinstance(raw_tool.get("presets"), list) else []
        tool_capabilities = raw_tool.get("capabilities") if isinstance(raw_tool.get("capabilities"), list) else []
        tool_metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else {}
        tool_output_schema = raw_tool.get("output_schema") if isinstance(raw_tool.get("output_schema"), dict) else {}
        tool_aliases = _normalize_tool_aliases(module_name, canonical_tool_name, raw_tool.get("aliases"))
        tool_platforms = _normalize_platforms(
            raw_tool.get("platforms")
            if isinstance(raw_tool.get("platforms"), list)
            else tool_metadata.get("platforms")
        )
        effective_platforms = tool_platforms if tool_platforms != ["any"] else module_platforms
        metadata_domain = str(tool_metadata.get("domain") or _tool_domain_from_name(canonical_tool_name, module_name))
        metadata_risk_level = str(tool_metadata.get("risk_level") or tool_risk_level)

        normalized_tools.append(
            {
                "tool": canonical_tool_name,
                "aliases": tool_aliases,
                "method": method_name,
                "description": tool_description[:500],
                "params_schema": _params_schema_to_json_schema(tool_params_schema),
                "defaults": _params_schema_to_defaults(tool_params_schema),
                "presets": tool_presets,
                "capabilities": tool_capabilities,
                "output_schema": tool_output_schema,
                "risk_level": tool_risk_level,
                "metadata": {
                    "domain": metadata_domain,
                    "platforms": effective_platforms,
                    "risk_level": metadata_risk_level,
                    "requires_consent": bool(tool_metadata.get("requires_consent", False)),
                    "timeout_sec": tool_metadata.get("timeout_sec"),
                    "idempotent": bool(tool_metadata.get("idempotent", False)),
                    "side_effects": bool(tool_metadata.get("side_effects", False)),
                    "allow_roles": tool_metadata.get("allow_roles"),
                    "scopes": tool_metadata.get("scopes") if isinstance(tool_metadata.get("scopes"), list) else [],
                    "origin": str(tool_metadata.get("origin") or "managed"),
                },
                "user_function_body": body_text,
            }
        )

    return normalized_tools


def _render_tool_methods(tool_specs: List[Dict[str, Any]]) -> str:
    fragments: List[str] = []
    for tool in tool_specs:
        metadata = tool["metadata"]
        fragments.append(
            TOOL_METHOD_TEMPLATE.format(
                tool_name_literal=repr(tool["tool"]),
                aliases_literal=repr(tool["aliases"]),
                description_literal=repr(tool["description"]),
                risk_level_literal=repr(tool["risk_level"]),
                params_schema_literal=repr(tool["params_schema"]),
                output_schema_literal=repr(tool["output_schema"]),
                presets_literal=repr(tool["presets"]),
                metadata_risk_level_literal=repr(metadata["risk_level"]),
                metadata_scopes_literal=repr(metadata["scopes"]),
                metadata_requires_consent_literal=repr(metadata["requires_consent"]),
                metadata_allow_roles_literal=repr(metadata["allow_roles"]),
                metadata_domain_literal=repr(metadata["domain"]),
                metadata_platforms_literal=repr(metadata["platforms"]),
                metadata_timeout_sec_literal=repr(metadata["timeout_sec"]),
                metadata_idempotent_literal=repr(metadata["idempotent"]),
                metadata_origin_literal=repr(metadata["origin"]),
                metadata_side_effects_literal=repr(metadata["side_effects"]),
                method_name=tool["method"],
                defaults_literal=repr(tool["defaults"]),
                user_function_body=tool["user_function_body"],
            )
        )
    return "\n".join(fragments).rstrip()


def build_module_package(
    module_name: str,
    version: str,
    tool_name: str,
    description: str,
    user_function_body: str,
    risk_level: str = DEFAULT_RISK_LEVEL,
    params_schema: Optional[List[Dict[str, Any]]] = None,
    presets: Optional[List[Dict[str, Any]]] = None,
    platforms: Optional[List[str]] = None,
    method_name: Optional[str] = None,
    capabilities: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    requirements: Optional[List[str]] = None,
    optional_requirements: Optional[List[str]] = None,
    min_agent_version: Optional[str] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    aliases: Optional[List[str]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bytes, dict]:
    if not (module_name and module_name.strip()):
        raise ValueError("module_name is required")
    if not (version and version.strip()):
        raise ValueError("version is required")

    tools_payload = _coerce_tools_payload(
        tool_name=tool_name,
        description=description,
        user_function_body=user_function_body,
        risk_level=risk_level,
        params_schema=params_schema,
        presets=presets,
        method_name=method_name,
        capabilities=capabilities,
        metadata=metadata,
        output_schema=output_schema,
        aliases=aliases,
        tools=tools,
    )
    if not tools_payload:
        raise ValueError("at least one tool definition is required")

    mod_name = _sanitize_identifier(module_name, "custom_module")
    module_platforms = _normalize_platforms(platforms)
    tool_specs = _normalize_tool_specs(
        module_name=mod_name,
        module_platforms=module_platforms,
        tools_payload=tools_payload,
    )

    module_py = MODULE_PY_TEMPLATE.format(
        module_name=mod_name,
        module_name_literal=repr(mod_name),
        tool_methods=_render_tool_methods(tool_specs),
    )

    manifest = {
        "manifest_version": 2,
        "module_name": mod_name,
        "module_version": version.strip(),
        "entrypoint": "module:register",
        "description": str(description or tool_specs[0]["description"]).strip()[:500],
        "platforms": module_platforms,
        "requirements": requirements or [],
        "optional_requirements": optional_requirements or [],
        "min_agent_version": min_agent_version,
        "tools": [
            {
                "tool": tool["tool"],
                "aliases": tool["aliases"],
                "method": tool["method"],
                "description": tool["description"],
                "params_schema": tool["params_schema"],
                "output_schema": tool["output_schema"],
                "presets": tool["presets"],
                "capabilities": tool["capabilities"],
                "metadata": tool["metadata"],
            }
            for tool in tool_specs
        ],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("module.py", module_py)

    return buf.getvalue(), manifest_summary_from_manifest(manifest)
