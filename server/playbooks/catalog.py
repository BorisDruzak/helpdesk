"""Diagnostic playbook catalog and draft normalization."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from playbooks.tool_catalog import (
    build_condition_hints,
    build_required_capabilities_manifest,
    expand_preset_params,
)


KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
DIAGNOSTIC_OUTPUT_CONTRACT = {
    "schema_version": "1.0",
    "status_path": "result.status",
    "status_values": ["ok", "error"],
    "success_values": ["ok"],
    "error_values": ["error"],
    "summary_path": "result.output.summary",
    "error_code_path": "result.error.code",
    "compact_fields": [],
}


def _diagnostic_condition_hints(error_codes: list[str] | None = None) -> dict[str, Any]:
    return build_condition_hints(DIAGNOSTIC_OUTPUT_CONTRACT, error_codes or [])

DIAGNOSTIC_MODULE_CATALOG: list[dict[str, Any]] = []
SCENARIO_TEMPLATES: list[dict[str, Any]] = []


def _require_key(value: Any, *, field: str) -> str:
    key = str(value or "").strip()
    if not key:
        raise ValueError(f"{field} is required")
    if not KEY_PATTERN.match(key):
        raise ValueError(f"{field} must use latin snake_case")
    return key


def _step_type_for_block(block_type: str, executable_id: str | None) -> str:
    if block_type == "diagnostic":
        if not executable_id:
            raise ValueError("diagnostic block requires tool or capability_id")
        return "collect"
    if block_type in {"decision", "report", "transform"}:
        return block_type
    raise ValueError(f"unsupported block type: {block_type}")


def normalize_playbook_draft(raw: Any) -> dict[str, Any]:
    """Normalize a low-code diagnostic draft into persisted playbook/version/steps."""
    if not isinstance(raw, dict):
        raise ValueError("playbook draft must be an object")
    key = _require_key(raw.get("key"), field="key")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    blocks = raw.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("blocks must be a non-empty array")

    normalized_blocks: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    catalog_by_capability: dict[str, dict[str, Any]] = {}
    for index, raw_block in enumerate(blocks, start=1):
        if not isinstance(raw_block, dict):
            raise ValueError("each block must be an object")
        block_type = str(raw_block.get("type") or raw_block.get("block_type") or "diagnostic").strip().lower()
        module_kind = str(raw_block.get("module_kind") or "diagnostic").strip().lower()
        if module_kind == "remediation" or block_type in {"remediate", "remediation"}:
            raise ValueError("remediation blocks require explicit confirmation flow and are not allowed here")
        if module_kind != "diagnostic":
            raise ValueError(f"unsupported module_kind: {module_kind}")

        block_id = _require_key(raw_block.get("id") or raw_block.get("key") or f"step_{index}", field="block id")
        tool_manifest = raw_block.get("tool_manifest") if isinstance(raw_block.get("tool_manifest"), dict) else None
        capability_id = str(
            raw_block.get("capability_id")
            or raw_block.get("capability")
            or (tool_manifest or {}).get("capability_id")
            or (tool_manifest or {}).get("id")
            or raw_block.get("tool")
            or ""
        ).strip() or None
        tool = str(raw_block.get("tool") or capability_id or "").strip() or None
        params = raw_block.get("params")
        if params is None:
            params = raw_block.get("default_params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError(f"block {block_id!r} params must be an object")
        preset_id = str(raw_block.get("preset_id") or "").strip() or None
        if capability_id and tool_manifest:
            catalog_by_capability[capability_id] = deepcopy(tool_manifest)
        if preset_id and tool_manifest:
            params = expand_preset_params(tool_manifest, preset_id=preset_id, overrides=params)
        execution = tool_manifest.get("execution") if isinstance(tool_manifest, dict) and isinstance(tool_manifest.get("execution"), dict) else {}
        deployment = tool_manifest.get("deployment") if isinstance(tool_manifest, dict) and isinstance(tool_manifest.get("deployment"), dict) else {}
        execution_target = str(
            raw_block.get("execution_target")
            or (tool_manifest or {}).get("execution_target")
            or execution.get("target")
            or ""
        ).strip() or None
        provider_id = str(
            raw_block.get("provider_id")
            or (tool_manifest or {}).get("provider_id")
            or deployment.get("provider_id")
            or ""
        ).strip() or None
        install_policy = str(raw_block.get("install_policy") or "").strip().lower() or None
        if install_policy and install_policy not in {"lazy", "preinstalled", "required", "server"}:
            raise ValueError(f"unsupported install_policy: {install_policy}")

        step_type = _step_type_for_block(block_type, tool or capability_id)
        step = {
            "step_key": block_id,
            "order_no": index,
            "type": step_type,
            "tool": tool,
            "params_template_json": deepcopy(params),
            "if_expr": str(raw_block.get("condition") or raw_block.get("if_expr") or "").strip() or None,
            "timeout_sec": raw_block.get("timeout_sec"),
            "retry_policy_json": deepcopy(raw_block.get("retry_policy") or {}),
            "continue_on_error": bool(raw_block.get("continue_on_error", False)),
            "parallel_group": str(raw_block.get("parallel_group") or "").strip() or None,
        }
        if step["timeout_sec"] is not None:
            step["timeout_sec"] = int(step["timeout_sec"])
        normalized_block = {
            "id": block_id,
            "type": block_type,
            "module_kind": module_kind,
            "tool": tool,
            "capability_id": capability_id,
            "execution_target": execution_target,
            "provider_id": provider_id,
            "label": str(raw_block.get("label") or block_id).strip(),
            "params": deepcopy(params),
            "preset_id": preset_id,
            "install_policy": install_policy
            or (
                "lazy"
                if tool_manifest and tool_manifest.get("install_required")
                else "server"
            ),
            "condition": step["if_expr"],
            "timeout_sec": step["timeout_sec"],
            "continue_on_error": step["continue_on_error"],
            "parallel_group": step["parallel_group"],
            "tool_manifest": deepcopy(tool_manifest) if tool_manifest else None,
            "evidence": deepcopy((tool_manifest or {}).get("evidence")) if isinstance((tool_manifest or {}).get("evidence"), dict) else None,
        }
        normalized_blocks.append(normalized_block)
        steps.append(step)

    required_capabilities = build_required_capabilities_manifest(normalized_blocks, catalog_by_capability)

    return {
        "playbook": {
            "key": key,
            "name": name,
            "domain": str(raw.get("domain") or "diagnostics").strip() or "diagnostics",
            "owner": str(raw.get("owner") or "admin").strip() or "admin",
        },
        "version": str(raw.get("version") or "1.0.0").strip() or "1.0.0",
        "manifest": {
            "schema": "pc_client.playbook.self_healing.v2",
            "scenario_class": "diagnostic",
            "blocks": normalized_blocks,
            "required_tools": [],
            "required_capabilities": required_capabilities,
            "source": "admin_low_code_builder",
        },
        "steps": steps,
    }
