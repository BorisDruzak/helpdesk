from __future__ import annotations

from typing import Iterable


AGENT_RECIPE_RUNNER_PROVIDER_ID = "agent_recipe_runner"
AGENT_RECIPE_SUPPORTED_PLATFORMS = {"win32", "linux"}


COMPOSITE_RECIPE_PRESENTATION_SCHEMA = {
    "version": "1.0",
    "kind": "composite_recipe",
    "title": "Рецепт диагностики",
    "summary": {
        "title_path": "summary.title",
        "message_path": "summary.message",
        "status_path": "status",
    },
    "steps": {
        "path": "steps",
        "title_path": "title",
        "status_path": "status",
        "tool_id_path": "tool_id",
        "primitive_id_path": "primitive_id",
        "result_path": "result",
        "default_layout": "timeline",
    },
    "fallback": {"show_step_raw_json": True},
}


def _primitive_presentation_schema(title: str, fields: list[dict]) -> dict:
    return {
        "version": "1.0",
        "kind": "tool_result",
        "title": title,
        "blocks": [
            {"type": "field_grid", "id": "result", "title": title, "fields": fields},
            {"type": "raw_json", "collapsed": True},
        ],
        "fallback": {"show_raw_json": True},
    }


PRIMITIVE_PRESENTATION_SCHEMAS = {
    "file.exists": _primitive_presentation_schema(
        "Файл",
        [
            {"path": "path", "label": "Путь"},
            {"path": "exists", "label": "Существует"},
            {"path": "is_file", "label": "Файл"},
            {"path": "is_dir", "label": "Папка"},
        ],
    ),
    "process.exists": _primitive_presentation_schema(
        "Процесс",
        [
            {"path": "process_name", "label": "Имя процесса"},
            {"path": "exists", "label": "Найден"},
            {"path": "matches", "label": "Совпадения"},
        ],
    ),
    "dns.resolve": _primitive_presentation_schema(
        "DNS-разрешение",
        [
            {"path": "hostname", "label": "Имя"},
            {"path": "resolved", "label": "Разрешено"},
            {"path": "addresses", "label": "IP-адреса"},
        ],
    ),
    "tcp.connect": _primitive_presentation_schema(
        "TCP-подключение",
        [
            {"path": "host", "label": "Хост"},
            {"path": "port", "label": "Порт"},
            {"path": "connected", "label": "Подключение"},
            {"path": "duration_ms", "label": "Время", "unit": "мс"},
            {"path": "error", "label": "Ошибка", "empty_text": "—"},
        ],
    ),
    "http.request": _primitive_presentation_schema(
        "HTTP-запрос",
        [
            {"path": "url", "label": "URL"},
            {"path": "method", "label": "Метод"},
            {"path": "status_code", "label": "Код"},
            {"path": "reason", "label": "Причина"},
            {"path": "ok", "label": "Успешно"},
        ],
    ),
    "service.status": _primitive_presentation_schema(
        "Служба Windows",
        [
            {"path": "service_name", "label": "Служба"},
            {"path": "exists", "label": "Существует"},
            {"path": "state", "label": "Состояние"},
            {"path": "matches_expected", "label": "Ожидаемое состояние"},
            {"path": "details.error", "label": "Ошибка", "empty_text": "—"},
        ],
    ),
    "systemd.service.status": _primitive_presentation_schema(
        "Служба systemd",
        [
            {"path": "service_name", "label": "Служба"},
            {"path": "exists", "label": "Существует"},
            {"path": "state", "label": "Состояние"},
            {"path": "matches_expected", "label": "Ожидаемое состояние"},
            {"path": "details.SubState", "label": "SubState", "empty_text": "—"},
        ],
    ),
}


DEFAULT_AGENT_RECIPE_PRIMITIVES = [
    {"primitive_id": "file.exists", "primitive_version": "1.0", "title": "File exists", "platforms": ["win32", "linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["file.exists"]},
    {"primitive_id": "process.exists", "primitive_version": "1.0", "title": "Process exists", "platforms": ["win32", "linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["process.exists"]},
    {"primitive_id": "dns.resolve", "primitive_version": "1.0", "title": "DNS resolve", "platforms": ["win32", "linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["dns.resolve"]},
    {"primitive_id": "tcp.connect", "primitive_version": "1.0", "title": "TCP connect", "platforms": ["win32", "linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["tcp.connect"]},
    {"primitive_id": "http.request", "primitive_version": "1.0", "title": "HTTP request", "platforms": ["win32", "linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["http.request"]},
    {"primitive_id": "service.status", "primitive_version": "1.0", "title": "Windows service status", "platforms": ["win32"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["service.status"]},
    {"primitive_id": "systemd.service.status", "primitive_version": "1.0", "title": "systemd service status", "platforms": ["linux"], "risk_level": "low", "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS["systemd.service.status"]},
]


class AgentRecipeValidationError(ValueError):
    """Raised when a declarative agent recipe contract is invalid."""


def normalize_recipe_platforms(platforms: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for item in platforms or []:
        value = str(item or "").strip().lower()
        if value in {"windows", "win"}:
            value = "win32"
        if value in {"mac", "macos", "darwin"}:
            raise AgentRecipeValidationError("agent_recipe does not support macOS platforms")
        if value not in AGENT_RECIPE_SUPPORTED_PLATFORMS:
            raise AgentRecipeValidationError("agent_recipe platforms must be win32 and/or linux")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise AgentRecipeValidationError("agent_recipe requires at least one supported platform")
    return normalized
