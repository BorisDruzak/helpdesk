"""
Atomic module builder used by POST /api/modules/create.
"""

import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from utils.module_manifest import manifest_summary_from_manifest

MODULE_PY_TEMPLATE_NO_PARAMS = '''# Generated from admin create-module flow. Module: {{MODULE_NAME}}
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return "{{MODULE_NAME}}"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(
        name="{{TOOL_NAME}}",
        description="{{TOOL_DESCRIPTION}}",
        risk_level="{{RISK_LEVEL}}",
        metadata_risk_level="{{METADATA_RISK_LEVEL}}",
        metadata_scopes={{METADATA_SCOPES}},
        metadata_requires_consent={{REQUIRES_CONSENT}},
    )
    async def {{METHOD_NAME}}(self) -> Dict[str, Any]:
        # user code begins
{{USER_FUNCTION_BODY}}
        # user code ends

def register():
    return _Collector()
'''

MODULE_PY_TEMPLATE_WITH_PARAMS = '''# Generated from admin create-module flow. Module: {{MODULE_NAME}}
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return "{{MODULE_NAME}}"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(
        name="{{TOOL_NAME}}",
        description="{{TOOL_DESCRIPTION}}",
        risk_level="{{RISK_LEVEL}}",
        params_schema={{PARAMS_SCHEMA}},
        presets={{PRESETS_JSON}},
        metadata_risk_level="{{METADATA_RISK_LEVEL}}",
        metadata_scopes={{METADATA_SCOPES}},
        metadata_requires_consent={{REQUIRES_CONSENT}},
    )
    async def {{METHOD_NAME}}(self, **kwargs) -> Dict[str, Any]:
        params = {**{{DEFAULTS_DICT}}, **kwargs}
        # user code begins
{{USER_FUNCTION_BODY}}
        # user code ends

def register():
    return _Collector()
'''

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
) -> Tuple[bytes, dict]:
    if not (module_name and module_name.strip()):
        raise ValueError("module_name is required")
    if not (version and version.strip()):
        raise ValueError("version is required")
    if not (tool_name and tool_name.strip()):
        raise ValueError("tool_name is required")
    if not (description and description.strip()):
        raise ValueError("description is required")
    if user_function_body is None:
        user_function_body = ""

    mod_name = _sanitize_identifier(module_name, "custom_module")
    tool_name_clean = _sanitize_identifier(tool_name, "run")
    method_name_clean = _sanitize_identifier(method_name or tool_name_clean, tool_name_clean)
    if risk_level not in ALLOWED_RISK_LEVELS:
        risk_level = DEFAULT_RISK_LEVEL

    metadata = metadata or {}
    capabilities = capabilities or []
    params_schema = params_schema if isinstance(params_schema, list) else []
    presets = presets if isinstance(presets, list) else []
    platforms_list = _normalize_platforms(platforms)
    has_params = bool(params_schema)

    json_schema = _params_schema_to_json_schema(params_schema)
    defaults = _params_schema_to_defaults(params_schema)
    metadata_scopes = metadata.get("scopes") if isinstance(metadata.get("scopes"), list) else []
    metadata_risk_level = str(metadata.get("risk_level") or risk_level)
    metadata_requires_consent = "True" if metadata.get("requires_consent") else "False"

    body_lines = (user_function_body or "").strip().splitlines()
    if body_lines:
        body_text = "\n".join("        " + line for line in body_lines)
    else:
        body_text = "        return {}"

    if has_params:
        module_py = (
            MODULE_PY_TEMPLATE_WITH_PARAMS.replace("{{MODULE_NAME}}", mod_name)
            .replace("{{TOOL_NAME}}", tool_name_clean)
            .replace("{{METHOD_NAME}}", method_name_clean)
            .replace("{{TOOL_DESCRIPTION}}", description.strip().replace('"', '\\"'))
            .replace("{{RISK_LEVEL}}", risk_level)
            .replace("{{PARAMS_SCHEMA}}", repr(json_schema))
            .replace("{{PRESETS_JSON}}", repr(presets))
            .replace("{{DEFAULTS_DICT}}", repr(defaults))
            .replace("{{METADATA_RISK_LEVEL}}", metadata_risk_level)
            .replace("{{METADATA_SCOPES}}", repr(metadata_scopes))
            .replace("{{REQUIRES_CONSENT}}", metadata_requires_consent)
            .replace("{{USER_FUNCTION_BODY}}", body_text)
        )
    else:
        module_py = (
            MODULE_PY_TEMPLATE_NO_PARAMS.replace("{{MODULE_NAME}}", mod_name)
            .replace("{{TOOL_NAME}}", tool_name_clean)
            .replace("{{METHOD_NAME}}", method_name_clean)
            .replace("{{TOOL_DESCRIPTION}}", description.strip().replace('"', '\\"'))
            .replace("{{RISK_LEVEL}}", risk_level)
            .replace("{{METADATA_RISK_LEVEL}}", metadata_risk_level)
            .replace("{{METADATA_SCOPES}}", repr(metadata_scopes))
            .replace("{{REQUIRES_CONSENT}}", metadata_requires_consent)
            .replace("{{USER_FUNCTION_BODY}}", body_text)
        )

    full_tool_name = f"{mod_name}.{tool_name_clean}"
    manifest = {
        "manifest_version": 2,
        "module_name": mod_name,
        "module_version": version.strip(),
        "entrypoint": "module:register",
        "description": description.strip()[:500],
        "platforms": platforms_list,
        "requirements": requirements or [],
        "optional_requirements": optional_requirements or [],
        "min_agent_version": min_agent_version,
        "tools": [
            {
                "tool": full_tool_name,
                "method": method_name_clean,
                "description": description.strip()[:500],
                "params_schema": json_schema if has_params else {},
                "presets": presets,
                "capabilities": capabilities,
                "metadata": {
                    "domain": str(metadata.get("domain") or mod_name),
                    "platforms": platforms_list,
                    "risk_level": metadata_risk_level,
                    "requires_consent": bool(metadata.get("requires_consent", False)),
                    "timeout_sec": metadata.get("timeout_sec"),
                    "idempotent": bool(metadata.get("idempotent", False)),
                    "allow_roles": metadata.get("allow_roles"),
                    "scopes": metadata_scopes,
                    "origin": "managed",
                },
            }
        ],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("module.py", module_py)

    return buf.getvalue(), manifest_summary_from_manifest(manifest)
