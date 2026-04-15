"""Helpers for the admin module workbench."""

from __future__ import annotations

import json
import re
import textwrap
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from config import MODULES_STORAGE_DIR
from utils.module_manifest import get_module_manifest


_METHOD_BODY_RE = re.compile(
    r"async def (?P<method>[A-Za-z_][A-Za-z0-9_]*)\(self, \*\*kwargs\) -> Dict\[str, Any\]:"
    r".*?# user code begins\s*\n(?P<body>.*?)\n\s*# user code ends",
    re.DOTALL,
)


def _archive_path(module: object) -> Path:
    return MODULES_STORAGE_DIR / str(getattr(module, "storage_path", "") or "").strip()


def load_archive_text_files(module: object) -> dict[str, str]:
    archive_path = _archive_path(module)
    if not archive_path.exists():
        return {}
    text_files: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(archive_path.read_bytes()), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix not in {".py", ".json", ".md", ".txt"}:
                continue
            try:
                text_files[info.filename] = zf.read(info.filename).decode("utf-8")
            except Exception:
                continue
    return text_files


def parse_generated_tool_bodies(module_py: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in _METHOD_BODY_RE.finditer(module_py or ""):
        method = match.group("method")
        body = textwrap.dedent(match.group("body") or "").strip("\n")
        if method and body:
            result[method] = body.rstrip()
    return result


def build_editable_spec(module: object) -> dict[str, Any]:
    manifest_json = get_module_manifest(module)
    text_files = load_archive_text_files(module)
    module_py = text_files.get("module.py", "")
    parsed_bodies = parse_generated_tool_bodies(module_py)
    tools: list[dict[str, Any]] = []
    warnings: list[str] = []

    for tool in manifest_json.get("tools") or []:
        method_name = str(tool.get("method") or "").strip()
        user_function_body = parsed_bodies.get(method_name, "")
        if method_name and not user_function_body:
            warnings.append(
                f"Structured code body for method '{method_name}' was not reconstructed automatically."
            )
        tools.append(
            {
                "tool_name": tool.get("tool"),
                "aliases": tool.get("aliases") or [],
                "method_name": method_name,
                "description": tool.get("description") or "",
                "params_schema": tool.get("params_schema") or {},
                "output_schema": tool.get("output_schema") or {},
                "presets": tool.get("presets") or [],
                "capabilities": tool.get("capabilities") or [],
                "metadata": tool.get("metadata") or {},
                "contract_version": tool.get("contract_version") or "1.0.0",
                "dependencies": tool.get("dependencies") or {},
                "lifecycle": tool.get("lifecycle") or "stable",
                "error_codes": tool.get("error_codes") or [],
                "artifact_types": tool.get("artifact_types") or [],
                "redaction": tool.get("redaction") or {},
                "resources": tool.get("resources") or {},
                "user_function_body": user_function_body,
            }
        )

    source_files = [
        {
            "path": path,
            "size_bytes": len(content.encode("utf-8")),
            "content": content,
        }
        for path, content in sorted(text_files.items())
    ]

    manifest_text = ""
    if "manifest.json" in text_files:
        manifest_text = text_files["manifest.json"]
    elif manifest_json:
        manifest_text = json.dumps(manifest_json, ensure_ascii=False, indent=2)

    return {
        "module_name": manifest_json.get("module_name") or getattr(module, "module_name", ""),
        "version": manifest_json.get("module_version") or getattr(module, "version", ""),
        "module_api_version": manifest_json.get("module_api_version") or "1.0.0",
        "owner_scope": manifest_json.get("owner_scope") or "vendor",
        "description": manifest_json.get("description") or "",
        "platforms": manifest_json.get("platforms") or ["any"],
        "requirements": manifest_json.get("requirements") or [],
        "optional_requirements": manifest_json.get("optional_requirements") or [],
        "min_agent_version": manifest_json.get("min_agent_version"),
        "entrypoint": manifest_json.get("entrypoint") or "module:register",
        "tools": tools,
        "warnings": list(dict.fromkeys(warnings)),
        "source": {
            "manifest_json_text": manifest_text,
            "module_py_text": module_py,
            "files": source_files,
        },
    }
