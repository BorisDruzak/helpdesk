"""Helpers for the admin module workbench."""

from __future__ import annotations

import ast
import json
import re
import textwrap
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from config import MODULES_STORAGE_DIR
from utils.module_manifest import get_module_manifest


_METHOD_BODY_RE = re.compile(
    r"async def (?P<method>[A-Za-z_][A-Za-z0-9_]*)\(self, \*\*kwargs\) -> Dict\[str, Any\]:"
    r".*?# user code begins\s*\n(?P<body>.*?)\n\s*# user code ends",
    re.DOTALL,
)


def _archive_path(module: object) -> Path:
    return MODULES_STORAGE_DIR / str(getattr(module, "storage_path", "") or "").strip()


def load_archive_text_files_from_bytes(zip_bytes: bytes) -> dict[str, str]:
    text_files: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix not in {".py", ".json", ".md", ".txt", ".yaml", ".yml"}:
                continue
            try:
                text_files[info.filename] = zf.read(info.filename).decode("utf-8")
            except Exception:
                continue
    return text_files


def load_archive_text_files(module: object) -> dict[str, str]:
    archive_path = _archive_path(module)
    if not archive_path.exists():
        return {}
    return load_archive_text_files_from_bytes(archive_path.read_bytes())


def parse_generated_tool_bodies(module_py: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in _METHOD_BODY_RE.finditer(module_py or ""):
        method = match.group("method")
        body = textwrap.dedent(match.group("body") or "").strip("\n")
        if method and body:
            result[method] = body.rstrip()
    return result


def _decorator_base_name(decorator: ast.AST) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def _literal_or_none(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _extract_source_segment(lines: list[str], start_lineno: int | None, end_lineno: int | None) -> str:
    if not start_lineno or not end_lineno:
        return ""
    return "\n".join(lines[start_lineno - 1 : end_lineno]).rstrip()


def _extract_function_body(lines: list[str], node: ast.AsyncFunctionDef | ast.FunctionDef) -> str:
    if not node.body:
        return ""
    start_node: ast.stmt = node.body[0]
    if (
        isinstance(start_node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "params" for target in start_node.targets)
        and len(node.body) > 1
    ):
        start_node = node.body[1]
    body_text = _extract_source_segment(lines, getattr(start_node, "lineno", None), getattr(node.body[-1], "end_lineno", None))
    return textwrap.dedent(body_text).strip()


def parse_exposed_tool_functions(source_text: str) -> dict[str, Any]:
    result = {
        "methods": {},
        "tool_names": {},
        "parse_errors": [],
    }
    if not source_text.strip():
        return result

    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        result["parse_errors"].append(f"AST parse failed: {exc.msg} at line {exc.lineno}")
        return result

    lines = source_text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        exposed_decorator: ast.Call | None = None
        for decorator in node.decorator_list:
            if _decorator_base_name(decorator) == "exposed_tool" and isinstance(decorator, ast.Call):
                exposed_decorator = decorator
                break
        if exposed_decorator is None:
            continue

        keyword_values = {kw.arg: _literal_or_none(kw.value) for kw in exposed_decorator.keywords if kw.arg}
        tool_name = str(keyword_values.get("name") or "").strip()
        aliases = keyword_values.get("aliases") if isinstance(keyword_values.get("aliases"), list) else []
        body_text = _extract_function_body(lines, node)
        full_source = _extract_source_segment(lines, getattr(node, "lineno", None), getattr(node, "end_lineno", None))
        entry = {
            "method": node.name,
            "tool_name": tool_name,
            "aliases": aliases,
            "body": body_text,
            "full_source": full_source,
            "strategy": "ast",
            "start_lineno": getattr(node, "lineno", None),
            "end_lineno": getattr(node, "end_lineno", None),
        }
        result["methods"][node.name] = entry
        if tool_name:
            result["tool_names"][tool_name] = entry
        for alias in aliases:
            alias_name = str(alias or "").strip()
            if alias_name:
                result["tool_names"].setdefault(alias_name, entry)
    return result


def analyze_python_sources(text_files: dict[str, str]) -> dict[str, Any]:
    methods: dict[str, dict[str, Any]] = {}
    tool_names: dict[str, dict[str, Any]] = {}
    files_summary: list[dict[str, Any]] = []

    for path, content in sorted(text_files.items()):
        if Path(path).suffix.lower() != ".py":
            continue
        marker_bodies = parse_generated_tool_bodies(content)
        ast_info = parse_exposed_tool_functions(content)
        detected_entries: list[dict[str, Any]] = []

        for method_name, body in marker_bodies.items():
            entry = {
                "method": method_name,
                "tool_name": "",
                "aliases": [],
                "body": body,
                "full_source": "",
                "strategy": "markers",
                "source_path": path,
                "start_lineno": None,
                "end_lineno": None,
            }
            methods[method_name] = entry
            detected_entries.append(entry)

        for method_name, entry in ast_info["methods"].items():
            merged = {
                **entry,
                "body": methods.get(method_name, {}).get("body") or entry.get("body", ""),
                "strategy": methods.get(method_name, {}).get("strategy") or entry.get("strategy", "ast"),
                "source_path": path,
            }
            methods[method_name] = merged
            if merged.get("tool_name"):
                tool_names.setdefault(merged["tool_name"], merged)
            for alias in merged.get("aliases") or []:
                alias_name = str(alias or "").strip()
                if alias_name:
                    tool_names.setdefault(alias_name, merged)
            detected_entries.append(merged)

        files_summary.append(
            {
                "path": path,
                "size_bytes": len(content.encode("utf-8")),
                "language": "python",
                "content": content,
                "detected_tools": [
                    {
                        "method": item.get("method"),
                        "tool_name": item.get("tool_name"),
                        "strategy": item.get("strategy"),
                    }
                    for item in detected_entries
                ],
                "parse_errors": ast_info["parse_errors"],
            }
        )

    return {
        "methods": methods,
        "tool_names": tool_names,
        "files_summary": files_summary,
    }


def _tool_body_from_analysis(tool_name: str, method_name: str, python_analysis: dict[str, Any]) -> tuple[str, str | None]:
    methods = python_analysis.get("methods") or {}
    tool_names = python_analysis.get("tool_names") or {}

    if method_name and method_name in methods:
        entry = methods[method_name]
        return str(entry.get("body") or ""), str(entry.get("strategy") or "ast")
    if tool_name and tool_name in tool_names:
        entry = tool_names[tool_name]
        return str(entry.get("body") or ""), str(entry.get("strategy") or "ast")
    return "", None


def build_editable_spec_from_archive_bytes(
    *,
    zip_bytes: bytes,
    manifest_json: dict[str, Any] | None,
    fallback_module_name: str = "",
    fallback_version: str = "",
) -> dict[str, Any]:
    manifest_json = manifest_json or {}
    text_files = load_archive_text_files_from_bytes(zip_bytes)
    python_analysis = analyze_python_sources(text_files)
    tools: list[dict[str, Any]] = []
    warnings: list[str] = []

    for tool in manifest_json.get("tools") or []:
        method_name = str(tool.get("method") or "").strip()
        tool_name = str(tool.get("tool") or tool.get("name") or "").strip()
        user_function_body, strategy = _tool_body_from_analysis(tool_name, method_name, python_analysis)
        if (method_name or tool_name) and not user_function_body:
            warnings.append(
                f"Structured code body for tool '{tool_name or method_name}' was not reconstructed automatically."
            )
        tools.append(
            {
                "tool_name": tool_name,
                "aliases": tool.get("aliases") or [],
                "method_name": method_name,
                "description": tool.get("description") or "",
                "params_schema": tool.get("params_schema") or {},
                "output_schema": tool.get("output_schema") or {},
                "output_contract": tool.get("output_contract") or {},
                "presentation_schema": tool.get("presentation_schema") or {},
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
                "reconstruction_strategy": strategy or "raw",
            }
        )

    source_files = [
        {
            "path": path,
            "size_bytes": len(content.encode("utf-8")),
            "language": (
                "python"
                if path.endswith(".py")
                else "json"
                if path.endswith(".json")
                else "markdown"
                if path.endswith(".md")
                else "text"
            ),
            "content": content,
            "detected_tools": next(
                (item.get("detected_tools") for item in python_analysis["files_summary"] if item["path"] == path),
                [],
            ),
            "parse_errors": next(
                (item.get("parse_errors") for item in python_analysis["files_summary"] if item["path"] == path),
                [],
            ),
        }
        for path, content in sorted(text_files.items())
    ]

    unresolved_tools = [
        str(tool.get("tool_name") or tool.get("method_name") or "").strip()
        for tool in tools
        if not str(tool.get("user_function_body") or "").strip()
    ]
    manifest_text = text_files.get("manifest.json") or json.dumps(manifest_json, ensure_ascii=False, indent=2)
    primary_module_py = text_files.get("module.py", "")

    return {
        "module_name": manifest_json.get("module_name") or fallback_module_name,
        "version": manifest_json.get("module_version") or fallback_version,
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
            "module_py_text": primary_module_py,
            "files": source_files,
            "decomposition": {
                "resolved_tools": len(tools) - len(unresolved_tools),
                "unresolved_tools": unresolved_tools,
                "available_methods": sorted((python_analysis.get("methods") or {}).keys()),
                "available_tool_names": sorted((python_analysis.get("tool_names") or {}).keys()),
            },
        },
    }


def build_editable_spec(module: object) -> dict[str, Any]:
    manifest_json = get_module_manifest(module)
    archive_path = _archive_path(module)
    zip_bytes = archive_path.read_bytes() if archive_path.exists() else b""
    if not zip_bytes:
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
            "tools": [],
            "warnings": ["Module archive is missing on disk, so only manifest metadata is available."],
            "source": {
                "manifest_json_text": json.dumps(manifest_json, ensure_ascii=False, indent=2),
                "module_py_text": "",
                "files": [],
                "decomposition": {"resolved_tools": 0, "unresolved_tools": [], "available_methods": [], "available_tool_names": []},
            },
        }
    return build_editable_spec_from_archive_bytes(
        zip_bytes=zip_bytes,
        manifest_json=manifest_json,
        fallback_module_name=getattr(module, "module_name", ""),
        fallback_version=getattr(module, "version", ""),
    )
