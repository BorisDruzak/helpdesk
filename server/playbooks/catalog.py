"""Diagnostic playbook catalog and draft normalization."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
DIAGNOSTIC_OUTPUT_CONTRACT = {
    "status": "success|error",
    "found": "object",
    "error_code": "string|null",
    "attachments": "array",
}

DIAGNOSTIC_MODULE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "system.collect",
        "label": "Системный снимок",
        "tool": "system.collect",
        "block_type": "diagnostic",
        "module_kind": "diagnostic",
        "description": "ОС, hostname, сеть, ресурсы и базовая идентичность агента.",
        "default_params": {"preset": "network"},
        "changes_device": False,
        "requires_confirmation": False,
        "output_contract": deepcopy(DIAGNOSTIC_OUTPUT_CONTRACT),
    },
    {
        "id": "ip_address.get_ip",
        "label": "IP-адрес",
        "tool": "ip_address.get_ip",
        "block_type": "diagnostic",
        "module_kind": "diagnostic",
        "description": "Публичный/локальный IP и быстрая проверка сетевой видимости.",
        "default_params": {},
        "changes_device": False,
        "requires_confirmation": False,
        "output_contract": deepcopy(DIAGNOSTIC_OUTPUT_CONTRACT),
    },
    {
        "id": "diag.logs.collect",
        "label": "Сбор логов",
        "tool": "diag.logs.collect",
        "block_type": "diagnostic",
        "module_kind": "diagnostic",
        "description": "Безопасный пакет логов агента для прикрепления к тикету.",
        "default_params": {"preset": "agent", "tail_lines": 500},
        "changes_device": False,
        "requires_confirmation": True,
        "output_contract": {
            **deepcopy(DIAGNOSTIC_OUTPUT_CONTRACT),
            "attachments": ["logs_bundle"],
        },
    },
]

SCENARIO_TEMPLATES: list[dict[str, Any]] = [
    {
        "key": "site_not_opening",
        "title": "Сайт не открывается",
        "problem": "Проверить сетевой контекст, IP и логи агента перед ручной эскалацией.",
        "recommended_form_keys": ["site_system", "network"],
        "block_ids": ["system.collect", "ip_address.get_ip", "diag.logs.collect"],
    },
    {
        "key": "printer_not_printing",
        "title": "Не печатает принтер",
        "problem": "Собрать системный снимок и окружение рабочего места.",
        "recommended_form_keys": ["printer"],
        "block_ids": ["system.collect", "diag.logs.collect"],
    },
    {
        "key": "access_issue",
        "title": "Нет доступа в систему",
        "problem": "Зафиксировать форму обращения и состояние агента без изменения устройства.",
        "recommended_form_keys": ["access", "site_system"],
        "block_ids": ["system.collect", "diag.logs.collect"],
    },
    {
        "key": "agent_offline",
        "title": "Агент не выходит на сервер",
        "problem": "Собрать локальный статус и последние логи агента.",
        "recommended_form_keys": ["breakage"],
        "block_ids": ["system.collect", "diag.logs.collect"],
    },
    {
        "key": "internet_not_working",
        "title": "Не работает интернет",
        "problem": "Проверить сетевые признаки, IP и базовые логи.",
        "recommended_form_keys": ["network"],
        "block_ids": ["system.collect", "ip_address.get_ip", "diag.logs.collect"],
    },
]


def _require_key(value: Any, *, field: str) -> str:
    key = str(value or "").strip()
    if not key:
        raise ValueError(f"{field} is required")
    if not KEY_PATTERN.match(key):
        raise ValueError(f"{field} must use latin snake_case")
    return key


def _step_type_for_block(block_type: str, tool: str | None) -> str:
    if block_type == "diagnostic":
        if not tool:
            raise ValueError("diagnostic block requires tool")
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
        tool = str(raw_block.get("tool") or "").strip() or None
        params = raw_block.get("params")
        if params is None:
            params = raw_block.get("default_params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError(f"block {block_id!r} params must be an object")

        step_type = _step_type_for_block(block_type, tool)
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
            "label": str(raw_block.get("label") or block_id).strip(),
            "params": deepcopy(params),
            "condition": step["if_expr"],
            "timeout_sec": step["timeout_sec"],
            "continue_on_error": step["continue_on_error"],
            "parallel_group": step["parallel_group"],
        }
        normalized_blocks.append(normalized_block)
        steps.append(step)

    return {
        "playbook": {
            "key": key,
            "name": name,
            "domain": str(raw.get("domain") or "diagnostics").strip() or "diagnostics",
            "owner": str(raw.get("owner") or "admin").strip() or "admin",
        },
        "version": str(raw.get("version") or "1.0.0").strip() or "1.0.0",
        "manifest": {
            "schema": "pc_client.playbook.diagnostic.v1",
            "scenario_class": "diagnostic",
            "blocks": normalized_blocks,
            "source": "admin_low_code_builder",
        },
        "steps": steps,
    }

