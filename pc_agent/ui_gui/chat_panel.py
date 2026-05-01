"""Ticket chat panel for the agent GUI."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QDateTime, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from loguru import logger

from pc_agent.core.action_trace import get_action_trace_recorder
from pc_agent.core.runtime_paths import resolve_data_root

from .server_api import TicketApiClient
from . import theme
from .ticket_format import (
    format_ts_short,
    normalize_iso_ts,
    ticket_row_fingerprint,
    ticket_status_colors,
    ticket_status_label,
)
from .tickets_list_model import TicketCardDelegate, TicketsListModel

PINNED_STUB_META_KEY = "agent_stub_reply_to_message"
TICKET_LIST_POLL_INTERVAL_MS = 10_000
TICKET_DETAIL_POLL_INTERVAL_MS = 5_000
TICKET_HISTORY_PAGE_SIZE = 100
TICKET_HISTORY_TOP_THRESHOLD_PX = 72

OUTGOING_MESSAGE_ROLES = {"user", "agent", "requester"}
SUPPORT_MESSAGE_ROLES = {"support", "admin"}
DEFAULT_TICKET_FORM_PACK_KEY = "request_forms"
DEFAULT_TICKET_FORM_PACK_VERSION = "1.0.0"
OPTION_FIELD_TYPES = {"select", "radio"}
MULTI_SELECT_FIELD_TYPES = {"multi_select"}
PICKER_FIELD_TYPES = {"user_picker", "department_picker", "location_picker", "device_picker", "service_picker"}
PICKER_OPTION_KEYS = {
    "user_picker": "users",
    "department_picker": "departments",
    "location_picker": "locations",
    "device_picker": "devices",
    "service_picker": "services",
}

DEFAULT_PRIORITY_POLICY = {
    "impact_field": "impact_scope",
    "urgency_field": "work_continuity",
    "importance_field": "business_importance",
    "modifier_fields": {
        "critical_service": "critical_service",
        "public_service": "public_service",
    },
}
DEFAULT_PRIORITY_FIELD_ROLES = {
    "impact_scope": ["priority_field"],
    "work_continuity": ["priority_field"],
    "business_importance": ["priority_field"],
    "critical_service": ["priority_field", "sla_field"],
    "public_service": ["priority_field", "sla_field"],
}
HIGH_URGENCY_FACTS = {"work_stopped_no_workaround", "work_stopped", "no_workaround"}
HIGH_IMPORTANCE_FACTS = {"deadline_today", "deadline_tomorrow", "critical", "security", "public_service"}
AGENT_CREATE_ATTACHMENT_MAX_BYTES = 200 * 1024 * 1024


def build_default_priority_fields() -> list[dict[str, Any]]:
    return [
        {
            "key": "impact_scope",
            "label": "Кого затронула проблема?",
            "type": "radio",
            "required": True,
            "placeholder": "",
            "help_text": "",
            "options": [
                {"value": "single_user", "label": "Только меня"},
                {"value": "group", "label": "Несколько человек"},
                {"value": "department", "label": "Весь отдел"},
                {"value": "building_or_org", "label": "Здание / организация / критичная система"},
            ],
            "visible_when": None,
        },
        {
            "key": "work_continuity",
            "label": "Можно ли продолжать работу?",
            "type": "radio",
            "required": True,
            "placeholder": "",
            "help_text": "",
            "options": [
                {"value": "work_stopped_no_workaround", "label": "Нет, работа остановлена"},
                {"value": "partial_work", "label": "Можно работать частично"},
                {"value": "workaround_available", "label": "Есть обходной путь"},
                {"value": "inconvenience_only", "label": "Неудобно, но не блокирует"},
            ],
            "visible_when": None,
        },
        {
            "key": "business_importance",
            "label": "Есть важный срок или критичный процесс?",
            "type": "radio",
            "required": False,
            "placeholder": "",
            "help_text": "",
            "options": [
                {"value": "normal", "label": "Нет, обычная рабочая ситуация"},
                {"value": "deadline", "label": "Есть важный срок"},
                {"value": "deadline_today", "label": "Сегодня / завтра крайний срок"},
                {"value": "security", "label": "ИБ / публичная услуга / критичный процесс"},
            ],
            "visible_when": None,
        },
        {
            "key": "critical_service",
            "label": "Затронута критичная система",
            "type": "checkbox",
            "required": False,
            "placeholder": "Да",
            "help_text": "",
            "options": [],
            "visible_when": None,
        },
        {
            "key": "public_service",
            "label": "Затронут прием граждан / публичная услуга",
            "type": "checkbox",
            "required": False,
            "placeholder": "Да",
            "help_text": "",
            "options": [],
            "visible_when": None,
        },
    ]


def build_priority_facts_payload(
    *,
    impact_scope: str,
    work_continuity: str,
    business_importance: str,
    urgency_reason: str = "",
    importance_reason: str = "",
) -> dict[str, Any]:
    impact_scope = str(impact_scope or "single_user").strip() or "single_user"
    work_continuity = str(work_continuity or "workaround_available").strip() or "workaround_available"
    business_importance = str(business_importance or "normal").strip() or "normal"
    urgency = work_continuity in HIGH_URGENCY_FACTS
    importance = business_importance in HIGH_IMPORTANCE_FACTS or impact_scope in {"organization", "building_or_org", "critical_system"}
    return {
        "urgency": urgency,
        "importance": importance,
        "urgency_reason": urgency_reason.strip() or f"work_continuity={work_continuity}",
        "importance_reason": importance_reason.strip() or f"business_importance={business_importance}",
        "form_payload": {
            "impact_scope": impact_scope,
            "work_continuity": work_continuity,
            "business_importance": business_importance,
        },
    }


def ticket_form_priority_field_keys(form_def: Optional[dict[str, Any]]) -> list[str]:
    if not isinstance(form_def, dict):
        return []
    ordered: list[str] = []
    policy = form_def.get("priority_policy") if isinstance(form_def.get("priority_policy"), dict) else {}
    for policy_key in ("impact_field", "urgency_field", "importance_field"):
        field_key = str(policy.get(policy_key) or "").strip()
        if field_key and field_key not in ordered:
            ordered.append(field_key)
    modifier_fields = policy.get("modifier_fields") if isinstance(policy.get("modifier_fields"), dict) else {}
    for raw_field_key in modifier_fields.values():
        field_key = str(raw_field_key or "").strip()
        if field_key and field_key not in ordered:
            ordered.append(field_key)
    field_roles = form_def.get("field_roles") if isinstance(form_def.get("field_roles"), dict) else {}
    for raw_field_key, roles in field_roles.items():
        field_key = str(raw_field_key or "").strip()
        if field_key and isinstance(roles, list) and "priority_field" in roles and field_key not in ordered:
            ordered.append(field_key)
    form_field_keys = {
        str(field.get("key") or "").strip()
        for field in form_def.get("fields") or []
        if isinstance(field, dict)
    }
    return [field_key for field_key in ordered if field_key in form_field_keys]


def build_priority_facts_payload_from_form(
    form_def: Optional[dict[str, Any]],
    form_payload: dict[str, Any],
    *,
    fallback: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    fallback = fallback or build_priority_facts_payload(
        impact_scope="single_user",
        work_continuity="workaround_available",
        business_importance="normal",
    )
    policy = form_def.get("priority_policy") if isinstance(form_def, dict) and isinstance(form_def.get("priority_policy"), dict) else {}
    impact_key = str(policy.get("impact_field") or "impact_scope").strip()
    urgency_key = str(policy.get("urgency_field") or "work_continuity").strip()
    importance_key = str(policy.get("importance_field") or "business_importance").strip()
    fallback_values = fallback.get("form_payload") if isinstance(fallback.get("form_payload"), dict) else {}
    return build_priority_facts_payload(
        impact_scope=str(form_payload.get(impact_key) or fallback_values.get("impact_scope") or "single_user"),
        work_continuity=str(form_payload.get(urgency_key) or fallback_values.get("work_continuity") or "workaround_available"),
        business_importance=str(form_payload.get(importance_key) or fallback_values.get("business_importance") or "normal"),
        urgency_reason=str(fallback.get("urgency_reason") or ""),
        importance_reason=str(fallback.get("importance_reason") or ""),
    )


def _duration_to_user_text(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minutes = max(1, int(value))
        if minutes % 1440 == 0:
            return f"{minutes // 1440} дн"
        if minutes % 60 == 0:
            return f"{minutes // 60} ч"
        if minutes > 60:
            hours, remaining_minutes = divmod(minutes, 60)
            return f"{hours} ч {remaining_minutes} мин"
        return f"{minutes} мин"
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw.isdigit():
        return _duration_to_user_text(int(raw))
    match = re.match(r"^(\d+)\s*([mhd])$", raw)
    if not match:
        return raw
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return f"{amount} мин"
    if unit == "h":
        return f"{amount} ч"
    return f"{amount} дн"


def _bytes_to_user_text(size: int) -> str:
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} МБ"
    return f"{size / (1024 * 1024 * 1024):.1f} ГБ"


def format_attachment_item_label(file_path: str) -> str:
    path = Path(str(file_path or "").strip())
    name = path.name or str(file_path or "").strip()
    if not name:
        return "Файл"
    try:
        if path.exists() and path.is_file():
            return f"{name} · {_bytes_to_user_text(path.stat().st_size)}"
    except OSError:
        return name
    return name


def validate_create_attachment_paths(
    paths: list[str],
    *,
    max_bytes: int = AGENT_CREATE_ATTACHMENT_MAX_BYTES,
) -> list[str]:
    errors: list[str] = []
    for raw_path in paths:
        text = str(raw_path or "").strip()
        if not text:
            continue
        path = Path(text)
        name = path.name or text
        try:
            if not path.exists() or not path.is_file():
                errors.append(f"Файл не найден: {name}")
                continue
            size = path.stat().st_size
        except OSError:
            errors.append(f"Файл недоступен: {name}")
            continue
        if size > max_bytes:
            errors.append(f"Файл слишком большой: {name}. Максимум {_bytes_to_user_text(max_bytes)}.")
    return errors


def build_ticket_create_error_message(exc: BaseException | str) -> str:
    raw = str(exc or "").strip()
    lowered = raw.lower()
    if any(marker in lowered for marker in ("cannot connect", "connection refused", "connect call failed", "server disconnected")):
        return "Сервер поддержки недоступен. Проверьте подключение и попробуйте отправить обращение ещё раз."
    if any(marker in lowered for marker in ("form_version_conflict", "form_version", "pack version", "форма обращения обнов")):
        return "Форма обращения изменилась на сервере. Обновите шаблоны и проверьте поля перед отправкой."
    if any(marker in lowered for marker in ("413", "too large", "payload too large", "request entity too large")):
        return "Файл слишком большой. Уберите крупное вложение или приложите меньший файл."
    if any(marker in lowered for marker in ("file not found", "no such file", "не найден", "not found")):
        return "Один из файлов не найден. Уберите его из вложений или выберите файл заново."
    return "Не удалось создать обращение. Проверьте данные и попробуйте ещё раз."


def _target_for_priority(policy: dict[str, Any], target_key: str, priority_class: str) -> str:
    targets = policy.get("targets") if isinstance(policy.get("targets"), dict) else {}
    target_block = targets.get(target_key) if isinstance(targets.get(target_key), dict) else {}
    return str(target_block.get(priority_class) or target_block.get("P3") or "").strip()


def build_request_creation_preview(
    form_def: Optional[dict[str, Any]],
    *,
    priority_class: str = "P3",
    server_preview: Optional[dict[str, Any]] = None,
) -> str:
    if not isinstance(form_def, dict):
        return "Шаблон обращения пока не выбран."
    if isinstance(server_preview, dict):
        preview = server_preview.get("preview") if isinstance(server_preview.get("preview"), dict) else server_preview
        lines: list[str] = []
        title = str(
            preview.get("request_template_title")
            or form_def.get("request_template_title")
            or form_def.get("title")
            or form_def.get("key")
            or ""
        ).strip()
        if title:
            lines.append(f"Шаблон: {title}")
        routing = preview.get("routing") if isinstance(preview.get("routing"), dict) else {}
        queue = routing.get("target_queue_name") or routing.get("target_queue_id")
        if queue:
            lines.append(f"Предварительно попадёт в очередь: {queue}")
        if preview.get("approval_required"):
            lines.append("Потребуется согласование.")
        if preview.get("diagnostic_consent_required"):
            lines.append("Перед диагностикой потребуется ваше согласие.")
        sla = preview.get("sla") if isinstance(preview.get("sla"), dict) else {}
        first_response = _duration_to_user_text(sla.get("first_response_minutes"))
        resolution = _duration_to_user_text(sla.get("resolution_minutes"))
        if first_response:
            lines.append(f"Вам должны ответить примерно за {first_response}.")
        if resolution:
            lines.append(f"Решение или обходной вариант ожидается примерно за {resolution}.")
        if lines:
            return "\n".join(lines)

    lines: list[str] = []
    title = str(form_def.get("request_template_title") or form_def.get("title") or form_def.get("key") or "").strip()
    if title:
        lines.append(f"Шаблон: {title}")

    routing_policy = form_def.get("routing_policy") if isinstance(form_def.get("routing_policy"), dict) else {}
    fallback = routing_policy.get("fallback") if isinstance(routing_policy.get("fallback"), dict) else {}
    queue = (
        routing_policy.get("default_queue")
        or routing_policy.get("default_queue_id")
        or fallback.get("queue")
        or form_def.get("default_queue_id")
    )
    if queue:
        lines.append(f"Предварительно попадёт в очередь: {queue}")

    approval_policy = form_def.get("approval_policy") if isinstance(form_def.get("approval_policy"), dict) else {}
    if approval_policy.get("required"):
        lines.append("Потребуется согласование.")

    diagnostic_policy = form_def.get("diagnostic_policy") if isinstance(form_def.get("diagnostic_policy"), dict) else {}
    consent = diagnostic_policy.get("consent") if isinstance(diagnostic_policy.get("consent"), dict) else {}
    if diagnostic_policy.get("requires_user_consent") or consent.get("required_for_requester_device"):
        lines.append("Перед диагностикой потребуется ваше согласие.")
    elif diagnostic_policy.get("suggested_playbooks") or diagnostic_policy.get("suggested_playbook"):
        lines.append("После создания можно будет запустить диагностику.")

    sla_policy = form_def.get("sla_policy") if isinstance(form_def.get("sla_policy"), dict) else {}
    first_response = _duration_to_user_text(_target_for_priority(sla_policy, "first_response", priority_class))
    resolution = _duration_to_user_text(_target_for_priority(sla_policy, "resolution", priority_class))
    if first_response:
        lines.append(f"Вам должны ответить примерно за {first_response}.")
    if resolution:
        lines.append(f"Решение или обходной вариант ожидается примерно за {resolution}.")

    if not lines:
        return "После создания служба поддержки рассчитает очередь, сроки и дальнейшие действия."
    return "\n".join(lines)


def build_request_template_card_summary(form_def: Optional[dict[str, Any]], *, priority_class: str = "P3") -> str:
    if not isinstance(form_def, dict):
        return "Выберите шаблон обращения."

    title = str(form_def.get("request_template_title") or form_def.get("title") or form_def.get("key") or "").strip()
    category = str(form_def.get("category") or form_def.get("category_id") or form_def.get("ticket_type") or "").strip()
    description = str(form_def.get("description") or "").strip()
    fields = form_def.get("fields") if isinstance(form_def.get("fields"), list) else []
    required_labels = [
        str(field.get("label") or field.get("key") or "").strip()
        for field in fields
        if isinstance(field, dict) and field.get("required")
    ]
    required_labels = [label for label in required_labels if label]

    badges: list[str] = []
    approval_policy = form_def.get("approval_policy") if isinstance(form_def.get("approval_policy"), dict) else {}
    if approval_policy.get("required"):
        badges.append("Нужно согласование")

    diagnostic_policy = form_def.get("diagnostic_policy") if isinstance(form_def.get("diagnostic_policy"), dict) else {}
    if (
        diagnostic_policy.get("suggested_playbooks")
        or diagnostic_policy.get("suggested_playbook")
        or diagnostic_policy.get("suggested_playbook_id")
    ):
        badges.append("Может быть диагностика")

    if any(isinstance(field, dict) and str(field.get("type") or "").strip().lower() == "file" for field in fields):
        badges.append("Понадобятся файлы")

    sla_policy = form_def.get("sla_policy") if isinstance(form_def.get("sla_policy"), dict) else {}
    if _target_for_priority(sla_policy, "first_response", priority_class):
        badges.append("Есть сроки ответа")

    lines: list[str] = []
    if title:
        lines.append(title)
    if category:
        lines.append(f"Категория: {category}")
    if description:
        lines.append(description)
    if required_labels:
        lines.append(f"Обязательные поля: {', '.join(required_labels[:4])}")
    if badges:
        lines.append(" · ".join(badges))

    preview = build_request_creation_preview(form_def, priority_class=priority_class)
    preview_lines = [line for line in preview.splitlines() if not line.startswith("Шаблон:")]
    if preview_lines:
        lines.append("Что будет дальше:")
        lines.extend(preview_lines)

    return "\n".join(lines) if lines else "Выберите шаблон обращения."


def diagnostic_consent_required(form_def: Optional[dict[str, Any]]) -> bool:
    if not isinstance(form_def, dict):
        return False
    diagnostic_policy = form_def.get("diagnostic_policy") if isinstance(form_def.get("diagnostic_policy"), dict) else {}
    consent = diagnostic_policy.get("consent") if isinstance(diagnostic_policy.get("consent"), dict) else {}
    return bool(diagnostic_policy.get("requires_user_consent") or consent.get("required_for_requester_device"))


def build_diagnostic_consent_payload(form_def: Optional[dict[str, Any]], *, granted: bool) -> Optional[dict[str, Any]]:
    if not diagnostic_consent_required(form_def):
        return None
    return {
        "required": True,
        "granted": bool(granted),
        "scope": "requester_device",
        "source": "pc_agent_create",
        "request_template_key": str((form_def or {}).get("request_template_key") or (form_def or {}).get("key") or "").strip(),
    }


def build_default_ticket_form_pack() -> dict[str, Any]:
    pack = {
        "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
        "version": DEFAULT_TICKET_FORM_PACK_VERSION,
        "title": "Каталог заявок",
        "description": "Базовый каталог интеллектуальных форм.",
        "forms": [
            {
                "key": "breakage",
                "request_kind": "breakage",
                "title": "Поломка",
                "description": "Проблема с оборудованием или рабочим местом.",
                "fields": [
                    {"key": "asset_name", "label": "Что сломалось", "type": "text", "required": True, "placeholder": "Компьютер, монитор, МФУ", "help_text": "", "options": [], "visible_when": None},
                    {"key": "room", "label": "Кабинет", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "inventory_number", "label": "Инвентарный номер", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "access",
                "request_kind": "access",
                "title": "Доступ",
                "description": "Выдача или изменение доступа.",
                "fields": [
                    {"key": "system_name", "label": "В какую систему", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "role_name", "label": "Какая роль", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "approver", "label": "Кто согласует", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "software_install",
                "request_kind": "software_install",
                "title": "Установка ПО",
                "description": "Установка или обновление программного обеспечения.",
                "fields": [
                    {"key": "software_name", "label": "Какое ПО", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "version", "label": "Нужная версия", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "license_owner", "label": "Есть лицензия / кто владелец", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "hardware_replacement",
                "request_kind": "hardware_replacement",
                "title": "Замена техники",
                "description": "Замена ПК, периферии или другой техники.",
                "fields": [
                    {"key": "replace_what", "label": "Что нужно заменить", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "room", "label": "Кабинет", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "reason", "label": "Причина замены", "type": "textarea", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "printer",
                "request_kind": "printer",
                "title": "Печать / принтер",
                "description": "Проблемы с печатью или самим принтером.",
                "fields": [
                    {"key": "room", "label": "Кабинет", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "printer_model", "label": "Модель", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "printer_number", "label": "Номер принтера", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "network",
                "request_kind": "network",
                "title": "Сеть / интернет",
                "description": "Проблемы с локальной сетью или интернетом.",
                "fields": [
                    {"key": "room", "label": "Кабинет", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "pc_name", "label": "С какого ПК", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {
                        "key": "affected_scope",
                        "label": "У всех или у одного",
                        "type": "radio",
                        "required": False,
                        "placeholder": "",
                        "help_text": "",
                        "options": [
                            {"value": "single", "label": "У одного"},
                            {"value": "multiple", "label": "У нескольких"},
                            {"value": "all", "label": "У всех"},
                        ],
                        "visible_when": None,
                    },
                ],
            },
            {
                "key": "site_system",
                "request_kind": "site_system",
                "title": "Сайт / система",
                "description": "Проблемы с сайтом, сервисом или бизнес-системой.",
                "fields": [
                    {
                        "key": "issue_kind",
                        "label": "Тип проблемы",
                        "type": "select",
                        "required": True,
                        "placeholder": "",
                        "help_text": "",
                        "options": [
                            {"value": "site_down", "label": "Сайт не открывается"},
                            {"value": "auth", "label": "Не удаётся войти"},
                            {"value": "functional", "label": "Ошибка в работе функции"},
                        ],
                        "visible_when": None,
                    },
                    {"key": "system_name", "label": "Система / сайт", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "url", "label": "URL", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": {"field": "issue_kind", "equals": "site_down"}},
                    {"key": "pc_name", "label": "С какого ПК", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": {"field": "issue_kind", "equals": "site_down"}},
                    {
                        "key": "affected_scope",
                        "label": "У всех или у одного",
                        "type": "radio",
                        "required": False,
                        "placeholder": "",
                        "help_text": "",
                        "options": [
                            {"value": "single", "label": "У одного"},
                            {"value": "multiple", "label": "У нескольких"},
                            {"value": "all", "label": "У всех"},
                        ],
                        "visible_when": {"field": "issue_kind", "equals": "site_down"},
                    },
                ],
            },
            {
                "key": "new_account",
                "request_kind": "new_account",
                "title": "Новая учётка",
                "description": "Создание новой учётной записи.",
                "fields": [
                    {"key": "employee_name", "label": "Для кого", "type": "text", "required": True, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "department", "label": "Подразделение", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {"key": "systems", "label": "Какие системы нужны", "type": "textarea", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                ],
            },
            {
                "key": "mail_issue",
                "request_kind": "mail_issue",
                "title": "Проблема с почтой",
                "description": "Почта не приходит, не отправляется или не работает.",
                "fields": [
                    {"key": "mailbox", "label": "Почтовый ящик", "type": "text", "required": False, "placeholder": "", "help_text": "", "options": [], "visible_when": None},
                    {
                        "key": "problem_type",
                        "label": "Проблема",
                        "type": "select",
                        "required": False,
                        "placeholder": "",
                        "help_text": "",
                        "options": [
                            {"value": "send", "label": "Не отправляется"},
                            {"value": "receive", "label": "Не приходит"},
                            {"value": "auth", "label": "Не удаётся войти"},
                            {"value": "other", "label": "Другое"},
                        ],
                        "visible_when": None,
                    },
                ],
            },
        ],
    }
    ticket_type_by_key = {
        "breakage": "incident",
        "printer": "incident",
        "network": "incident",
        "site_system": "incident",
        "mail_issue": "incident",
        "access": "access_request",
        "new_account": "access_request",
        "software_install": "service_request",
        "hardware_replacement": "service_request",
    }
    for form in pack["forms"]:
        form.setdefault("request_template_key", str(form.get("key") or "").strip())
        form.setdefault("request_template_title", str(form.get("title") or form.get("key") or "").strip())
        form.setdefault("ticket_type", ticket_type_by_key.get(str(form.get("key") or ""), "service_request"))
        form.setdefault("priority_policy", dict(DEFAULT_PRIORITY_POLICY))
        existing_keys = {
            str(field.get("key") or "").strip()
            for field in form.get("fields") or []
            if isinstance(field, dict)
        }
        for field in build_default_priority_fields():
            if field["key"] not in existing_keys:
                form.setdefault("fields", []).append(dict(field))
        roles = dict(DEFAULT_PRIORITY_FIELD_ROLES)
        roles.update(form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {})
        form["field_roles"] = roles
    return pack


def normalize_ticket_form_pack(raw_pack: Any) -> dict[str, Any]:
    pack = raw_pack if isinstance(raw_pack, dict) else {}
    normalized = {
        "pack_key": str(pack.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY,
        "version": str(pack.get("version") or DEFAULT_TICKET_FORM_PACK_VERSION).strip() or DEFAULT_TICKET_FORM_PACK_VERSION,
        "title": str(pack.get("title") or "Каталог заявок").strip() or "Каталог заявок",
        "description": str(pack.get("description") or "").strip(),
        "forms": [],
    }
    raw_forms = pack.get("forms") if isinstance(pack.get("forms"), list) else []
    for form in raw_forms:
        if not isinstance(form, dict):
            continue
        form_key = str(form.get("key") or "").strip()
        if not form_key:
            continue
        normalized_form = {
            "key": form_key,
            "request_template_key": str(form.get("request_template_key") or form_key).strip() or form_key,
            "request_template_title": str(form.get("request_template_title") or form.get("title") or form_key).strip() or form_key,
            "request_kind": str(form.get("request_kind") or form_key).strip() or form_key,
            "ticket_type": str(form.get("ticket_type") or form.get("request_kind") or form_key).strip() or form_key,
            "title": str(form.get("title") or form_key).strip() or form_key,
            "description": str(form.get("description") or "").strip(),
            "priority_policy": form.get("priority_policy") if isinstance(form.get("priority_policy"), dict) else {},
            "field_roles": form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
            "routing_policy": form.get("routing_policy") if isinstance(form.get("routing_policy"), dict) else {},
            "approval_policy": form.get("approval_policy") if isinstance(form.get("approval_policy"), dict) else {},
            "diagnostic_policy": form.get("diagnostic_policy") if isinstance(form.get("diagnostic_policy"), dict) else {},
            "sla_policy": form.get("sla_policy") if isinstance(form.get("sla_policy"), dict) else {},
            "default_queue_id": form.get("default_queue_id"),
            "fields": [],
        }
        raw_fields = form.get("fields") if isinstance(form.get("fields"), list) else []
        for field in raw_fields:
            if not isinstance(field, dict):
                continue
            field_key = str(field.get("key") or "").strip()
            if not field_key:
                continue
            field_type = str(field.get("type") or "text").strip().lower() or "text"
            normalized_form["fields"].append(
                {
                    "key": field_key,
                    "label": str(field.get("label") or field_key).strip() or field_key,
                    "type": field_type,
                    "required": bool(field.get("required")),
                    "placeholder": str(field.get("placeholder") or "").strip(),
                    "help_text": str(field.get("help_text") or "").strip(),
                    "options": [
                        {
                            "value": str(option.get("value") or "").strip(),
                            "label": str(option.get("label") or option.get("value") or "").strip(),
                        }
                        for option in (field.get("options") if isinstance(field.get("options"), list) else [])
                        if isinstance(option, dict) and str(option.get("value") or "").strip()
                    ],
                    "visible_when": field.get("visible_when") if isinstance(field.get("visible_when"), dict) else None,
                }
            )
        normalized["forms"].append(normalized_form)
    if not normalized["forms"]:
        return build_default_ticket_form_pack()
    return normalized


def ticket_form_field_visible(field_def: dict[str, Any], values: dict[str, Any]) -> bool:
    rule = field_def.get("visible_when")
    if not isinstance(rule, dict):
        return True
    current_value = values.get(str(rule.get("field") or ""))
    if "equals" in rule:
        return str(current_value or "").strip() == str(rule.get("equals") or "").strip()
    allowed = {str(item or "").strip() for item in rule.get("in") or []}
    return str(current_value or "").strip() in allowed


def ticket_request_form_summary_rows(ticket: dict) -> List[tuple[str, str]]:
    custom_fields = ticket.get("custom_fields") if isinstance(ticket.get("custom_fields"), dict) else {}
    rows: List[tuple[str, str]] = []
    form_title = str(custom_fields.get("request_form_title") or "").strip()
    if form_title:
        rows.append(("Форма", form_title))
    for item in custom_fields.get("request_form_summary") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        if label and value:
            rows.append((label, value))
    return rows


def can_user_confirm_close(ticket: dict) -> bool:
    return str(ticket.get("status") or "").strip().lower() == "resolved"


def build_ticket_sla_user_summary(ticket: dict) -> str:
    priority = str(ticket.get("priority_class") or ticket.get("priority") or "").strip()
    first_response = str(ticket.get("first_response_due_at") or "").strip()
    resolution = str(ticket.get("resolution_due_at") or "").strip()
    parts: list[str] = []
    if priority:
        parts.append(f"Приоритет: {priority}")
    if first_response:
        parts.append(f"Вам должны ответить до {first_response}")
    if resolution:
        parts.append(f"Решение или обходной вариант ожидается до {resolution}")
    return "; ".join(parts)


def _format_user_deadline(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return normalize_iso_ts(text) or text


def _request_template_context(ticket: dict) -> dict[str, Any]:
    custom_fields = ticket.get("custom_fields") if isinstance(ticket.get("custom_fields"), dict) else {}
    template = custom_fields.get("request_template") if isinstance(custom_fields.get("request_template"), dict) else {}
    return template


def build_post_create_process_summary(ticket: dict, *, public_access_code: str = "") -> str:
    """Requester-facing process summary shown after a ticket is created."""
    if not isinstance(ticket, dict):
        ticket = {}
    template = _request_template_context(ticket)
    lines: list[str] = []
    code = str(public_access_code or ticket.get("public_access_code") or "").strip()
    if code:
        lines.append(f"Код доступа: {code}")

    public_status = str(ticket.get("public_status_label") or ticket_status_label(str(ticket.get("status") or "")) or "").strip()
    if public_status:
        lines.append(f"Статус: {public_status}")

    queue = str(ticket.get("queue_name") or ticket.get("queue_code") or ticket.get("queue_id") or "").strip()
    if queue:
        lines.append(f"Очередь: {queue}")

    assignee = str(ticket.get("assignee_display_name") or ticket.get("assignee_name") or ticket.get("assignee_id") or "").strip()
    lines.append(f"Исполнитель: {assignee or 'пока не назначен'}")

    next_owner = str(ticket.get("next_action_owner") or "").strip().lower()
    if next_owner in {"support", "assignee", "queue"}:
        lines.append("Сейчас работает поддержка.")
    elif next_owner in {"requester", "user"}:
        lines.append("Сейчас нужен ваш ответ.")
    elif next_owner in {"approval", "approver"}:
        lines.append("Сейчас ожидается согласование.")

    approval_policy = template.get("approval_policy") if isinstance(template.get("approval_policy"), dict) else {}
    if approval_policy.get("required"):
        lines.append("Потребуется согласование.")

    diagnostic_policy = template.get("diagnostic_policy") if isinstance(template.get("diagnostic_policy"), dict) else {}
    if (
        diagnostic_policy.get("suggested_playbooks")
        or diagnostic_policy.get("suggested_playbook_id")
        or diagnostic_policy.get("suggested_playbook")
    ):
        lines.append("Диагностика может быть предложена специалистом.")

    first_response_due = _format_user_deadline(ticket.get("first_response_due_at"))
    resolution_due = _format_user_deadline(ticket.get("resolution_due_at"))
    if first_response_due:
        lines.append(f"Вам должны ответить до {first_response_due}.")
    if resolution_due:
        lines.append(f"Решение или обходной вариант ожидается до {resolution_due}.")

    reporting_policy = template.get("reporting_policy") if isinstance(template.get("reporting_policy"), dict) else {}
    closure_policy = template.get("closure_policy") if isinstance(template.get("closure_policy"), dict) else {}
    if reporting_policy.get("enabled") or reporting_policy.get("required_sections") or closure_policy.get("evidence"):
        lines.append("Паспорт решения будет заполнен по итогам работ.")

    if not lines:
        return "Обращение создано. Служба поддержки рассчитает очередь, сроки и дальнейшие действия."
    return "\n".join(lines)


def ticket_matches_query(ticket: dict, query: str) -> bool:
    normalized_query = (query or "").strip().casefold()
    if not normalized_query:
        return True
    haystack = " ".join(
        str(ticket.get(key) or "")
        for key in (
            "ticket_code",
            "ticket_id",
            "title",
            "description",
            "status",
            "priority_class",
            "priority",
            "queue_code",
            "assignee_id",
            "requester_display_name",
        )
    ).casefold()
    return normalized_query in haystack


def message_visual_role(message: dict) -> str:
    role = str(message.get("from_role") or "").strip().lower()
    direction = str(message.get("direction") or "").strip().lower()
    if direction == "from_agent" or role in OUTGOING_MESSAGE_ROLES:
        return "self"
    if role in SUPPORT_MESSAGE_ROLES:
        return "support"
    return "neutral"


def merge_ticket_stream(existing: List[dict], incoming: List[dict], *, key_fields: tuple[str, ...]) -> List[dict]:
    merged = list(existing)
    seen = set()
    for item in merged:
        for key_field in key_fields:
            value = item.get(key_field)
            if value not in (None, ""):
                seen.add((key_field, str(value)))
                break
    for item in incoming:
        marker = None
        for key_field in key_fields:
            value = item.get(key_field)
            if value not in (None, ""):
                marker = (key_field, str(value))
                break
        if marker and marker in seen:
            continue
        if marker:
            seen.add(marker)
        merged.append(item)
    return merged


def prepend_ticket_stream(existing: List[dict], incoming: List[dict], *, key_fields: tuple[str, ...]) -> List[dict]:
    merged_existing = list(existing)
    seen = set()
    for item in merged_existing:
        for key_field in key_fields:
            value = item.get(key_field)
            if value not in (None, ""):
                seen.add((key_field, str(value)))
                break

    prepended: List[dict] = []
    for item in incoming:
        marker = None
        for key_field in key_fields:
            value = item.get(key_field)
            if value not in (None, ""):
                marker = (key_field, str(value))
                break
        if marker and marker in seen:
            continue
        if marker:
            seen.add(marker)
        prepended.append(item)
    return prepended + merged_existing


class MessageBubbleWidget(QFrame):
    """Single message/event bubble in the messenger timeline."""

    def __init__(
        self,
        panel: "ChatPanel",
        bubble_role: str,
        sender: str,
        text: str,
        ts_text: str,
        attachments: Optional[List[str]] = None,
        menu_text: Optional[str] = None,
        reply_to: Optional[dict] = None,
        message_context: Optional[dict] = None,
    ) -> None:
        super().__init__(panel)
        self._panel = panel
        self._bubble_role = bubble_role
        self._menu_text = (menu_text or text or "").strip()
        self._interactive = bubble_role in {"self", "support"}
        self._message_context = dict(message_context or {})
        self._sender_label: Optional[QLabel] = None
        self._reply_wrap: Optional[QFrame] = None
        self._reply_author_label: Optional[QLabel] = None
        self._reply_preview_label: Optional[QLabel] = None
        self._text_label: Optional[QLabel] = None
        self._time_label: Optional[QLabel] = None
        self._attachment_labels: list[QLabel] = []
        self.setObjectName(f"bubble_{bubble_role}")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        styles = {
            "self": (
                theme.BUBBLE_SELF_BG,
                theme.BUBBLE_SELF_BORDER,
                theme.BUBBLE_SELF_FG,
                theme.TEXT_MUTED,
            ),
            "support": (
                theme.BUBBLE_SUPPORT_BG,
                theme.BUBBLE_SUPPORT_BORDER,
                theme.BUBBLE_SUPPORT_FG,
                theme.TEXT_MUTED,
            ),
            "event": (
                theme.BUBBLE_EVENT_BG,
                theme.BUBBLE_EVENT_BORDER,
                theme.BUBBLE_EVENT_FG,
                theme.BUBBLE_EVENT_MUTED,
            ),
        }
        bg, border, fg, muted = styles.get(bubble_role, styles["event"])

        self.setStyleSheet(
            f"""
            QFrame#{self.objectName()} {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(6)

        if sender:
            sender_label = QLabel(sender)
            sender_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._sender_label = sender_label
            layout.addWidget(sender_label)

        reply_info = self._panel._resolve_reply_reference(reply_to)
        if reply_info:
            reply_author = QLabel(reply_info.get("sender_display_name") or "Ответ")
            reply_author.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_preview = QLabel(reply_info.get("preview") or "")
            reply_preview.setWordWrap(True)
            reply_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_wrap = QFrame()
            reply_wrap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reply_layout = QVBoxLayout(reply_wrap)
            reply_layout.setContentsMargins(8, 6, 8, 6)
            reply_layout.setSpacing(2)
            reply_layout.addWidget(reply_author)
            reply_layout.addWidget(reply_preview)
            self._reply_wrap = reply_wrap
            self._reply_author_label = reply_author
            self._reply_preview_label = reply_preview
            layout.addWidget(reply_wrap)

        text_label = QLabel(text or "Вложение")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._text_label = text_label
        layout.addWidget(text_label)

        for attachment in attachments or []:
            chip = QLabel(attachment)
            chip.setWordWrap(True)
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._attachment_labels.append(chip)
            layout.addWidget(chip)

        if ts_text:
            time_label = QLabel(ts_text)
            time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._time_label = time_label
            layout.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignRight if bubble_role == "support" else Qt.AlignmentFlag.AlignLeft)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        styles = {
            "self": (
                theme.BUBBLE_SELF_BG,
                theme.BUBBLE_SELF_BORDER,
                theme.BUBBLE_SELF_FG,
                theme.TEXT_MUTED,
            ),
            "support": (
                theme.BUBBLE_SUPPORT_BG,
                theme.BUBBLE_SUPPORT_BORDER,
                theme.BUBBLE_SUPPORT_FG,
                theme.TEXT_MUTED,
            ),
            "event": (
                theme.BUBBLE_EVENT_BG,
                theme.BUBBLE_EVENT_BORDER,
                theme.BUBBLE_EVENT_FG,
                theme.BUBBLE_EVENT_MUTED,
            ),
        }
        bg, border, fg, muted = styles.get(self._bubble_role, styles["event"])
        self.setStyleSheet(
            f"""
            QFrame#{self.objectName()} {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )
        if self._sender_label is not None:
            self._sender_label.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT + 1}pt; color: {muted}; font-weight: 700; border: none; background: transparent;"
            )
        if self._reply_author_label is not None:
            self._reply_author_label.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT}pt; font-weight: 700; color: {theme.LINK}; border: none; background: transparent;"
            )
        if self._reply_preview_label is not None:
            self._reply_preview_label.setStyleSheet(
                f"font-size: {theme.BODY_PT}pt; color: {theme.TEXT_SECONDARY}; border: none; background: transparent;"
            )
        if self._reply_wrap is not None:
            self._reply_wrap.setStyleSheet(
                f"background: {theme.BG_INPUT}; border: 1px solid {theme.BORDER_SOFT}; border-radius: 12px;"
            )
        if self._text_label is not None:
            self._text_label.setStyleSheet(
                f"font-size: {theme.BUBBLE_BODY_PT}pt; color: {fg}; border: none; background: transparent; "
                f"line-height: 1.5; padding: 2px 0;"
            )
        for chip in self._attachment_labels:
            chip.setStyleSheet(
                f"font-size: {theme.BODY_PT}pt; color: {fg}; "
                f"padding: 6px 10px; border-radius: 10px; border: 1px solid {theme.BORDER_SOFT}; "
                f"background: {theme.BG_INPUT}; font-weight: 600;"
            )
        if self._time_label is not None:
            self._time_label.setStyleSheet(
                f"font-size: {theme.UI_FONT_PT}pt; color: {muted}; border: none; background: transparent;"
            )

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self._interactive or not self._menu_text:
            event.ignore()
            return
        context = dict(self._message_context)
        if not context.get("preview"):
            context["preview"] = self._menu_text
        self._panel._open_message_context_menu(event.globalPos(), context)
        event.accept()

class TicketFileFieldWidget(QWidget):
    """Single file selector used by dynamic ticket forms."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("Файл не выбран")
        self.choose_button = QPushButton("Выбрать файл")
        self.choose_button.setObjectName("SecondaryButton")
        self.choose_button.clicked.connect(self._choose_file)
        self.clear_button = QPushButton("Убрать")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.clicked.connect(self.clear_file_path)
        layout.addWidget(self.path_input, 1)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.clear_button)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if path:
            self.set_file_path(path)

    def set_file_path(self, path: str) -> None:
        normalized = str(path or "").strip()
        if normalized == self._path:
            return
        self._path = normalized
        self.path_input.setText(normalized)
        self.changed.emit()

    def clear_file_path(self) -> None:
        self.set_file_path("")

    def value(self) -> dict[str, str]:
        if not self._path:
            return {}
        return {"path": self._path, "filename": Path(self._path).name}

    def file_path(self) -> str:
        return self._path


class TicketDynamicFieldsWidget(QWidget):
    """Dynamic form fields driven by the ticket form catalog."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._field_defs: list[dict[str, Any]] = []
        self._containers: dict[str, QWidget] = {}
        self._widgets: dict[str, QWidget] = {}
        self._labels: dict[str, QLabel] = {}
        self._help_labels: dict[str, QLabel] = {}
        self._error_labels: dict[str, QLabel] = {}
        self._registry_options: dict[str, list[dict[str, Any]]] = {}
        self._show_validation_feedback = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def clear_form(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_defs = []
        self._containers = {}
        self._widgets = {}
        self._labels = {}
        self._help_labels = {}
        self._error_labels = {}
        self._registry_options = {}
        self._show_validation_feedback = False

    def set_form(
        self,
        form_def: Optional[dict[str, Any]],
        values: Optional[dict[str, Any]] = None,
        *,
        include_keys: Optional[set[str]] = None,
        exclude_keys: Optional[set[str]] = None,
        registry_options: Optional[dict[str, Any]] = None,
    ) -> None:
        self.clear_form()
        values = values or {}
        self._registry_options = {
            str(key): [item for item in value if isinstance(item, dict)]
            for key, value in (registry_options or {}).items()
            if isinstance(value, list)
        }
        if not isinstance(form_def, dict):
            return
        include_keys = {str(key) for key in include_keys or set()}
        exclude_keys = {str(key) for key in exclude_keys or set()}
        self._field_defs = [
            field
            for field in list(form_def.get("fields") or [])
            if isinstance(field, dict)
            and (not include_keys or str(field.get("key") or "").strip() in include_keys)
            and str(field.get("key") or "").strip() not in exclude_keys
        ]
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key:
                continue
            container = QWidget(self)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)

            field_label_text = str(field_def.get("label") or field_key)
            if field_def.get("required"):
                field_label_text = f"{field_label_text} *"
            field_label = QLabel(field_label_text)
            field_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT + 1}pt; font-weight: 700; color: {theme.TEXT_PRIMARY};")
            container_layout.addWidget(field_label)

            field_type = str(field_def.get("type") or "text").strip().lower()
            widget: QWidget
            if field_type == "textarea":
                input_widget = QTextEdit()
                input_widget.setMinimumHeight(88)
                input_widget.setPlaceholderText(field_def.get("placeholder") or "")
                input_widget.setPlainText(str(values.get(field_key) or ""))
                input_widget.textChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type == "date":
                input_widget = QDateEdit()
                input_widget.setCalendarPopup(True)
                input_widget.setDisplayFormat("yyyy-MM-dd")
                current_date = QDate.fromString(str(values.get(field_key) or "")[:10], "yyyy-MM-dd")
                input_widget.setDate(current_date if current_date.isValid() else QDate.currentDate())
                input_widget.dateChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type == "datetime":
                input_widget = QDateTimeEdit()
                input_widget.setCalendarPopup(True)
                input_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
                raw_datetime = str(values.get(field_key) or "").strip().replace("T", " ")[:16]
                current_datetime = QDateTime.fromString(raw_datetime, "yyyy-MM-dd HH:mm")
                input_widget.setDateTime(current_datetime if current_datetime.isValid() else QDateTime.currentDateTime())
                input_widget.dateTimeChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type in OPTION_FIELD_TYPES:
                input_widget = QComboBox()
                input_widget.addItem("Выберите...", "")
                for option in field_def.get("options") or []:
                    input_widget.addItem(option.get("label") or option.get("value") or "", option.get("value") or "")
                current_index = input_widget.findData(str(values.get(field_key) or ""))
                if current_index >= 0:
                    input_widget.setCurrentIndex(current_index)
                input_widget.currentIndexChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type in PICKER_FIELD_TYPES:
                input_widget = QComboBox()
                input_widget.addItem("Выберите...", "")
                option_key = PICKER_OPTION_KEYS.get(field_type, "")
                options = self._registry_options.get(option_key) or field_def.get("options") or []
                for option in options:
                    option_value = str(
                        option.get("value")
                        or option.get("id")
                        or option.get("person_id")
                        or option.get("department_id")
                        or option.get("location_id")
                        or option.get("device_id")
                        or option.get("service_id")
                        or ""
                    ).strip()
                    option_label = str(
                        option.get("label")
                        or option.get("display_name")
                        or option.get("name")
                        or option.get("hostname")
                        or option_value
                    ).strip()
                    if option_value:
                        input_widget.addItem(option_label, option_value)
                current_value = str(values.get(field_key) or "").strip()
                if current_value and input_widget.findData(current_value) < 0:
                    input_widget.addItem(current_value, current_value)
                current_index = input_widget.findData(current_value)
                if current_index >= 0:
                    input_widget.setCurrentIndex(current_index)
                elif input_widget.count() == 2:
                    input_widget.setCurrentIndex(1)
                input_widget.currentIndexChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type in MULTI_SELECT_FIELD_TYPES:
                input_widget = QListWidget()
                input_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
                current_values = values.get(field_key)
                if isinstance(current_values, list):
                    selected_values = {str(item) for item in current_values}
                else:
                    selected_values = {item.strip() for item in str(current_values or "").split(",") if item.strip()}
                for option in field_def.get("options") or []:
                    option_value = str(option.get("value") or "").strip()
                    item = QListWidgetItem(option.get("label") or option_value)
                    item.setData(Qt.ItemDataRole.UserRole, option_value)
                    input_widget.addItem(item)
                    item.setSelected(option_value in selected_values)
                input_widget.itemSelectionChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type == "checkbox":
                input_widget = QCheckBox(field_def.get("placeholder") or "Подтверждаю")
                input_widget.setChecked(bool(values.get(field_key)))
                input_widget.stateChanged.connect(self._on_any_changed)
                widget = input_widget
            elif field_type == "file":
                input_widget = TicketFileFieldWidget()
                raw_value = values.get(field_key)
                if isinstance(raw_value, dict):
                    input_widget.set_file_path(str(raw_value.get("path") or ""))
                else:
                    input_widget.set_file_path(str(raw_value or ""))
                input_widget.changed.connect(self._on_any_changed)
                widget = input_widget
            else:
                input_widget = QLineEdit()
                input_widget.setPlaceholderText(field_def.get("placeholder") or "")
                input_widget.setText(str(values.get(field_key) or ""))
                input_widget.textChanged.connect(self._on_any_changed)
                widget = input_widget

            container_layout.addWidget(widget)
            help_text = str(field_def.get("help_text") or "").strip()
            if help_text:
                help_label = QLabel(help_text)
                help_label.setWordWrap(True)
                help_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT}pt; color: {theme.TEXT_MUTED};")
                container_layout.addWidget(help_label)
                self._help_labels[field_key] = help_label

            error_label = QLabel("")
            error_label.setWordWrap(True)
            error_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT}pt; color: {theme.DANGER_FG};")
            error_label.setVisible(False)
            container_layout.addWidget(error_label)

            self._containers[field_key] = container
            self._widgets[field_key] = widget
            self._labels[field_key] = field_label
            self._error_labels[field_key] = error_label
            self._layout.addWidget(container)

        self._layout.addStretch(1)
        self._apply_visibility()
        self._apply_validation_state(set())

    def _on_any_changed(self, *_args) -> None:
        self._apply_visibility()
        if self._show_validation_feedback:
            self.validate_required_fields(show_feedback=True)
        self.changed.emit()

    def _field_value(self, field_key: str) -> Any:
        widget = self._widgets.get(field_key)
        if widget is None:
            return ""
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QDateEdit):
            return widget.date().toString("yyyy-MM-dd")
        if isinstance(widget, QDateTimeEdit):
            return widget.dateTime().toString("yyyy-MM-ddTHH:mm")
        if isinstance(widget, QComboBox):
            return str(widget.currentData() or "").strip()
        if isinstance(widget, QListWidget):
            result: list[str] = []
            for item in widget.selectedItems():
                value = item.data(Qt.ItemDataRole.UserRole)
                result.append(str(value if value is not None else item.text()).strip())
            return [item for item in result if item]
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, TicketFileFieldWidget):
            return widget.value()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def values(self, *, visible_only: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {}
        current_values = {field_def.get("key"): self._field_value(str(field_def.get("key") or "")) for field_def in self._field_defs}
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key:
                continue
            if visible_only and not ticket_form_field_visible(field_def, current_values):
                continue
            result[field_key] = current_values.get(field_key)
        return result

    def set_file_field_path(self, field_key: str, path: str) -> None:
        widget = self._widgets.get(str(field_key or "").strip())
        if isinstance(widget, TicketFileFieldWidget):
            widget.set_file_path(path)

    def clear_file_field_path(self, field_key: str) -> None:
        widget = self._widgets.get(str(field_key or "").strip())
        if isinstance(widget, TicketFileFieldWidget):
            widget.clear_file_path()

    def file_attachment_paths(self, *, visible_only: bool = True) -> list[str]:
        paths: list[str] = []
        current_values = {field_def.get("key"): self._field_value(str(field_def.get("key") or "")) for field_def in self._field_defs}
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or str(field_def.get("type") or "").strip().lower() != "file":
                continue
            if visible_only and not ticket_form_field_visible(field_def, current_values):
                continue
            widget = self._widgets.get(field_key)
            if isinstance(widget, TicketFileFieldWidget):
                path = widget.file_path()
                if path:
                    paths.append(path)
        return paths

    def missing_required_labels(self) -> list[str]:
        values = self.values(visible_only=False)
        missing: list[str] = []
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or not field_def.get("required"):
                continue
            if not ticket_form_field_visible(field_def, values):
                continue
            value = values.get(field_key)
            if field_def.get("type") == "checkbox":
                if value is not True:
                    missing.append(str(field_def.get("label") or field_key))
            elif isinstance(value, list):
                if not value:
                    missing.append(str(field_def.get("label") or field_key))
            elif isinstance(value, dict):
                if not str(value.get("path") or value.get("filename") or "").strip():
                    missing.append(str(field_def.get("label") or field_key))
            elif not str(value or "").strip():
                missing.append(str(field_def.get("label") or field_key))
        return missing

    def _missing_required_keys(self) -> set[str]:
        values = self.values(visible_only=False)
        missing: set[str] = set()
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or not field_def.get("required"):
                continue
            if not ticket_form_field_visible(field_def, values):
                continue
            value = values.get(field_key)
            if field_def.get("type") == "checkbox":
                if value is not True:
                    missing.add(field_key)
            elif isinstance(value, list):
                if not value:
                    missing.add(field_key)
            elif isinstance(value, dict):
                if not str(value.get("path") or value.get("filename") or "").strip():
                    missing.add(field_key)
            elif not str(value or "").strip():
                missing.add(field_key)
        return missing

    def clear_validation_feedback(self) -> None:
        self._show_validation_feedback = False
        self._apply_validation_state(set())

    def validate_required_fields(self, *, show_feedback: bool = False) -> list[str]:
        if show_feedback:
            self._show_validation_feedback = True
        missing_keys = self._missing_required_keys()
        self._apply_validation_state(missing_keys if self._show_validation_feedback else set())
        return [
            str(field_def.get("label") or field_def.get("key") or "")
            for field_def in self._field_defs
            if str(field_def.get("key") or "").strip() in missing_keys
        ]

    def _apply_validation_state(self, missing_keys: set[str]) -> None:
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            label = self._labels.get(field_key)
            help_label = self._help_labels.get(field_key)
            error_label = self._error_labels.get(field_key)
            widget = self._widgets.get(field_key)
            is_missing = field_key in missing_keys
            if label is not None:
                label.setStyleSheet(
                    f"font-size: {theme.UI_FONT_PT + 1}pt; font-weight: 700; "
                    f"color: {theme.DANGER_FG if is_missing else theme.TEXT_PRIMARY};"
                )
            if help_label is not None:
                help_label.setStyleSheet(
                    f"font-size: {theme.UI_FONT_PT}pt; color: {theme.DANGER_FG if is_missing else theme.TEXT_MUTED};"
                )
            if error_label is not None:
                if is_missing:
                    error_text = str(
                        field_def.get("required_message")
                        or f"Заполните поле «{field_def.get('label') or field_key}»."
                    ).strip()
                    error_label.setText(error_text)
                    error_label.setVisible(True)
                else:
                    error_label.setText("")
                    error_label.setVisible(False)
            if widget is not None:
                if is_missing:
                    widget.setStyleSheet(
                        f"border: 1px solid {theme.DANGER_BORDER}; border-radius: 14px; "
                        f"background: {theme.DANGER_BG}; color: {theme.TEXT_PRIMARY};"
                    )
                else:
                    widget.setStyleSheet("")

    def _apply_visibility(self) -> None:
        values = self.values(visible_only=False)
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            container = self._containers.get(field_key)
            if container is not None:
                container.setVisible(ticket_form_field_visible(field_def, values))


class TicketCreateDialog(QDialog):
    """Modal dialog for ticket creation."""

    def __init__(self, panel: "ChatPanel"):
        super().__init__(panel)
        self.panel = panel

        self.setWindowTitle("Создать обращение")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        profile_group = QGroupBox("Профиль инициатора")
        profile_layout = QVBoxLayout(profile_group)
        self.profile_selector = QComboBox()
        self.profile_selector.currentIndexChanged.connect(self._on_profile_changed)
        profile_layout.addWidget(self.profile_selector)

        self.profile_summary = QLabel("")
        self.profile_summary.setWordWrap(True)
        profile_layout.addWidget(self.profile_summary)

        profile_buttons = QHBoxLayout()
        self.manage_profiles_btn = QPushButton("Профили")
        self.manage_profiles_btn.clicked.connect(self._on_manage_profiles)
        profile_buttons.addWidget(self.manage_profiles_btn)
        profile_buttons.addStretch(1)
        profile_layout.addLayout(profile_buttons)
        layout.addWidget(profile_group)

        forms_group = QGroupBox("Шаблон обращения")
        forms_layout = QVBoxLayout(forms_group)
        self.form_selector = QComboBox()
        self.form_selector.currentIndexChanged.connect(self._on_form_changed)
        forms_layout.addWidget(self.form_selector)
        self.form_summary = QLabel("")
        self.form_summary.setWordWrap(True)
        forms_layout.addWidget(self.form_summary)
        self.dynamic_fields_widget = TicketDynamicFieldsWidget(self)
        self.dynamic_fields_widget.changed.connect(self._on_form_fields_changed)
        forms_layout.addWidget(self.dynamic_fields_widget)
        layout.addWidget(forms_group)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Опишите проблему для службы поддержки")
        self.description_input.setMinimumHeight(140)
        layout.addWidget(self.description_input)

        priority_form = QFormLayout()
        self.impact_scope_select = QComboBox()
        self.impact_scope_select.addItem("Только я", "single_user")
        self.impact_scope_select.addItem("Несколько человек", "group")
        self.impact_scope_select.addItem("Весь отдел", "department")
        self.impact_scope_select.addItem("Здание / организация / критичная система", "building_or_org")
        self.impact_scope_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.work_continuity_select = QComboBox()
        self.work_continuity_select.addItem("Есть обходной путь", "workaround_available")
        self.work_continuity_select.addItem("Можно работать частично", "partial_work")
        self.work_continuity_select.addItem("Работа остановлена, обходного пути нет", "work_stopped_no_workaround")
        self.work_continuity_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.business_importance_select = QComboBox()
        self.business_importance_select.addItem("Обычная рабочая ситуация", "normal")
        self.business_importance_select.addItem("Есть важный срок", "deadline")
        self.business_importance_select.addItem("Сегодня / завтра крайний срок", "deadline_today")
        self.business_importance_select.addItem("ИБ / публичная услуга / критичный процесс", "security")
        self.business_importance_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.urgency_reason_input = QLineEdit()
        self.urgency_reason_input.setPlaceholderText("Что именно остановлено или затруднено")
        self.importance_reason_input = QLineEdit()
        self.importance_reason_input.setPlaceholderText("Срок, критичный процесс или регламент")
        priority_form.addRow("Кого затронуло", self.impact_scope_select)
        priority_form.addRow("Можно ли работать", self.work_continuity_select)
        priority_form.addRow("Важность процесса", self.business_importance_select)
        priority_form.addRow("Факт срочности", self.urgency_reason_input)
        priority_form.addRow("Факт важности", self.importance_reason_input)
        layout.addLayout(priority_form)
        self.priority_dynamic_fields_widget = TicketDynamicFieldsWidget(self)
        self.priority_dynamic_fields_widget.changed.connect(self._on_form_fields_changed)
        layout.addWidget(self.priority_dynamic_fields_widget)
        self.diagnostic_consent_checkbox = QCheckBox(
            "Разрешаю выполнить диагностику моего устройства для этого обращения"
        )
        self.diagnostic_consent_checkbox.setVisible(False)
        layout.addWidget(self.diagnostic_consent_checkbox)

        buttons = QHBoxLayout()
        self.create_btn = QPushButton("Создать")
        self.create_btn.clicked.connect(self._on_accept)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        self.create_btn.setObjectName("PrimaryButton")
        self.cancel_btn.setObjectName("SecondaryButton")
        buttons.addWidget(self.create_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.manage_profiles_btn.setObjectName("SecondaryButton")
        theme.apply_agent_dialog_theme(self)
        self._refresh_profiles()
        self._refresh_forms()

    def _refresh_profiles(self) -> None:
        active_id = self.panel._profiles_data.get("active_profile_id")
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        for profile in self.panel._profiles():
            title = profile.get("display_name") or profile.get("full_name") or "Без имени"
            self.profile_selector.addItem(title, profile.get("id"))

        if self.profile_selector.count() > 0:
            if active_id:
                idx = self.profile_selector.findData(active_id)
                self.profile_selector.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                self.profile_selector.setCurrentIndex(0)

        self.profile_selector.blockSignals(False)
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _on_profile_changed(self, *_args) -> None:
        profile_id = self.profile_selector.currentData()
        self.panel._profiles_data["active_profile_id"] = profile_id
        self.panel._save_profiles()
        self.profile_summary.setText(self.panel.current_requester_profile_summary())

    def _refresh_forms(self) -> None:
        form_pack = self.panel.ticket_form_pack()
        forms = list(form_pack.get("forms") or [])
        current_key = self.form_selector.currentData()
        self.form_selector.blockSignals(True)
        self.form_selector.clear()
        for form in forms:
            self.form_selector.addItem(form.get("title") or form.get("key") or "Форма", form.get("key"))
        if self.form_selector.count() > 0:
            index = self.form_selector.findData(current_key)
            self.form_selector.setCurrentIndex(index if index >= 0 else 0)
        self.form_selector.blockSignals(False)
        self._on_form_changed()

    def _selected_form(self) -> Optional[dict[str, Any]]:
        form_key = self.form_selector.currentData()
        for form in self.panel.ticket_form_pack().get("forms") or []:
            if form.get("key") == form_key:
                return form
        forms = self.panel.ticket_form_pack().get("forms") or []
        return forms[0] if forms else None

    def _on_form_changed(self, *_args) -> None:
        form = self._selected_form()
        if not form:
            self.form_summary.setText("Каталог форм не загружен.")
            self.dynamic_fields_widget.clear_form()
            self.priority_dynamic_fields_widget.clear_form()
            return
        self.form_summary.setText(form.get("description") or "Уточните детали обращения, чтобы оно сразу попало в нужный поток.")
        priority_keys = set(ticket_form_priority_field_keys(form))
        registry_options = self.panel.registry_options()
        self.dynamic_fields_widget.set_form(form, exclude_keys=priority_keys, registry_options=registry_options)
        self.priority_dynamic_fields_widget.set_form(form, include_keys=priority_keys, registry_options=registry_options)
        self.priority_dynamic_fields_widget.setVisible(bool(priority_keys))
        consent_required = diagnostic_consent_required(form)
        self.diagnostic_consent_checkbox.setVisible(consent_required)
        self.diagnostic_consent_checkbox.setChecked(False)

    def _on_form_fields_changed(self) -> None:
        self.form_summary.setText((self._selected_form() or {}).get("description") or "")

    def _on_manage_profiles(self) -> None:
        self.panel.open_profile_manager()
        self._refresh_profiles()

    def _on_accept(self) -> None:
        if not self.panel.has_active_profile():
            QMessageBox.warning(self, "Профиль обязателен", "Выберите профиль инициатора.")
            return
        if not self.description_input.toPlainText().strip():
            QMessageBox.warning(self, "Ошибка", "Опишите проблему")
            return
        missing_fields = self.dynamic_fields_widget.missing_required_labels()
        missing_fields.extend(self.priority_dynamic_fields_widget.missing_required_labels())
        if missing_fields:
            QMessageBox.warning(
                self,
                "Не хватает данных",
                "Заполните обязательные поля: " + ", ".join(missing_fields),
            )
            return
        self.accept()

    def payload(self) -> dict:
        description = self.description_input.toPlainText().strip()
        priority_facts = build_priority_facts_payload(
            impact_scope=str(self.impact_scope_select.currentData() or "single_user"),
            work_continuity=str(self.work_continuity_select.currentData() or "workaround_available"),
            business_importance=str(self.business_importance_select.currentData() or "normal"),
            urgency_reason=self.urgency_reason_input.text().strip(),
            importance_reason=self.importance_reason_input.text().strip(),
        )
        form_pack = self.panel.ticket_form_pack()
        selected_form = self._selected_form() or {}
        form_payload = self.dynamic_fields_widget.values()
        form_payload.update(self.priority_dynamic_fields_widget.values())
        attachment_paths = [
            *self.dynamic_fields_widget.file_attachment_paths(),
            *self.priority_dynamic_fields_widget.file_attachment_paths(),
        ]
        priority_facts = build_priority_facts_payload_from_form(
            selected_form,
            form_payload,
            fallback=priority_facts,
        )
        for key, value in (priority_facts.get("form_payload") or {}).items():
            form_payload.setdefault(key, value)
        consent_payload = build_diagnostic_consent_payload(
            selected_form,
            granted=self.diagnostic_consent_checkbox.isChecked(),
        )
        payload = {
            "title": f"Обращение: {selected_form.get('request_template_title') or selected_form.get('title') or 'служба поддержки'}",
            "description": description,
            "urgency": priority_facts["urgency"],
            "importance": priority_facts["importance"],
            "urgency_reason": priority_facts["urgency_reason"],
            "importance_reason": priority_facts["importance_reason"],
            "form_key": selected_form.get("key"),
            "request_template_key": selected_form.get("request_template_key") or selected_form.get("key"),
            "form_pack_key": form_pack.get("pack_key"),
            "form_pack_version": form_pack.get("version"),
            "form_payload": form_payload,
            "ticket_type": selected_form.get("ticket_type") or selected_form.get("request_kind") or selected_form.get("key") or "request",
            "attachment_paths": list(dict.fromkeys(attachment_paths)),
        }
        if consent_payload is not None:
            payload["diagnostic_consent"] = consent_payload
        return payload


class TicketCreateWizardWidget(QFrame):
    """Embedded step-by-step ticket creation flow for the main window."""

    ticketCreated = Signal(str)
    cancelled = Signal()

    def __init__(self, panel: "ChatPanel", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._loading_profile_combo = False
        self._current_step = 0
        self._submitting = False
        self._capture_in_progress = False
        self._status_is_error = False
        self._server_creation_preview: dict[str, Any] | None = None
        self._preview_request_seq = 0
        self._attachment_paths: list[str] = []
        self._temporary_attachment_paths: set[str] = set()
        self._last_created_ticket_id = ""
        self.setObjectName("ProfileSidebar")
        self.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        title = QLabel("Создание обращения")
        title.setObjectName("ProfileSidebarTitle")
        outer.addWidget(title)

        self._subtitle = QLabel(
            "Заявка создаётся по шагам. Следующий этап откроется только после заполнения предыдущего."
        )
        self._subtitle.setObjectName("ProfileHint")
        self._subtitle.setWordWrap(True)
        outer.addWidget(self._subtitle)

        step_row = QHBoxLayout()
        step_row.setSpacing(8)
        self._step_buttons: list[QPushButton] = []
        for index, label in enumerate(("1. Профиль", "2. Тип", "3. Описание", "4. Приоритет")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("SecondaryButton")
            btn.clicked.connect(lambda _checked=False, step=index: self._go_to_step(step))
            step_row.addWidget(btn)
            self._step_buttons.append(btn)
        outer.addLayout(step_row)

        self._step_caption = QLabel("")
        self._step_caption.setObjectName("ProfileHint")
        outer.addWidget(self._step_caption)

        self._stack = QStackedWidget()
        self._stack.setObjectName("TicketCreateWizardStack")
        outer.addWidget(self._stack, 1)

        self._build_profile_step()
        self._build_form_step()
        self._build_description_step()
        self._build_priority_step()

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.setObjectName("SecondaryButton")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._back_btn = QPushButton("Назад")
        self._back_btn.setObjectName("SecondaryButton")
        self._back_btn.clicked.connect(self._on_back_clicked)
        self._next_btn = QPushButton("Далее")
        self._next_btn.setObjectName("PrimaryButton")
        self._next_btn.clicked.connect(self._on_next_clicked)
        self._submit_btn = QPushButton("Создать обращение")
        self._submit_btn.setObjectName("PrimaryButton")
        self._submit_btn.clicked.connect(self._on_submit_clicked)
        footer.addWidget(self._cancel_btn)
        footer.addStretch(1)
        footer.addWidget(self._back_btn)
        footer.addWidget(self._next_btn)
        footer.addWidget(self._submit_btn)
        outer.addLayout(footer)

        self._status_label = QLabel("")
        self._status_label.setObjectName("ProfileHint")
        self._status_label.setWordWrap(True)
        outer.addWidget(self._status_label)

        self.result_group = QGroupBox("Обращение создано")
        result_layout = QVBoxLayout(self.result_group)
        result_layout.setContentsMargins(10, 10, 10, 10)
        result_layout.setSpacing(8)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("ProfileHint")
        self.access_code_label = QLabel("")
        self.access_code_label.setWordWrap(True)
        self.access_code_label.setObjectName("ProfileHint")
        self.next_action_label = QLabel("")
        self.next_action_label.setWordWrap(True)
        self.next_action_label.setObjectName("ProfileHint")
        self.deadline_label = QLabel("")
        self.deadline_label.setWordWrap(True)
        self.deadline_label.setObjectName("ProfileHint")
        result_layout.addWidget(self.access_code_label)
        result_layout.addWidget(self.next_action_label)
        result_layout.addWidget(self.deadline_label)
        result_layout.addWidget(self.result_label)
        result_actions = QHBoxLayout()
        self.open_created_ticket_btn = QPushButton("Открыть обращение")
        self.open_created_ticket_btn.setObjectName("PrimaryButton")
        self.open_created_ticket_btn.clicked.connect(self._on_open_created_ticket)
        self.add_message_to_created_ticket_btn = QPushButton("Добавить сообщение")
        self.add_message_to_created_ticket_btn.setObjectName("SecondaryButton")
        self.add_message_to_created_ticket_btn.clicked.connect(self._on_add_message_to_created_ticket)
        self.create_another_btn = QPushButton("Создать ещё одно")
        self.create_another_btn.setObjectName("SecondaryButton")
        self.create_another_btn.clicked.connect(self._on_create_another_clicked)
        result_actions.addWidget(self.open_created_ticket_btn)
        result_actions.addWidget(self.add_message_to_created_ticket_btn)
        result_actions.addWidget(self.create_another_btn)
        result_actions.addStretch(1)
        result_layout.addLayout(result_actions)
        self.result_group.setVisible(False)
        outer.addWidget(self.result_group)

        self.refresh_from_panel()
        self.reset_wizard()

    def _build_profile_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        group = QGroupBox("Шаг 1. Профиль инициатора")
        group_layout = QVBoxLayout(group)
        self.profile_selector = QComboBox()
        self.profile_selector.currentIndexChanged.connect(self._on_profile_changed)
        group_layout.addWidget(self.profile_selector)

        self.profile_summary = QLabel("")
        self.profile_summary.setWordWrap(True)
        group_layout.addWidget(self.profile_summary)

        self.manage_profiles_btn = QPushButton("Изменить / создать профиль")
        self.manage_profiles_btn.setObjectName("SecondaryButton")
        self.manage_profiles_btn.clicked.connect(self._on_manage_profiles)
        group_layout.addWidget(self.manage_profiles_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(group)
        layout.addStretch(1)
        self._stack.addWidget(page)

    def _build_form_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        group = QGroupBox("Шаг 2. Шаблон обращения и уточнения")
        group_layout = QVBoxLayout(group)
        self.template_search_input = QLineEdit()
        self.template_search_input.setPlaceholderText("Поиск по шаблонам")
        self.template_search_input.textChanged.connect(self._refresh_template_list)
        group_layout.addWidget(self.template_search_input)

        self.template_list = QListWidget()
        self.template_list.setMinimumHeight(132)
        self.template_list.currentItemChanged.connect(self._on_template_item_changed)
        group_layout.addWidget(self.template_list)

        self.selected_template_card = QLabel("Выберите шаблон обращения.")
        self.selected_template_card.setWordWrap(True)
        self.selected_template_card.setObjectName("ProfileHint")
        group_layout.addWidget(self.selected_template_card)

        self.form_selector = QComboBox()
        self.form_selector.currentIndexChanged.connect(self._on_form_changed)
        self.form_selector.setVisible(False)
        group_layout.addWidget(self.form_selector)
        self.form_summary = QLabel("")
        self.form_summary.setWordWrap(True)
        group_layout.addWidget(self.form_summary)
        self.dynamic_fields_widget = TicketDynamicFieldsWidget(self)
        self.dynamic_fields_widget.changed.connect(self._on_form_fields_changed)
        group_layout.addWidget(self.dynamic_fields_widget)
        layout.addWidget(group)
        layout.addStretch(1)
        self._stack.addWidget(page)

    def _build_description_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        description_group = QGroupBox("Шаг 3. Описание и материалы")
        description_layout = QVBoxLayout(description_group)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Опишите проблему для службы поддержки")
        self.description_input.setMinimumHeight(180)
        self.description_input.textChanged.connect(self._update_navigation_state)
        description_layout.addWidget(self.description_input)

        attachments_hint = QLabel(
            "При необходимости сразу приложите скриншот или видео. После создания обращения они уйдут первым сообщением."
        )
        attachments_hint.setWordWrap(True)
        attachments_hint.setObjectName("ProfileHint")
        description_layout.addWidget(attachments_hint)

        attachments_actions = QHBoxLayout()
        self.add_screenshot_btn = QPushButton("Сделать скриншот")
        self.add_screenshot_btn.setObjectName("SecondaryButton")
        self.add_screenshot_btn.clicked.connect(self._on_add_screenshot)
        self.add_video_btn = QPushButton("Записать видео")
        self.add_video_btn.setObjectName("SecondaryButton")
        self.add_video_btn.clicked.connect(self._on_add_video)
        self.add_file_btn = QPushButton("Добавить файл")
        self.add_file_btn.setObjectName("SecondaryButton")
        self.add_file_btn.clicked.connect(self._on_add_file)
        self.remove_attachment_btn = QPushButton("Удалить выбранное")
        self.remove_attachment_btn.setObjectName("SecondaryButton")
        self.remove_attachment_btn.clicked.connect(self._on_remove_selected_attachment)
        attachments_actions.addWidget(self.add_screenshot_btn)
        attachments_actions.addWidget(self.add_video_btn)
        attachments_actions.addWidget(self.add_file_btn)
        attachments_actions.addWidget(self.remove_attachment_btn)
        attachments_actions.addStretch(1)
        description_layout.addLayout(attachments_actions)

        self.attachments_list = QListWidget()
        self.attachments_list.setMinimumHeight(120)
        description_layout.addWidget(self.attachments_list)

        layout.addWidget(description_group)
        layout.addStretch(1)
        self._stack.addWidget(page)

    def _build_priority_step(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        group = QGroupBox("Шаг 4. Влияние, срочность и важность")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.impact_scope_select = QComboBox()
        self.impact_scope_select.addItem("Только я", "single_user")
        self.impact_scope_select.addItem("Несколько человек", "group")
        self.impact_scope_select.addItem("Весь отдел", "department")
        self.impact_scope_select.addItem("Здание / организация / критичная система", "building_or_org")
        self.impact_scope_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.work_continuity_select = QComboBox()
        self.work_continuity_select.addItem("Есть обходной путь", "workaround_available")
        self.work_continuity_select.addItem("Можно работать частично", "partial_work")
        self.work_continuity_select.addItem("Работа остановлена, обходного пути нет", "work_stopped_no_workaround")
        self.work_continuity_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.business_importance_select = QComboBox()
        self.business_importance_select.addItem("Обычная рабочая ситуация", "normal")
        self.business_importance_select.addItem("Есть важный срок", "deadline")
        self.business_importance_select.addItem("Сегодня / завтра крайний срок", "deadline_today")
        self.business_importance_select.addItem("ИБ / публичная услуга / критичный процесс", "security")
        self.business_importance_select.currentIndexChanged.connect(self._on_form_fields_changed)
        self.urgency_reason_input = QLineEdit()
        self.urgency_reason_input.setPlaceholderText("Что именно остановлено или затруднено")
        self.importance_reason_input = QLineEdit()
        self.importance_reason_input.setPlaceholderText("Срок, критичный процесс или регламент")
        form.addRow("Кого затронуло", self.impact_scope_select)
        form.addRow("Можно ли работать", self.work_continuity_select)
        form.addRow("Важность процесса", self.business_importance_select)
        form.addRow("Факт срочности", self.urgency_reason_input)
        form.addRow("Факт важности", self.importance_reason_input)
        layout.addWidget(group)
        self.priority_fallback_group = group
        self.priority_dynamic_fields_widget = TicketDynamicFieldsWidget(self)
        self.priority_dynamic_fields_widget.changed.connect(self._on_form_fields_changed)
        layout.addWidget(self.priority_dynamic_fields_widget)
        self.diagnostic_consent_checkbox = QCheckBox(
            "Разрешаю выполнить диагностику моего устройства для этого обращения"
        )
        self.diagnostic_consent_checkbox.stateChanged.connect(self._update_navigation_state)
        layout.addWidget(self.diagnostic_consent_checkbox)

        summary = QLabel(
            "После подтверждения обращение создастся с выбранным профилем, шаблоном, описанием и материалами."
        )
        summary.setWordWrap(True)
        summary.setObjectName("ProfileHint")
        process_preview_group = QGroupBox("Что будет после отправки")
        process_preview_layout = QVBoxLayout(process_preview_group)
        process_preview_layout.setContentsMargins(10, 10, 10, 10)
        process_preview_layout.setSpacing(6)
        summary.setText("Проверьте маршрут, сроки, согласование и диагностику до создания обращения.")
        process_preview_layout.addWidget(summary)
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setObjectName("ProfileHint")
        process_preview_layout.addWidget(self.preview_label)
        self.preview_warning_label = QLabel("")
        self.preview_warning_label.setWordWrap(True)
        self.preview_warning_label.setObjectName("ProfileHint")
        self.preview_warning_label.setStyleSheet("color: #a16207; background: transparent;")
        self.preview_warning_label.setVisible(False)
        process_preview_layout.addWidget(self.preview_warning_label)
        layout.addWidget(process_preview_group)
        layout.addStretch(1)
        self._stack.addWidget(page)

    async def async_prepare(self) -> None:
        self._set_status("Загружаю шаблоны обращений...", error=False)
        try:
            await self._panel._async_refresh_ticket_form_pack()
            self.refresh_from_panel()
            self.reset_wizard()
            self._set_status("Форма готова. Начните с выбора профиля.", error=False)
        except Exception as exc:
            logger.error(f"Ошибка подготовки мастера создания тикета: {exc}")
            self._set_status(f"Не удалось подготовить форму: {exc}", error=True)

    def refresh_from_panel(self) -> None:
        self._refresh_profiles()
        self._refresh_forms()
        self._sync_attachments_list()
        self._update_navigation_state()
        self._update_creation_preview()

    def reset_wizard(self) -> None:
        self._current_step = 0
        self.description_input.clear()
        self.impact_scope_select.setCurrentIndex(0)
        self.work_continuity_select.setCurrentIndex(0)
        self.business_importance_select.setCurrentIndex(0)
        self.urgency_reason_input.clear()
        self.importance_reason_input.clear()
        self.dynamic_fields_widget.clear_validation_feedback()
        self.priority_dynamic_fields_widget.clear_validation_feedback()
        self._cleanup_temporary_attachments()
        self._attachment_paths.clear()
        self._sync_attachments_list()
        self._go_to_step(0, force=True)
        self._set_status("", error=False)
        self._hide_create_result()

    def _set_status(self, text: str, *, error: bool) -> None:
        self._status_is_error = error
        color = theme.DANGER_FG if error else theme.TEXT_MUTED
        self._status_label.setStyleSheet(f"color: {color}; background: transparent;")
        self._status_label.setText(text)

    def _hide_create_result(self) -> None:
        self._last_created_ticket_id = ""
        self.result_label.setText("")
        self.access_code_label.setText("")
        self.next_action_label.setText("")
        self.deadline_label.setText("")
        self.result_group.setVisible(False)

    def _show_create_result(self, ticket: dict[str, Any], *, public_access_code: str = "") -> None:
        self._last_created_ticket_id = str(ticket.get("ticket_id") or "")
        code = str(public_access_code or ticket.get("public_access_code") or "").strip()
        self.access_code_label.setText(f"Код доступа: {code}" if code and code != "—" else "")
        next_owner = str(ticket.get("next_action_owner") or "").strip().lower()
        if next_owner in {"support", "assignee", "queue"}:
            next_action_text = "Что дальше: сейчас работает поддержка."
        elif next_owner in {"requester", "user"}:
            next_action_text = "Что дальше: сейчас нужен ваш ответ."
        elif next_owner in {"approval", "approver"}:
            next_action_text = "Что дальше: сейчас ожидается согласование."
        else:
            next_action_text = "Что дальше: следующий шаг появится в обращении."
        self.next_action_label.setText(next_action_text)
        deadline_parts: list[str] = []
        first_response_due = _format_user_deadline(ticket.get("first_response_due_at"))
        resolution_due = _format_user_deadline(ticket.get("resolution_due_at"))
        if first_response_due:
            deadline_parts.append(f"Вам должны ответить до {first_response_due}.")
        if resolution_due:
            deadline_parts.append(f"Решение или обходной вариант ожидается до {resolution_due}.")
        self.deadline_label.setText(" ".join(deadline_parts) if deadline_parts else "Сроки покажутся в обращении после расчёта сервером.")
        self.result_label.setText(build_post_create_process_summary(ticket, public_access_code=public_access_code))
        has_ticket = bool(self._last_created_ticket_id)
        self.open_created_ticket_btn.setEnabled(has_ticket)
        self.add_message_to_created_ticket_btn.setEnabled(has_ticket)
        self.result_group.setVisible(True)

    def _on_open_created_ticket(self) -> None:
        if self._last_created_ticket_id:
            self.ticketCreated.emit(self._last_created_ticket_id)

    def _on_add_message_to_created_ticket(self) -> None:
        if self._last_created_ticket_id:
            self.ticketCreated.emit(self._last_created_ticket_id)

    def _on_create_another_clicked(self) -> None:
        self.reset_wizard()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())
        self._set_status(self._status_label.text(), error=self._status_is_error)
        self.dynamic_fields_widget.validate_required_fields(
            show_feedback=self.dynamic_fields_widget._show_validation_feedback
        )

    def _refresh_profiles(self) -> None:
        active_id = self._panel._profiles_data.get("active_profile_id")
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        for profile in self._panel._profiles():
            title = profile.get("display_name") or profile.get("full_name") or "Без имени"
            self.profile_selector.addItem(title, profile.get("id"))
        if self.profile_selector.count() > 0:
            idx = self.profile_selector.findData(active_id) if active_id else 0
            self.profile_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self.profile_selector.blockSignals(False)
        self.profile_summary.setText(self._panel.current_requester_profile_summary() or "Профиль не выбран.")

    def _on_profile_changed(self, *_args) -> None:
        if self._loading_profile_combo:
            return
        profile_id = self.profile_selector.currentData()
        self._panel._profiles_data["active_profile_id"] = profile_id
        self._panel._save_profiles()
        self.profile_summary.setText(self._panel.current_requester_profile_summary() or "Профиль не выбран.")
        self._update_navigation_state()
        self._update_creation_preview()

    def _current_priority_class_hint(self) -> str:
        priority_facts = build_priority_facts_payload(
            impact_scope=str(self.impact_scope_select.currentData() or "single_user"),
            work_continuity=str(self.work_continuity_select.currentData() or "workaround_available"),
            business_importance=str(self.business_importance_select.currentData() or "normal"),
        )
        if priority_facts["urgency"] and priority_facts["importance"]:
            return "P1"
        if priority_facts["urgency"] or priority_facts["importance"]:
            return "P2"
        return "P3"

    def _update_creation_preview(self) -> None:
        if hasattr(self, "preview_label"):
            self.preview_label.setText(
                build_request_creation_preview(
                    self._selected_form(),
                    priority_class=self._current_priority_class_hint(),
                    server_preview=self._server_creation_preview,
                )
            )

    def _schedule_server_creation_preview(self) -> None:
        self._preview_request_seq += 1
        self._server_creation_preview = None
        if hasattr(self, "preview_warning_label"):
            self.preview_warning_label.setText("")
            self.preview_warning_label.setVisible(False)
        self._update_creation_preview()
        if not self._selected_form() or not getattr(self._panel, "ticket_client", None):
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.create_task(self._async_refresh_server_creation_preview(self._preview_request_seq))

    async def _async_refresh_server_creation_preview(self, request_seq: int) -> None:
        try:
            payload = self._payload()
            result = await self._panel.ticket_client.preview_ticket_create(
                form_key=payload.get("form_key"),
                request_template_key=payload.get("request_template_key"),
                form_pack_key=payload.get("form_pack_key"),
                form_pack_version=payload.get("form_pack_version"),
                form_payload=payload.get("form_payload") if isinstance(payload.get("form_payload"), dict) else {},
                ticket_type=payload.get("ticket_type"),
            )
        except Exception as exc:
            logger.debug(f"Предпросмотр создания обращения недоступен: {exc}")
            if request_seq == self._preview_request_seq and hasattr(self, "preview_warning_label"):
                self.preview_warning_label.setText(
                    "Предпросмотр сервера временно недоступен. Можно продолжить: очередь и сроки будут рассчитаны при создании."
                )
                self.preview_warning_label.setVisible(True)
            return
        if request_seq != self._preview_request_seq:
            return
        if isinstance(result, dict):
            self._server_creation_preview = result.get("preview") if isinstance(result.get("preview"), dict) else result
            if hasattr(self, "preview_warning_label"):
                self.preview_warning_label.setText("")
                self.preview_warning_label.setVisible(False)
            self._update_creation_preview()

    def _refresh_forms(self) -> None:
        form_pack = self._panel.ticket_form_pack()
        forms = list(form_pack.get("forms") or [])
        current_key = self.form_selector.currentData()
        self.form_selector.blockSignals(True)
        self.form_selector.clear()
        for form in forms:
            self.form_selector.addItem(form.get("title") or form.get("key") or "Форма", form.get("key"))
        if self.form_selector.count() > 0:
            index = self.form_selector.findData(current_key)
            self.form_selector.setCurrentIndex(index if index >= 0 else 0)
        self.form_selector.blockSignals(False)
        self._refresh_template_list()
        self._on_form_changed()

    def _selected_form(self) -> Optional[dict[str, Any]]:
        form_key = self.form_selector.currentData()
        for form in self._panel.ticket_form_pack().get("forms") or []:
            if form.get("key") == form_key:
                return form
        forms = self._panel.ticket_form_pack().get("forms") or []
        return forms[0] if forms else None

    def _refresh_template_list(self, *_args) -> None:
        if not hasattr(self, "template_list"):
            return
        forms = list(self._panel.ticket_form_pack().get("forms") or [])
        current_key = str(self.form_selector.currentData() or "").strip()
        query = str(self.template_search_input.text() if hasattr(self, "template_search_input") else "").strip().casefold()
        self.template_list.blockSignals(True)
        self.template_list.clear()
        for form in forms:
            title = str(form.get("request_template_title") or form.get("title") or form.get("key") or "Форма").strip()
            search_blob = " ".join(
                str(form.get(key) or "") for key in ("key", "request_template_title", "title", "description", "category", "ticket_type")
            ).casefold()
            if query and query not in search_blob:
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, form.get("key"))
            item.setToolTip(build_request_template_card_summary(form, priority_class=self._current_priority_class_hint()))
            self.template_list.addItem(item)
        selected_row = 0
        for row in range(self.template_list.count()):
            item = self.template_list.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == current_key:
                selected_row = row
                break
        if self.template_list.count() > 0:
            self.template_list.setCurrentRow(selected_row)
        self.template_list.blockSignals(False)

    def _sync_template_list_selection(self, form_key: Any) -> None:
        if not hasattr(self, "template_list"):
            return
        target = str(form_key or "").strip()
        self.template_list.blockSignals(True)
        for row in range(self.template_list.count()):
            item = self.template_list.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == target:
                self.template_list.setCurrentRow(row)
                break
        self.template_list.blockSignals(False)

    def _on_template_item_changed(self, current: Optional[QListWidgetItem], _previous: Optional[QListWidgetItem] = None) -> None:
        if current is None:
            return
        form_key = current.data(Qt.ItemDataRole.UserRole)
        index = self.form_selector.findData(form_key)
        if index >= 0 and index != self.form_selector.currentIndex():
            self.form_selector.setCurrentIndex(index)

    def _on_form_changed(self, *_args) -> None:
        form = self._selected_form()
        if not form:
            self.form_summary.setText("Каталог форм пока недоступен.")
            if hasattr(self, "selected_template_card"):
                self.selected_template_card.setText("Каталог шаблонов пока недоступен.")
            self.dynamic_fields_widget.clear_form()
            self.priority_dynamic_fields_widget.clear_form()
            self.priority_fallback_group.setVisible(True)
        else:
            self._sync_template_list_selection(form.get("key"))
            self.form_summary.setText(
                form.get("description") or "Уточните детали, чтобы обращение сразу попало в нужный поток."
            )
            if hasattr(self, "selected_template_card"):
                self.selected_template_card.setText(
                    build_request_template_card_summary(form, priority_class=self._current_priority_class_hint())
                )
            priority_keys = set(ticket_form_priority_field_keys(form))
            registry_options = self._panel.registry_options()
            self.dynamic_fields_widget.set_form(form, exclude_keys=priority_keys, registry_options=registry_options)
            self.priority_dynamic_fields_widget.set_form(form, include_keys=priority_keys, registry_options=registry_options)
            self.priority_dynamic_fields_widget.setVisible(bool(priority_keys))
            self.priority_fallback_group.setVisible(not bool(priority_keys))
            consent_required = diagnostic_consent_required(form)
            self.diagnostic_consent_checkbox.setVisible(consent_required)
            self.diagnostic_consent_checkbox.setChecked(False)
        self._update_navigation_state()
        self._update_creation_preview()
        self._schedule_server_creation_preview()

    def _on_form_fields_changed(self) -> None:
        self.dynamic_fields_widget.validate_required_fields(show_feedback=False)
        self.priority_dynamic_fields_widget.validate_required_fields(show_feedback=False)
        self._update_navigation_state()
        self._update_creation_preview()
        self._schedule_server_creation_preview()

    def _on_manage_profiles(self) -> None:
        self._panel.open_profile_manager(start_new=True)
        self.refresh_from_panel()

    def _sync_attachments_list(self) -> None:
        self.attachments_list.clear()
        for file_path in self._attachment_paths:
            item = QListWidgetItem(format_attachment_item_label(file_path))
            item.setToolTip(file_path)
            self.attachments_list.addItem(item)
        self.remove_attachment_btn.setEnabled(self.attachments_list.count() > 0)
        self._set_media_controls_enabled(not self._submitting and not self._capture_in_progress)

    def _set_media_controls_enabled(self, enabled: bool) -> None:
        self.add_screenshot_btn.setEnabled(enabled)
        self.add_video_btn.setEnabled(enabled)
        self.add_file_btn.setEnabled(enabled)
        self.remove_attachment_btn.setEnabled(enabled and self.attachments_list.count() > 0)

    def _cleanup_temporary_attachments(self) -> None:
        for file_path in list(self._temporary_attachment_paths):
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                logger.debug(f"Не удалось удалить временное вложение: {file_path}")
            self._temporary_attachment_paths.discard(file_path)

    def _add_attachment_path(self, file_path: str, *, temporary: bool = False) -> None:
        normalized = str(file_path or "").strip()
        if not normalized:
            return
        if normalized not in self._attachment_paths:
            self._attachment_paths.append(normalized)
        if temporary:
            self._temporary_attachment_paths.add(normalized)
        self._sync_attachments_list()

    def _pick_attachments(self, title: str, file_filter: str) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, title, "", file_filter)
        if not files:
            return
        for file_path in files:
            self._add_attachment_path(file_path)

    def _on_add_screenshot(self) -> None:
        if self._capture_in_progress:
            return
        asyncio.create_task(self._async_capture_screenshot())

    def _on_add_video(self) -> None:
        if self._capture_in_progress:
            return
        duration_sec, accepted = QInputDialog.getInt(
            self,
            "Запись видео",
            "Длительность записи (сек):",
            30,
            5,
            120,
            5,
        )
        if not accepted:
            return
        asyncio.create_task(self._async_capture_video(duration_sec))

    def _on_add_file(self) -> None:
        self._pick_attachments(
            "Добавить файл",
            "Все файлы (*.*)"
        )

    def _on_remove_selected_attachment(self) -> None:
        row = self.attachments_list.currentRow()
        if row < 0:
            return
        if 0 <= row < len(self._attachment_paths):
            file_path = self._attachment_paths.pop(row)
            if file_path in self._temporary_attachment_paths:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    logger.debug(f"Не удалось удалить временный файл: {file_path}")
                self._temporary_attachment_paths.discard(file_path)
        self._sync_attachments_list()

    async def _async_capture_screenshot(self) -> None:
        self._capture_in_progress = True
        self._set_media_controls_enabled(False)
        self._set_status("Создаю скриншот для заявки...", error=False)
        try:
            from modules.impl.screen import ScreenCollector

            collector = ScreenCollector()
            result = await collector.collect()
            artifact = next(iter(result.get("_artifacts") or []), {})
            local_path = str(artifact.get("local_path") or "").strip()
            if not local_path:
                raise RuntimeError("Скриншот создан, но файл не найден.")
            self._add_attachment_path(local_path, temporary=True)
            self._set_status(f"Скриншот добавлен: {Path(local_path).name}", error=False)
        except Exception as exc:
            logger.error(f"Ошибка создания скриншота для заявки: {exc}")
            self._set_status(f"Не удалось сделать скриншот: {exc}", error=True)
            QMessageBox.warning(self, "Скриншот", str(exc))
        finally:
            self._capture_in_progress = False
            self._sync_attachments_list()

    async def _async_capture_video(self, duration_sec: int) -> None:
        self._capture_in_progress = True
        self._set_media_controls_enabled(False)
        self._set_status(
            f"Записываю видео ({duration_sec} сек.). Подождите, пожалуйста...",
            error=False,
        )
        try:
            from modules.impl.screen import ScreenCollector

            collector = ScreenCollector()
            result = await collector.record(duration_sec=duration_sec)
            artifact = next(iter(result.get("_artifacts") or []), {})
            local_path = str(artifact.get("local_path") or "").strip()
            if not local_path:
                raise RuntimeError("Видео записано, но файл не найден.")
            self._add_attachment_path(local_path, temporary=True)
            self._set_status(f"Видео добавлено: {Path(local_path).name}", error=False)
        except Exception as exc:
            logger.error(f"Ошибка записи видео для заявки: {exc}")
            self._set_status(f"Не удалось записать видео: {exc}", error=True)
            QMessageBox.warning(self, "Видео", str(exc))
        finally:
            self._capture_in_progress = False
            self._sync_attachments_list()

    def _step_ready(self, step: int) -> bool:
        if step == 0:
            return self._panel.has_active_profile()
        if step == 1:
            return bool(self._selected_form()) and not self.dynamic_fields_widget.validate_required_fields(show_feedback=False)
        if step == 2:
            return bool(self.description_input.toPlainText().strip())
        if step == 3:
            return not self.priority_dynamic_fields_widget.validate_required_fields(show_feedback=False)
        return True

    def _all_required_steps_ready(self) -> bool:
        return all(self._step_ready(step) for step in range(4))

    def _go_to_step(self, step: int, *, force: bool = False) -> None:
        if not force:
            for previous_step in range(step):
                if not self._step_ready(previous_step):
                    return
        self._current_step = max(0, min(step, self._stack.count() - 1))
        self._stack.setCurrentIndex(self._current_step)
        self._update_navigation_state()

    def _update_navigation_state(self) -> None:
        for index, button in enumerate(self._step_buttons):
            unlocked = all(self._step_ready(prev_step) for prev_step in range(index))
            button.setEnabled(unlocked and not self._submitting)
            button.setChecked(index == self._current_step)

        self._back_btn.setEnabled(self._current_step > 0 and not self._submitting)
        self._next_btn.setVisible(self._current_step < self._stack.count() - 1)
        self._next_btn.setEnabled(self._step_ready(self._current_step) and not self._submitting)
        self._submit_btn.setVisible(self._current_step == self._stack.count() - 1)
        self._submit_btn.setEnabled(self._all_required_steps_ready() and not self._submitting)
        self._cancel_btn.setEnabled(not self._submitting)

        captions = {
            0: "Шаг 1 из 4. Выберите инициатора заявки.",
            1: "Шаг 2 из 4. Укажите тип обращения и обязательные поля.",
            2: "Шаг 3 из 4. Опишите проблему и при желании приложите материалы.",
            3: "Шаг 4 из 4. Уточните приоритет и завершите создание.",
        }
        self._step_caption.setText(captions.get(self._current_step, ""))

    def _step_validation_error(self, step: int) -> str:
        if step == 0:
            return "Выберите профиль инициатора перед переходом дальше."
        if step == 1:
            missing_fields = self.dynamic_fields_widget.validate_required_fields(show_feedback=True)
            if missing_fields:
                return "Заполните обязательные поля: " + ", ".join(missing_fields)
            return "Выберите шаблон обращения."
        if step == 2:
            return "Опишите проблему, чтобы можно было создать заявку."
        if step == 3:
            missing_fields = self.priority_dynamic_fields_widget.validate_required_fields(show_feedback=True)
            if missing_fields:
                return "Заполните поля для расчета приоритета: " + ", ".join(missing_fields)
        return ""

    def _on_back_clicked(self) -> None:
        self._go_to_step(self._current_step - 1)

    def _on_next_clicked(self) -> None:
        if self._step_ready(self._current_step):
            self._go_to_step(self._current_step + 1)
            self._set_status("", error=False)
            return
        self._set_status(self._step_validation_error(self._current_step), error=True)

    def _on_cancel_clicked(self) -> None:
        if self._submitting:
            return
        self.reset_wizard()
        self.cancelled.emit()

    def _payload(self) -> dict[str, Any]:
        description = self.description_input.toPlainText().strip()
        priority_facts = build_priority_facts_payload(
            impact_scope=str(self.impact_scope_select.currentData() or "single_user"),
            work_continuity=str(self.work_continuity_select.currentData() or "workaround_available"),
            business_importance=str(self.business_importance_select.currentData() or "normal"),
            urgency_reason=self.urgency_reason_input.text().strip(),
            importance_reason=self.importance_reason_input.text().strip(),
        )
        form_pack = self._panel.ticket_form_pack()
        selected_form = self._selected_form() or {}
        form_payload = self.dynamic_fields_widget.values()
        form_payload.update(self.priority_dynamic_fields_widget.values())
        attachment_paths = [
            *self._attachment_paths,
            *self.dynamic_fields_widget.file_attachment_paths(),
            *self.priority_dynamic_fields_widget.file_attachment_paths(),
        ]
        priority_facts = build_priority_facts_payload_from_form(
            selected_form,
            form_payload,
            fallback=priority_facts,
        )
        for key, value in (priority_facts.get("form_payload") or {}).items():
            form_payload.setdefault(key, value)
        consent_payload = build_diagnostic_consent_payload(
            selected_form,
            granted=self.diagnostic_consent_checkbox.isChecked(),
        )
        payload = {
            "title": f"Обращение: {selected_form.get('request_template_title') or selected_form.get('title') or 'служба поддержки'}",
            "description": description,
            "urgency": priority_facts["urgency"],
            "importance": priority_facts["importance"],
            "urgency_reason": priority_facts["urgency_reason"],
            "importance_reason": priority_facts["importance_reason"],
            "form_key": selected_form.get("key"),
            "request_template_key": selected_form.get("request_template_key") or selected_form.get("key"),
            "form_pack_key": form_pack.get("pack_key"),
            "form_pack_version": form_pack.get("version"),
            "form_payload": form_payload,
            "ticket_type": selected_form.get("ticket_type") or selected_form.get("request_kind") or selected_form.get("key") or "request",
            "attachment_paths": list(dict.fromkeys(attachment_paths)),
        }
        if consent_payload is not None:
            payload["diagnostic_consent"] = consent_payload
        return payload

    def _on_submit_clicked(self) -> None:
        if not self._all_required_steps_ready():
            for step in range(4):
                if not self._step_ready(step):
                    self._go_to_step(step, force=True)
                    self._set_status(self._step_validation_error(step), error=True)
                    break
            return
        asyncio.create_task(self._async_submit())

    async def _async_submit(self) -> None:
        self._submitting = True
        self._update_navigation_state()
        self._set_status("Создаю обращение и подготавливаю первое сообщение...", error=False)
        try:
            payload = self._payload()
            attachment_errors = validate_create_attachment_paths(payload.get("attachment_paths") or [])
            if attachment_errors:
                message = "\n".join(attachment_errors)
                self._set_status(message, error=True)
                QMessageBox.warning(self, "Проверьте вложения", message)
                return
            result = await self._panel._async_create_ticket(
                payload,
                show_success_dialog=False,
                raise_errors=True,
            )
            ticket = result.get("ticket", {}) if isinstance(result, dict) else {}
            ticket_id = str(ticket.get("ticket_id") or "")
            code = result.get("public_access_code") or "—"
            self.reset_wizard()
            self._set_status("Обращение создано. Проверьте дальнейшие действия ниже.", error=False)
            self._show_create_result(ticket, public_access_code=str(code))
            self.ticketCreated.emit(ticket_id)
        except Exception as exc:
            logger.error(f"Ошибка создания обращения из мастера: {exc}")
            message = build_ticket_create_error_message(exc)
            self._set_status(message, error=True)
            QMessageBox.critical(self, "Ошибка", message)
        finally:
            self._submitting = False
            self._update_navigation_state()


class ProfileSidebarWidget(QFrame):
    """Левая колонка главного окна: данные активного профиля и переключение."""

    def __init__(self, panel: "ChatPanel", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._loading_combo = False
        self.setObjectName("ProfileSidebar")
        self.setStyleSheet(theme.profile_sidebar_stylesheet())
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        title = QLabel("Профиль инициатора")
        title.setObjectName("ProfileSidebarTitle")
        outer.addWidget(title)

        self._hint = QLabel("")
        self._hint.setObjectName("ProfileHint")
        self._hint.setWordWrap(True)
        outer.addWidget(self._hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self._fld_display = QLabel("—")
        self._fld_display.setObjectName("ProfileFieldValue")
        self._fld_display.setWordWrap(True)
        self._lbl_display = QLabel("Отображаемое имя")
        self._lbl_display.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_display, self._fld_display)

        self._fld_full = QLabel("—")
        self._fld_full.setObjectName("ProfileFieldValue")
        self._fld_full.setWordWrap(True)
        self._lbl_full = QLabel("ФИО")
        self._lbl_full.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_full, self._fld_full)

        self._fld_location = QLabel("—")
        self._fld_location.setObjectName("ProfileFieldValue")
        self._fld_location.setWordWrap(True)
        self._lbl_location = QLabel("Корпус / кабинет")
        self._lbl_location.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_location, self._fld_location)

        self._fld_phone = QLabel("—")
        self._fld_phone.setObjectName("ProfileFieldValue")
        self._fld_phone.setWordWrap(True)
        self._lbl_phone = QLabel("Телефон")
        self._lbl_phone.setObjectName("ProfileFieldLabel")
        form.addRow(self._lbl_phone, self._fld_phone)

        outer.addLayout(form)

        combo_label = QLabel("Активный профиль")
        combo_label.setObjectName("ProfileFieldLabel")
        outer.addWidget(combo_label)
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(self._on_combo_changed)
        outer.addWidget(self._profile_combo)

        btn_row = QVBoxLayout()
        btn_row.setSpacing(8)
        self._btn_manage = QPushButton("Изменить / создать профиль")
        self._btn_manage.clicked.connect(self._on_manage_clicked)
        btn_row.addWidget(self._btn_manage)
        outer.addLayout(btn_row)

        outer.addStretch(1)
        self.refresh_from_panel()

    def _on_manage_clicked(self) -> None:
        self._panel.open_profile_manager(start_new=False)

    def _on_combo_changed(self, _index: int) -> None:
        if self._loading_combo:
            return
        pid = self._profile_combo.currentData()
        if pid is None:
            return
        cur = self._panel._profiles_data.get("active_profile_id")
        if pid == cur:
            return
        self._panel._profiles_data["active_profile_id"] = pid
        self._panel._save_profiles()

    def refresh_from_panel(self) -> None:
        profile = self._panel._active_profile()
        if profile is None:
            self._hint.setText("Профиль не выбран. Создайте или выберите профиль — без него нельзя создать обращение.")
            self._fld_display.setText("—")
            self._fld_full.setText("—")
            self._fld_location.setText("—")
            self._fld_phone.setText("—")
            for w in (
                self._lbl_display,
                self._lbl_full,
                self._lbl_location,
                self._lbl_phone,
                self._fld_display,
                self._fld_full,
                self._fld_location,
                self._fld_phone,
            ):
                w.show()
        else:
            self._hint.setText("")
            self._fld_display.setText(str(profile.get("display_name") or "—"))
            self._fld_full.setText(str(profile.get("full_name") or "—"))
            loc = " ".join(filter(None, [profile.get("building"), profile.get("room")])) or "—"
            self._fld_location.setText(loc)
            self._fld_phone.setText(str(profile.get("phone") or "—"))

        self._loading_combo = True
        self._profile_combo.clear()
        active_id = self._panel._profiles_data.get("active_profile_id")
        for p in self._panel._profiles():
            title = p.get("display_name") or p.get("full_name") or "Без имени"
            self._profile_combo.addItem(str(title), p.get("id"))
        if self._profile_combo.count() == 0:
            self._profile_combo.addItem("(нет профилей)", None)
        else:
            idx = -1
            if active_id:
                idx = self._profile_combo.findData(active_id)
            if idx < 0:
                idx = 0
            self._profile_combo.setCurrentIndex(idx)
        self._loading_combo = False


class TicketsSidebarWidget(QFrame):
    """Left function panel with ticket search, filters, and list."""

    def __init__(self, panel: "ChatPanel", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self.setObjectName("MainPanel")
        self.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())
        self.setMinimumWidth(720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(18)

        title = QLabel("Обращения")
        title.setObjectName("MainTitle")
        outer.addWidget(title)

        hint = QLabel("Список ваших обращений. Двойной клик открывает чат справа.")
        hint.setObjectName("MainSubtitle")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        # Hidden compatibility button: create flow is now triggered from the left app menu,
        # but ChatPanel still toggles this button while the create dialog is in progress.
        self.create_ticket_btn = QPushButton("Создать обращение")
        self.create_ticket_btn.hide()

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(20)
        self.ticket_search_input = QLineEdit()
        self.ticket_search_input.setObjectName("SearchInput")
        self.ticket_search_input.setPlaceholderText("Поиск по коду, названию, статусу")
        self.ticket_search_input.setMinimumHeight(52)
        self.ticket_search_input.addAction(QIcon(theme.icon_path("search")), QLineEdit.ActionPosition.LeadingPosition)
        self.ticket_search_input.textChanged.connect(panel._on_ticket_search_changed)
        search_row.addWidget(self.ticket_search_input, 1)

        self.filters_btn = QPushButton("Фильтры")
        self.filters_btn.setObjectName("SecondaryButton")
        self.filters_btn.setIcon(QIcon(theme.icon_path("filters")))
        self.filters_btn.setIconSize(QSize(20, 20))
        self.filters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filters_btn.setToolTip("Фильтры списка обращений")
        self.filters_btn.clicked.connect(self._show_filters_menu)
        search_row.addWidget(self.filters_btn, 0)
        outer.addLayout(search_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(10)
        self.filter_all_button = QPushButton("Все 0")
        self.filter_all_button.setObjectName("TicketFilterChipActive")
        self.filter_all_button.setCheckable(True)
        self.filter_all_button.setChecked(True)
        self.filter_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_all_button.clicked.connect(lambda _checked=False: self._select_filter("all"))
        filters_row.addWidget(self.filter_all_button)

        self.filter_open_checkbox = QPushButton("Открытые 0")
        self.filter_open_checkbox.setObjectName("TicketFilterChip")
        self.filter_open_checkbox.setCheckable(True)
        self.filter_open_checkbox.setChecked(True)
        self.filter_open_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_open_checkbox.clicked.connect(lambda _checked=False: self._select_filter("open"))
        filters_row.addWidget(self.filter_open_checkbox)

        self.filter_closed_checkbox = QPushButton("Закрытые 0")
        self.filter_closed_checkbox.setObjectName("TicketFilterChip")
        self.filter_closed_checkbox.setCheckable(True)
        self.filter_closed_checkbox.setChecked(True)
        self.filter_closed_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_closed_checkbox.clicked.connect(lambda _checked=False: self._select_filter("closed"))
        filters_row.addWidget(self.filter_closed_checkbox)
        filters_row.addStretch(1)
        outer.addLayout(filters_row)

        self.tickets_empty_label = QLabel("Ничего не найдено")
        self.tickets_empty_label.setObjectName("ProfileHint")
        self.tickets_empty_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-weight: 600; padding: 8px 4px; background: transparent;"
        )
        self.tickets_empty_label.setVisible(False)
        outer.addWidget(self.tickets_empty_label)

        self.tickets_list = QListView()
        self.tickets_list.setObjectName("TicketsListView")
        self.tickets_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tickets_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tickets_list.setUniformItemSizes(True)
        self.tickets_list.setSpacing(10)
        self.tickets_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tickets_list.setMouseTracking(True)
        self.tickets_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tickets_list.setAutoFillBackground(True)
        self.tickets_model = TicketsListModel(self.tickets_list)
        self.tickets_list.setModel(self.tickets_model)
        self.tickets_list.setItemDelegate(TicketCardDelegate(self.tickets_list))
        self.tickets_list.doubleClicked.connect(lambda *_: panel._on_open_ticket())
        outer.addWidget(self.tickets_list, 1)

        open_row = QHBoxLayout()
        open_row.addStretch(1)
        self.open_ticket_btn = QPushButton("Открыть чат")
        self.open_ticket_btn.setObjectName("PrimaryButton")
        self.open_ticket_btn.setIcon(QIcon(theme.icon_path("message")))
        self.open_ticket_btn.setIconSize(QSize(20, 20))
        self.open_ticket_btn.setMinimumHeight(56)
        self.open_ticket_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_ticket_btn.clicked.connect(panel._on_open_ticket)
        open_row.addWidget(self.open_ticket_btn)
        outer.addLayout(open_row)
        self.refresh_theme()

    def _show_filters_menu(self) -> None:
        menu = QMenu(self)
        theme.apply_agent_dialog_theme(menu)

        all_action = menu.addAction("Все обращения")
        all_action.setCheckable(True)
        all_action.setChecked(self.filter_open_checkbox.isChecked() and self.filter_closed_checkbox.isChecked())
        all_action.triggered.connect(lambda _checked=False: self._select_filter("all"))

        open_action = menu.addAction("Только открытые")
        open_action.setCheckable(True)
        open_action.setChecked(self.filter_open_checkbox.isChecked() and not self.filter_closed_checkbox.isChecked())
        open_action.triggered.connect(lambda _checked=False: self._select_filter("open"))

        closed_action = menu.addAction("Только закрытые")
        closed_action.setCheckable(True)
        closed_action.setChecked(self.filter_closed_checkbox.isChecked() and not self.filter_open_checkbox.isChecked())
        closed_action.triggered.connect(lambda _checked=False: self._select_filter("closed"))

        menu.addSeparator()
        clear_search_action = menu.addAction("Очистить поиск")
        clear_search_action.setEnabled(bool(self.ticket_search_input.text().strip()))
        clear_search_action.triggered.connect(self.ticket_search_input.clear)

        menu.exec(self.filters_btn.mapToGlobal(self.filters_btn.rect().bottomLeft()))

    def _select_filter(self, mode: str) -> None:
        self.filter_all_button.blockSignals(True)
        self.filter_open_checkbox.blockSignals(True)
        self.filter_closed_checkbox.blockSignals(True)
        try:
            if mode == "all":
                self.filter_all_button.setChecked(True)
                self.filter_open_checkbox.setChecked(True)
                self.filter_closed_checkbox.setChecked(True)
            elif mode == "closed":
                self.filter_all_button.setChecked(False)
                self.filter_open_checkbox.setChecked(False)
                self.filter_closed_checkbox.setChecked(True)
            else:
                self.filter_all_button.setChecked(False)
                self.filter_open_checkbox.setChecked(True)
                self.filter_closed_checkbox.setChecked(False)
        finally:
            self.filter_all_button.blockSignals(False)
            self.filter_open_checkbox.blockSignals(False)
            self.filter_closed_checkbox.blockSignals(False)
        self._panel._on_ticket_filter_changed()

    def update_filter_counts(self, total: int, open_count: int, closed_count: int) -> None:
        self.filter_all_button.setText(f"Все  {total}")
        self.filter_open_checkbox.setText(f"Открытые  {open_count}")
        self.filter_closed_checkbox.setText(f"Закрытые  {closed_count}")
        all_active = self.filter_open_checkbox.isChecked() and self.filter_closed_checkbox.isChecked()
        self.filter_all_button.setChecked(all_active)
        self.filter_all_button.setObjectName("TicketFilterChipActive" if all_active else "TicketFilterChip")
        self.filter_open_checkbox.setObjectName(
            "TicketFilterChipActive" if self.filter_open_checkbox.isChecked() and not all_active else "TicketFilterChip"
        )
        self.filter_closed_checkbox.setObjectName(
            "TicketFilterChipActive" if self.filter_closed_checkbox.isChecked() and not all_active else "TicketFilterChip"
        )
        for button in (self.filter_all_button, self.filter_open_checkbox, self.filter_closed_checkbox):
            button.style().unpolish(button)
            button.style().polish(button)

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.chat_panel_stylesheet() + theme.profile_sidebar_stylesheet())
        self.tickets_empty_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-weight: 600; padding: 8px 4px; background: transparent;"
        )
        if hasattr(self, "ticket_search_input"):
            self.ticket_search_input.setStyleSheet("")


class ChatPanel(QWidget):
    """Ticket UI used by the desktop agent."""

    chatSessionChanged = Signal(str)
    requesterProfileChanged = Signal()
    listNavigationVisibilityChanged = Signal(bool)
    ticketsListChanged = Signal()

    def __init__(
        self,
        ticket_client: Optional[TicketApiClient] = None,
        base_url: Optional[str] = None,
        device_id: str = "test_pc_01",
        actor_role: str = "support",
        auth_token: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)

        if base_url is None:
            try:
                from pc_agent.config.config_loader import get_config

                base_url = get_config().server.api_url
            except Exception:
                from pc_agent.config.config_loader import ServerConfig

                base_url = ServerConfig().api_url

        self.device_id = device_id
        try:
            from core.identity import IdentityManager

            identity = IdentityManager().load_or_create()
            self.device_id = identity.get("uuid", device_id)
        except Exception as exc:
            logger.warning(f"Не удалось загрузить identity: {exc}")

        self.user_display_name = socket.gethostname() or "User"
        self.ticket_client = ticket_client or TicketApiClient(
            base_url,
            self.device_id,
            self.user_display_name,
            auth_token=auth_token,
        )

        self.active_ticket_id: Optional[str] = None
        self.current_job_id: Optional[str] = None
        self.tickets_cache: List[dict] = []
        self.local_action_buffer: Dict[str, List[dict]] = {}
        self._ticket_search_query = ""
        self._show_open_tickets = True
        self._show_closed_tickets = True
        self._pinned_messages: Dict[str, List[dict]] = {}
        self._reply_target: Optional[dict] = None
        self._last_timeline_html: Optional[str] = None
        self._last_timeline_item_signatures: List[str] = []
        self._pending_ticket_snapshot: Optional[tuple[dict, List[dict], List[dict]]] = None
        self._active_ticket_messages: List[dict] = []
        self._active_ticket_events: List[dict] = []
        self._last_detail_event_id = 0
        self._oldest_loaded_event_id = 0
        self._has_older_history = False
        self._loading_older_history = False
        self._bubble_menu_open = False
        self._timeline_bubbles: List[MessageBubbleWidget] = []
        self._resolution_prompt_keys: set[str] = set()
        self._resolution_prompt_open_for: Optional[str] = None
        self._pending_tasks: set[asyncio.Task] = set()
        self._is_closing = False
        self._last_marked_read_event_id: Dict[str, int] = {}
        self._optimistic_read_event_id: Dict[str, int] = {}
        self._follow_latest_messages = True
        self._force_scroll_to_latest_on_next_render = False
        self._suspend_scroll_tracking = False
        self._timeline_scroll_restore_revision = 0
        self._profile_sidebar: Optional[ProfileSidebarWidget] = None
        self._tickets_sidebar: Optional[TicketsSidebarWidget] = None
        self._last_tickets_list_fingerprint: Optional[str] = None
        self._last_detail_header_sig: Optional[str] = None
        self._ticket_list_refresh_seq = 0
        self._ticket_detail_refresh_seq = 0
        self._ticket_list_refresh_task: Optional[asyncio.Task] = None
        self._ticket_list_refresh_pending = False
        self._ticket_detail_refresh_task: Optional[asyncio.Task] = None
        self._ticket_detail_refresh_pending = False
        self._tickets_model: Optional[TicketsListModel] = None

        self._profiles_path = resolve_data_root() / "requester_profiles.json"
        self._profiles_data = self._load_profiles()
        self._ticket_form_pack_path = resolve_data_root() / "ticket_form_pack.json"
        self._ticket_form_pack = self._load_ticket_form_pack()
        self._registry_options_path = resolve_data_root() / "registry_options.json"
        self._registry_options = self._load_registry_options()

        self._ticket_list_timer = QTimer(self)
        self._ticket_list_timer.timeout.connect(self._refresh_ticket_list_async)
        self._ticket_detail_timer = QTimer(self)
        self._ticket_detail_timer.timeout.connect(self._refresh_ticket_detail_async)

        self._setup_ui()
        self._ticket_list_timer.start(TICKET_LIST_POLL_INTERVAL_MS)
        self._refresh_ticket_list_async()
        self._refresh_ticket_form_pack_async()

    def _setup_ui(self) -> None:
        self.setObjectName("AgentChatPanel")
        self.setStyleSheet(theme.chat_panel_stylesheet())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._setup_chat_screen()
        root_layout.addWidget(self.chat_screen)

        self._apply_view_port_opts()
        self._solidify_stack_backgrounds()
        self._refresh_profile_selector()

    def _setup_chat_screen(self) -> None:
        self.chat_screen = QWidget()
        self.chat_screen.setObjectName("ChatScreenRoot")
        main_layout = QHBoxLayout(self.chat_screen)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        self.left_panel = QFrame()
        self.left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_panel.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px;"
        )
        self.left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setSpacing(10)

        self.back_to_list_btn = QPushButton("← К обращениям")
        self.back_to_list_btn.setObjectName("SecondaryButton")
        self.back_to_list_btn.clicked.connect(self._show_list_screen)
        left_layout.addWidget(self.back_to_list_btn)

        self.ticket_info_label = QLabel("Обращение не выбрано")
        self.ticket_info_label.setWordWrap(True)
        self.ticket_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.ticket_info_label.linkActivated.connect(self._on_ticket_code_clicked)
        self.ticket_info_label.setStyleSheet(
            f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 14px 16px; border-radius: 16px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG};"
        )
        left_layout.addWidget(self.ticket_info_label)

        self.ticket_meta_label = QLabel("Откройте обращение в списке.")
        self.ticket_meta_label.setWordWrap(True)
        self.ticket_meta_label.setTextFormat(Qt.TextFormat.RichText)
        self.ticket_meta_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.ticket_meta_label.setStyleSheet(
            f"padding: 12px 14px; color: {theme.TEXT_SECONDARY}; background: {theme.BG_INPUT}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 14px; font-size: {theme.BODY_PT}pt; line-height: 1.45;"
        )
        left_layout.addWidget(self.ticket_meta_label, 1)
        left_layout.addStretch(1)
        main_layout.addWidget(self.left_panel)

        self.right_center = QWidget()
        self.right_center.setObjectName("ChatRightColumn")
        self.right_center.setStyleSheet(
            f"QWidget#ChatRightColumn {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 18px; }}"
        )
        center_layout = QVBoxLayout(self.right_center)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(10)

        self.ticket_status_top = QLabel("Статус: —")
        self.ticket_status_top.setStyleSheet(
            f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 12px 16px; border-radius: 14px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG};"
        )
        center_layout.addWidget(self.ticket_status_top)

        self.top_pinned_info = QLabel("Код авторизации и ссылка обращения появятся здесь.")
        self.top_pinned_info.setWordWrap(True)
        self.top_pinned_info.setTextFormat(Qt.TextFormat.RichText)
        self.top_pinned_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.top_pinned_info.setOpenExternalLinks(True)
        self.top_pinned_info.linkActivated.connect(self._on_top_info_link_activated)
        self.top_pinned_info.setStyleSheet(
            f"padding: 12px 14px; border: 1px solid {theme.BORDER}; border-radius: 12px; "
            f"background: {theme.INFO_BG}; color: {theme.INFO_FG}; font-size: {theme.BODY_PT}pt;"
        )
        center_layout.addWidget(self.top_pinned_info)

        self.pinned_messages_widget = QWidget()
        pinned_row = QHBoxLayout(self.pinned_messages_widget)
        pinned_row.setContentsMargins(8, 8, 8, 8)
        pinned_row.setSpacing(8)
        self.pinned_messages_label = QLabel("")
        self.pinned_messages_label.setWordWrap(True)
        self.pinned_messages_label.setStyleSheet(
            f"color: {theme.LINK}; font-size: {theme.BODY_PT}pt; font-weight: 600;"
        )
        self.pinned_clear_btn = QPushButton("✕")
        self.pinned_clear_btn.setFixedSize(28, 28)
        self.pinned_clear_btn.clicked.connect(self._clear_pinned_messages_for_active_ticket)
        pinned_row.addWidget(self.pinned_messages_label, 1)
        pinned_row.addWidget(self.pinned_clear_btn)
        self.pinned_messages_widget.setStyleSheet(
            f"border: 1px dashed {theme.BORDER_SOFT}; border-radius: 12px; background: {theme.BG_CARD_ALT};"
        )
        self.pinned_messages_widget.hide()
        center_layout.addWidget(self.pinned_messages_widget)

        self.reply_stub_label = QLabel("")
        self.reply_stub_label.setWordWrap(True)
        self.reply_stub_label.hide()
        center_layout.addWidget(self.reply_stub_label)

        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setObjectName("TimelineScroll")
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline_scroll.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(16, 16, 16, 16)
        self.timeline_layout.setSpacing(12)
        # Верхний spacer прижимает короткий чат к низу, как в мессенджерах.
        self.timeline_layout.addStretch(1)
        self.timeline_scroll.setWidget(self.timeline_container)
        self.timeline_shell = QWidget()
        self.timeline_shell.setObjectName("TimelineShell")
        timeline_shell_layout = QGridLayout(self.timeline_shell)
        timeline_shell_layout.setContentsMargins(0, 0, 0, 0)
        timeline_shell_layout.setHorizontalSpacing(0)
        timeline_shell_layout.setVerticalSpacing(0)
        timeline_shell_layout.addWidget(self.timeline_scroll, 0, 0)

        self.jump_to_latest_btn = QToolButton()
        self.jump_to_latest_btn.setObjectName("JumpToLatestButton")
        self.jump_to_latest_btn.setText("↓")
        self.jump_to_latest_btn.setToolTip("Перейти к последним сообщениям")
        self.jump_to_latest_btn.clicked.connect(self._jump_to_latest_messages)
        self.jump_to_latest_btn.setVisible(False)
        self.jump_to_latest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_to_latest_btn.setFixedSize(48, 48)
        timeline_shell_layout.addWidget(
            self.jump_to_latest_btn,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )
        center_layout.addWidget(self.timeline_shell, 1)

        timeline_scrollbar = self.timeline_scroll.verticalScrollBar()
        timeline_scrollbar.valueChanged.connect(self._on_timeline_scroll_changed)
        timeline_scrollbar.rangeChanged.connect(self._on_timeline_scroll_changed)

        self.input_line = QLineEdit()
        self.input_line.setObjectName("ChatInputLine")
        self.input_line.setPlaceholderText("Сообщение по обращению")
        self.input_line.returnPressed.connect(self._on_send)
        center_layout.addWidget(self.input_line)

        self.resolution_message_widget = QWidget()
        resolution_layout = QHBoxLayout(self.resolution_message_widget)
        resolution_layout.setContentsMargins(10, 8, 10, 8)
        self.resolution_prompt_label = QLabel(
            "Поддержка перевела обращение в статус 'Решён'. Подтвердить закрытие?"
        )
        self.resolution_prompt_label.setStyleSheet(
            f"font-size: {theme.BODY_PT}pt; color: {theme.TEXT_PRIMARY}; background: transparent;"
        )
        self.resolution_confirm_btn = QPushButton("Подтвердить")
        self.resolution_confirm_btn.setObjectName("PrimaryButton")
        self.resolution_confirm_btn.clicked.connect(lambda: self._spawn_task(self._async_close_ticket()))
        self.resolution_reject_btn = QPushButton("Отклонить")
        self.resolution_reject_btn.setObjectName("SecondaryButton")
        self.resolution_reject_btn.clicked.connect(self._on_reject_resolution)
        resolution_layout.addWidget(self.resolution_prompt_label, 1)
        resolution_layout.addWidget(self.resolution_confirm_btn)
        resolution_layout.addWidget(self.resolution_reject_btn)
        self.resolution_message_widget.hide()
        center_layout.addWidget(self.resolution_message_widget)

        actions = QHBoxLayout()
        self.send_btn = QPushButton("Отправить")
        self.send_btn.setObjectName("ChatSendButton")
        self.send_btn.clicked.connect(self._on_send)
        self.attach_btn = QToolButton()
        self.attach_btn.setText("📎")
        self.attach_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.attach_btn.setToolTip("Прикрепить")
        attach_menu = QMenu(self.attach_btn)
        attach_menu.setObjectName("AgentPopupMenu")
        attach_menu.addAction("Прикрепить фото", self._on_attach_photo)
        attach_menu.addAction("Прикрепить документ", self._on_attach_document)
        attach_menu.addAction("Прикрепить любой файл", self._on_attach_any_file)
        self.attach_btn.setMenu(attach_menu)
        self.media_btn = QPushButton("Скриншот / Видео")
        media_menu = QMenu(self.media_btn)
        media_menu.setObjectName("AgentPopupMenu")
        media_menu.addAction("Сделать скриншот", self._on_send_screenshot)
        media_menu.addAction("Записать видео до 60 секунд", self._on_send_video)
        self.media_btn.setMenu(media_menu)
        self.tool_status_label = QLabel("")
        actions.addWidget(self.send_btn)
        actions.addWidget(self.attach_btn)
        actions.addWidget(self.media_btn)
        actions.addWidget(self.tool_status_label, 1)
        center_layout.addLayout(actions)

        main_layout.addWidget(self.right_center, 3)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.chat_panel_stylesheet())
        self._apply_view_port_opts()
        if hasattr(self, "left_panel"):
            self.left_panel.setStyleSheet(
                f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 16px;"
            )
        if hasattr(self, "right_center"):
            self.right_center.setStyleSheet(
                f"QWidget#ChatRightColumn {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 18px; }}"
            )
        if hasattr(self, "ticket_info_label"):
            self.ticket_info_label.setStyleSheet(
                f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 14px 16px; border-radius: 16px; "
                f"background: {theme.INFO_BG}; color: {theme.INFO_FG};"
            )
        if hasattr(self, "ticket_meta_label"):
            self.ticket_meta_label.setStyleSheet(
                f"padding: 12px 14px; color: {theme.TEXT_SECONDARY}; background: {theme.BG_INPUT}; "
                f"border: 1px solid {theme.BORDER}; border-radius: 14px; font-size: {theme.BODY_PT}pt; line-height: 1.45;"
            )
        normalized_status = ""
        if hasattr(self, "ticket_status_top"):
            status_text = self.ticket_status_top.text()
            if ":" in status_text:
                normalized_status = status_text.split(":", 1)[1].split("•", 1)[0].strip().lower().replace(" ", "_")
            status_fg, status_bg = ticket_status_colors(normalized_status or "unknown")
            self.ticket_status_top.setStyleSheet(
                f"font-weight: 700; font-size: {theme.TITLE_PT}pt; padding: 12px 16px; border-radius: 14px; "
                f"background: {status_bg}; color: {status_fg};"
            )
        if hasattr(self, "top_pinned_info"):
            self.top_pinned_info.setStyleSheet(
                f"padding: 12px 14px; border: 1px solid {theme.BORDER}; border-radius: 12px; "
                f"background: {theme.INFO_BG}; color: {theme.INFO_FG}; font-size: {theme.BODY_PT}pt;"
            )
        if hasattr(self, "pinned_messages_label"):
            self.pinned_messages_label.setStyleSheet(
                f"color: {theme.LINK}; font-size: {theme.BODY_PT}pt; font-weight: 600;"
            )
        if hasattr(self, "pinned_messages_widget"):
            self.pinned_messages_widget.setStyleSheet(
                f"border: 1px dashed {theme.BORDER_SOFT}; border-radius: 12px; background: {theme.BG_CARD_ALT};"
            )
        if hasattr(self, "reply_stub_label"):
            self.reply_stub_label.setStyleSheet(
                f"padding: 6px 10px; border-radius: 10px; background: {theme.INFO_BG}; "
                f"color: {theme.INFO_FG}; border: 1px solid {theme.BORDER};"
            )
        if hasattr(self, "resolution_message_widget"):
            self.resolution_message_widget.setStyleSheet(
                f"background: {theme.BG_CARD_ALT}; border: 1px solid {theme.BORDER_SOFT}; border-radius: 12px;"
            )
        if hasattr(self, "resolution_prompt_label"):
            self.resolution_prompt_label.setStyleSheet(
                f"font-size: {theme.BODY_PT}pt; color: {theme.TEXT_PRIMARY}; background: transparent;"
            )
        self._apply_ticket_background(normalized_status)
        if hasattr(self, "timeline_layout"):
            for index in range(self.timeline_layout.count()):
                item = self.timeline_layout.itemAt(index)
                widget = item.widget()
                if isinstance(widget, MessageBubbleWidget):
                    widget.refresh_theme()

    def _apply_view_port_opts(self) -> None:
        base = QFont()
        base.setFamilies(["Segoe UI", "Tahoma", "Arial"])
        base.setPointSize(10)
        self.setFont(base)
        if hasattr(self, "tickets_list"):
            self.tickets_list.setFont(base)
            _list_bg = QColor(theme.BG_CARD)
            list_pal = QPalette(self.tickets_list.palette())
            list_pal.setColor(QPalette.ColorRole.Window, _list_bg)
            list_pal.setColor(QPalette.ColorRole.Base, _list_bg)
            self.tickets_list.setPalette(list_pal)

            t_vp = self.tickets_list.viewport()
            t_vp.setMouseTracking(True)
            # Не ставить WA_OpaquePaintEvent: иначе Qt не заливает фон viewport, а делегат рисует
            # только строки — на Windows остаётся «чёрная дыра».
            t_vp.setAutoFillBackground(True)
            t_vp.setStyleSheet(f"background-color: {theme.BG_CARD};")
            vp_pal = QPalette(t_vp.palette())
            vp_pal.setColor(QPalette.ColorRole.Window, _list_bg)
            vp_pal.setColor(QPalette.ColorRole.Base, _list_bg)
            t_vp.setPalette(vp_pal)
        if hasattr(self, "timeline_scroll"):
            self.timeline_scroll.setAutoFillBackground(True)
            tsp = self.timeline_scroll.palette()
            tsp.setColor(self.timeline_scroll.backgroundRole(), QColor(theme.TIMELINE_SCROLL_BG))
            self.timeline_scroll.setPalette(tsp)
            s_vp = self.timeline_scroll.viewport()
            # На Windows OpaquePaintEvent у viewport QScrollArea приводит к "грязной"
            # перерисовке (старые пузыри визуально остаются под новыми).
            s_vp.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
            s_vp.setAutoFillBackground(True)
            pal2 = s_vp.palette()
            pal2.setColor(s_vp.backgroundRole(), QColor(theme.TIMELINE_SCROLL_BG))
            s_vp.setPalette(pal2)
        if hasattr(self, "timeline_container"):
            self.timeline_container.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def _solidify_stack_backgrounds(self) -> None:
        page = QColor(theme.BG_PAGE)
        for w in (self, self.chat_screen):
            w.setAutoFillBackground(True)
            pal = QPalette(w.palette())
            pal.setColor(QPalette.ColorRole.Window, page)
            w.setPalette(pal)
        if hasattr(self, "timeline_container"):
            tl = QColor(theme.TIMELINE_SCROLL_BG)
            self.timeline_container.setAutoFillBackground(True)
            p = QPalette(self.timeline_container.palette())
            p.setColor(QPalette.ColorRole.Window, tl)
            self.timeline_container.setPalette(p)

    def _profiles_dir_ready(self) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self) -> dict:
        try:
            if self._profiles_path.exists():
                return json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Не удалось загрузить профили: {exc}")
        return {"active_profile_id": None, "profiles": []}

    def _save_profiles(self) -> None:
        self._profiles_dir_ready()
        self._profiles_path.write_text(
            json.dumps(self._profiles_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._refresh_profile_selector()
        self.requesterProfileChanged.emit()
        self._sync_profile_to_registry()

    def _load_ticket_form_pack(self) -> dict[str, Any]:
        try:
            if self._ticket_form_pack_path.exists():
                raw = json.loads(self._ticket_form_pack_path.read_text(encoding="utf-8"))
                return normalize_ticket_form_pack(raw)
        except Exception as exc:
            logger.warning(f"Не удалось загрузить каталог форм: {exc}")
        return build_default_ticket_form_pack()

    def _save_ticket_form_pack(self) -> None:
        self._profiles_dir_ready()
        self._ticket_form_pack_path.write_text(
            json.dumps(self._ticket_form_pack, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def ticket_form_pack(self) -> dict[str, Any]:
        return self._ticket_form_pack

    def _load_registry_options(self) -> dict[str, Any]:
        try:
            if self._registry_options_path.exists():
                raw = json.loads(self._registry_options_path.read_text(encoding="utf-8"))
                return raw if isinstance(raw, dict) else {}
        except Exception as exc:
            logger.warning(f"Не удалось загрузить справочники формы: {exc}")
        return {}

    def _save_registry_options(self) -> None:
        self._profiles_dir_ready()
        self._registry_options_path.write_text(
            json.dumps(self._registry_options, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def registry_options(self) -> dict[str, Any]:
        return self._registry_options if isinstance(self._registry_options, dict) else {}

    def _apply_registry_options(self, raw_options: Any) -> None:
        self._registry_options = raw_options if isinstance(raw_options, dict) else {}
        self._save_registry_options()

    def _apply_ticket_form_pack(self, raw_pack: Any) -> None:
        self._ticket_form_pack = normalize_ticket_form_pack(raw_pack)
        self._save_ticket_form_pack()

    def _refresh_ticket_form_pack_async(self, force: bool = False) -> None:
        self._spawn_task(self._async_refresh_ticket_form_pack(force=force))

    async def _async_refresh_ticket_form_pack(self, force: bool = False) -> None:
        if self._is_closing:
            return
        current_version = str(self._ticket_form_pack.get("version") or "") if isinstance(self._ticket_form_pack, dict) else ""
        try:
            result = await self.ticket_client.get_ticket_form_pack_current(
                pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
                current_version=current_version or None,
            )
            pack = result.get("pack") if isinstance(result, dict) else None
            has_update = bool(result.get("has_update")) if isinstance(result, dict) else False
            next_version = str((pack or {}).get("version") or "")
            if pack and (force or has_update or next_version != current_version):
                self._apply_ticket_form_pack(pack)
        except Exception as exc:
            logger.info(f"Каталог форм недоступен, используем кеш: {exc}")
        try:
            self._apply_registry_options(await self.ticket_client.get_registry_options())
        except Exception as exc:
            logger.info(f"Справочники форм недоступны, используем кеш: {exc}")

    def _profiles(self) -> List[dict]:
        profiles = self._profiles_data.get("profiles")
        return profiles if isinstance(profiles, list) else []

    def set_profile_sidebar(self, sidebar: ProfileSidebarWidget) -> None:
        self._profile_sidebar = sidebar

    def set_tickets_sidebar(self, sidebar: TicketsSidebarWidget) -> None:
        self._tickets_sidebar = sidebar
        self.create_ticket_btn = sidebar.create_ticket_btn
        self.ticket_search_input = sidebar.ticket_search_input
        self.filter_open_checkbox = sidebar.filter_open_checkbox
        self.filter_closed_checkbox = sidebar.filter_closed_checkbox
        self.tickets_empty_label = sidebar.tickets_empty_label
        self.tickets_list = sidebar.tickets_list
        self.open_ticket_btn = sidebar.open_ticket_btn
        self._tickets_model = sidebar.tickets_model
        self._apply_view_port_opts()
        self._update_tickets_list_ui()

    def _refresh_profile_selector(self) -> None:
        if self._profile_sidebar is not None:
            self._profile_sidebar.refresh_from_panel()

    def _filtered_tickets_for_list(self) -> List[dict]:
        filtered: List[dict] = []
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            status = str(ticket.get("status") or "").strip().lower()
            is_closed = status == "closed"
            if is_closed and not self._show_closed_tickets:
                continue
            if (not is_closed) and not self._show_open_tickets:
                continue
            if ticket_matches_query(ticket, self._ticket_search_query):
                filtered.append(ticket)
        return filtered

    @staticmethod
    def _fingerprint_visible_tickets(filtered: List[dict]) -> str:
        return "\n".join(ticket_row_fingerprint(t) for t in filtered)

    def _ticket_counts_for_current_query(self) -> tuple[int, int, int]:
        open_count = 0
        closed_count = 0
        for row in self.tickets_cache:
            ticket = row.get("ticket", row)
            if not ticket_matches_query(ticket, self._ticket_search_query):
                continue
            status = str(ticket.get("status") or "").strip().lower()
            if status == "closed":
                closed_count += 1
            else:
                open_count += 1
        return open_count + closed_count, open_count, closed_count

    def _on_ticket_search_changed(self, text: str) -> None:
        self._ticket_search_query = text or ""
        self._last_tickets_list_fingerprint = None
        self._update_tickets_list_ui()

    def _on_ticket_filter_changed(self) -> None:
        self._show_open_tickets = bool(self.filter_open_checkbox.isChecked())
        self._show_closed_tickets = bool(self.filter_closed_checkbox.isChecked())
        if not self._show_open_tickets and not self._show_closed_tickets:
            self._show_open_tickets = True
            self.filter_open_checkbox.blockSignals(True)
            self.filter_open_checkbox.setChecked(True)
            self.filter_open_checkbox.blockSignals(False)
        self._last_tickets_list_fingerprint = None
        self._update_tickets_list_ui()

    def _active_profile(self) -> Optional[dict]:
        active_id = self._profiles_data.get("active_profile_id")
        if not active_id:
            return None
        for profile in self._profiles():
            if profile.get("id") == active_id:
                return profile
        return None

    def current_requester_profile_summary(self) -> str:
        profile = self._active_profile()
        if not profile:
            return f"Без профиля | {self.user_display_name}"
        parts = [profile.get("full_name") or profile.get("display_name") or "Без имени"]
        if profile.get("department"):
            parts.append(profile["department"])
        location = " ".join(filter(None, [profile.get("building"), profile.get("room")]))
        if location:
            parts.append(location)
        if profile.get("phone"):
            parts.append(profile["phone"])
        return " | ".join(parts)

    def has_active_profile(self) -> bool:
        return self._active_profile() is not None

    def open_profile_manager(self, *, start_new: bool = False) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Профили инициатора")
        dialog.setMinimumWidth(540)
        theme.apply_agent_dialog_theme(dialog)
        layout = QVBoxLayout(dialog)

        profiles_list = QListWidget()
        profiles_list.setObjectName("ProfileManagerList")
        layout.addWidget(profiles_list)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        display_name = QLineEdit()
        full_name = QLineEdit()
        department = QLineEdit()
        building = QLineEdit()
        room = QLineEdit()
        phone = QLineEdit()
        form.addRow("Отображаемое имя", display_name)
        form.addRow("ФИО", full_name)
        form.addRow("Подразделение", department)
        form.addRow("Здание", building)
        form.addRow("Кабинет", room)
        form.addRow("Телефон", phone)
        layout.addWidget(form_widget)

        def refresh_profiles(
            selected_id: Optional[str] = None,
            *,
            skip_auto_select: bool = False,
        ) -> None:
            profiles_list.clear()
            for profile in self._profiles():
                title = profile.get("display_name") or profile.get("full_name") or "Без имени"
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, profile.get("id"))
                profiles_list.addItem(item)
                if selected_id and profile.get("id") == selected_id:
                    profiles_list.setCurrentItem(item)
            if skip_auto_select:
                return
            if profiles_list.count() and profiles_list.currentRow() < 0:
                profiles_list.setCurrentRow(0)

        def load_current() -> None:
            item = profiles_list.currentItem()
            profile_id = item.data(Qt.ItemDataRole.UserRole) if item else None
            profile = next((p for p in self._profiles() if p.get("id") == profile_id), None)
            display_name.setText(profile.get("display_name") if profile else "")
            full_name.setText(profile.get("full_name") if profile else "")
            department.setText(profile.get("department") if profile else "")
            building.setText(profile.get("building") if profile else "")
            room.setText(profile.get("room") if profile else "")
            phone.setText(profile.get("phone") if profile else "")

        profiles_list.currentItemChanged.connect(lambda *_: load_current())

        buttons = QHBoxLayout()
        btn_new = QPushButton("Новый")
        btn_save = QPushButton("Сохранить")
        btn_delete = QPushButton("Удалить")
        btn_select = QPushButton("Выбрать активным")
        btn_save.setObjectName("PrimaryButton")
        btn_select.setObjectName("PrimaryButton")
        btn_new.setObjectName("SecondaryButton")
        btn_delete.setObjectName("SecondaryButton")
        buttons.addWidget(btn_new)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_delete)
        buttons.addWidget(btn_select)
        layout.addLayout(buttons)

        def current_profile_id() -> Optional[str]:
            item = profiles_list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def save_profile(*, force_new: bool) -> None:
            profile_id = None if force_new else current_profile_id()
            payload = {
                "id": profile_id or str(uuid.uuid4()),
                "display_name": display_name.text().strip(),
                "full_name": full_name.text().strip(),
                "department": department.text().strip(),
                "building": building.text().strip(),
                "room": room.text().strip(),
                "phone": phone.text().strip(),
            }
            profiles = [p for p in self._profiles() if p.get("id") != payload["id"]]
            profiles.append(payload)
            self._profiles_data["profiles"] = profiles
            if not self._profiles_data.get("active_profile_id"):
                self._profiles_data["active_profile_id"] = payload["id"]
            self._save_profiles()
            refresh_profiles(payload["id"])

        def save_clicked() -> None:
            save_profile(force_new=current_profile_id() is None)

        def start_blank_profile() -> None:
            profiles_list.clearSelection()
            display_name.clear()
            full_name.clear()
            department.clear()
            building.clear()
            room.clear()
            phone.clear()

        def delete_profile() -> None:
            profile_id = current_profile_id()
            if not profile_id:
                return
            self._profiles_data["profiles"] = [p for p in self._profiles() if p.get("id") != profile_id]
            if self._profiles_data.get("active_profile_id") == profile_id:
                self._profiles_data["active_profile_id"] = self._profiles()[0].get("id") if self._profiles() else None
            self._save_profiles()
            refresh_profiles()
            load_current()

        def select_active() -> None:
            profile_id = current_profile_id()
            if not profile_id:
                return
            self._profiles_data["active_profile_id"] = profile_id
            self._save_profiles()
            dialog.accept()

        btn_new.clicked.connect(start_blank_profile)
        btn_save.clicked.connect(save_clicked)
        btn_delete.clicked.connect(delete_profile)
        btn_select.clicked.connect(select_active)

        active = self._profiles_data.get("active_profile_id")
        if start_new:
            refresh_profiles(None, skip_auto_select=True)
            profiles_list.clearSelection()
            load_current()
        else:
            refresh_profiles(active)
            load_current()
        dialog.exec()
        self._refresh_profile_selector()

    def _current_requester_payload(self) -> tuple[dict, str]:
        profile = self._active_profile() or {}
        requester_profile = {
            "profile_id": profile.get("id") or "",
            "display_name": profile.get("display_name") or "",
            "full_name": profile.get("full_name") or "",
            "department": profile.get("department") or "",
            "building": profile.get("building") or "",
            "room": profile.get("room") or "",
            "phone": profile.get("phone") or "",
        }
        display_name = profile.get("display_name") or profile.get("full_name") or self.user_display_name
        return requester_profile, display_name

    def _registry_profile_payload(self, profile: Optional[dict] = None) -> Optional[tuple[str, str, dict]]:
        profile = profile or self._active_profile()
        if not profile:
            return None
        profile_id = str(profile.get("id") or "").strip()
        if not profile_id:
            return None
        display_name = profile.get("display_name") or profile.get("full_name") or self.user_display_name
        payload = {
            "profile_id": profile_id,
            "display_name": profile.get("display_name") or "",
            "full_name": profile.get("full_name") or "",
            "department": profile.get("department") or "",
            "building": profile.get("building") or "",
            "room": profile.get("room") or "",
            "phone": profile.get("phone") or "",
        }
        return profile_id, display_name, payload

    def _sync_profile_to_registry(self, profile: Optional[dict] = None) -> None:
        registry_payload = self._registry_profile_payload(profile)
        if registry_payload is None:
            return
        requester_id, display_name, payload = registry_payload
        self._spawn_task(
            self.ticket_client.sync_registry_profile(
                requester_id=requester_id,
                display_name=display_name,
                profile=payload,
            )
        )

    def _spawn_task(self, coro) -> Optional[asyncio.Task]:
        if self._is_closing:
            try:
                coro.close()
            except Exception:
                pass
            return None
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)

        def _done(done_task: asyncio.Task) -> None:
            self._pending_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug(f"Фоновая задача ChatPanel завершилась с ошибкой: {exc}")

        task.add_done_callback(_done)
        return task

    def _cancel_pending_tasks(self) -> None:
        self._is_closing = True
        for task in list(self._pending_tasks):
            task.cancel()
        self._pending_tasks.clear()

    def _refresh_ticket_list_async(self) -> None:
        self._schedule_singleflight_refresh("_ticket_list_refresh_task", "_ticket_list_refresh_pending", self._async_refresh_ticket_list)

    def _refresh_ticket_detail_async(self) -> None:
        if self.active_ticket_id:
            self._schedule_singleflight_refresh(
                "_ticket_detail_refresh_task",
                "_ticket_detail_refresh_pending",
                self._async_refresh_ticket_detail,
            )

    def _schedule_singleflight_refresh(self, task_attr: str, pending_attr: str, factory) -> Optional[asyncio.Task]:
        existing = getattr(self, task_attr, None)
        if existing and not existing.done():
            setattr(self, pending_attr, True)
            return existing
        setattr(self, pending_attr, False)
        task = self._spawn_task(factory())
        setattr(self, task_attr, task)
        if task is None:
            return None

        def _done(done_task: asyncio.Task) -> None:
            if getattr(self, task_attr, None) is done_task:
                setattr(self, task_attr, None)
            if self._is_closing:
                setattr(self, pending_attr, False)
                return
            if getattr(self, pending_attr, False):
                setattr(self, pending_attr, False)
                self._schedule_singleflight_refresh(task_attr, pending_attr, factory)

        task.add_done_callback(_done)
        return task

    async def _async_refresh_ticket_list(self) -> None:
        if self._is_closing:
            return
        self._ticket_list_refresh_seq += 1
        my_seq = self._ticket_list_refresh_seq
        try:
            result = await self.ticket_client.list_tickets()
            if self._is_closing or my_seq != self._ticket_list_refresh_seq:
                return
            if result.get("status") != "ok":
                return
            self.tickets_cache = result.get("tickets", [])
            filtered = self._filtered_tickets_for_list()
            fp = self._fingerprint_visible_tickets(filtered)
            if fp == self._last_tickets_list_fingerprint:
                return
            self._update_tickets_list_ui()
        except Exception as exc:
            if not self._is_closing:
                logger.exception(
                    "Ошибка загрузки списка обращений: "
                    f"type={type(exc).__name__} detail={exc!r}"
                )

    def _update_tickets_list_ui(self) -> None:
        if self._tickets_sidebar is None or self._tickets_model is None:
            return
        filtered_tickets = self._filtered_tickets_for_list()
        self._last_tickets_list_fingerprint = self._fingerprint_visible_tickets(filtered_tickets)
        if hasattr(self._tickets_sidebar, "update_filter_counts"):
            self._tickets_sidebar.update_filter_counts(*self._ticket_counts_for_current_query())

        sm = self.tickets_list.selectionModel()
        prev_tid: Optional[str] = None
        cur = sm.currentIndex()
        if cur.isValid() and self._tickets_model is not None:
            prev_ticket = self._tickets_model.ticket_at_row(cur.row())
            if prev_ticket:
                prev_tid = str(prev_ticket.get("ticket_id") or "")

        current_id = self.active_ticket_id or prev_tid
        scroll_bar = self.tickets_list.verticalScrollBar()
        scroll_value = scroll_bar.value()

        self.tickets_list.setUpdatesEnabled(False)
        try:
            assert self._tickets_model is not None
            self._tickets_model.set_rows(filtered_tickets)
            self.tickets_empty_label.setVisible(len(filtered_tickets) == 0)
            if not filtered_tickets:
                sm.clear()
                QTimer.singleShot(0, lambda: scroll_bar.setValue(0))
            else:
                row = self._tickets_model.row_for_ticket_id(current_id) if current_id else -1
                if row < 0:
                    row = 0
                idx = self._tickets_model.index(row, 0)
                self.tickets_list.setCurrentIndex(idx)
                QTimer.singleShot(0, lambda: scroll_bar.setValue(min(scroll_value, scroll_bar.maximum())))
        finally:
            self.tickets_list.setUpdatesEnabled(True)
        self.ticketsListChanged.emit()

    def _latest_requester_read_event_id(self, ticket: dict, messages: List[dict], events: List[dict]) -> int:
        counters = ticket.get("chat_counters") or {}
        unread_messages = int(counters.get("requester_unread_messages") or 0)
        unread_tools = int(counters.get("requester_unread_tool_calls") or 0)
        if unread_messages <= 0 and unread_tools <= 0:
            return 0
        last_read_event_id = int(counters.get("requester_last_read_event_id") or 0)
        if self._has_older_history and self._oldest_loaded_event_id > 0:
            if last_read_event_id < max(self._oldest_loaded_event_id - 1, 0):
                return 0

        latest_event_id = 0
        for message in messages:
            event_id = message.get("event_id")
            try:
                latest_event_id = max(latest_event_id, int(event_id))
            except (TypeError, ValueError):
                pass
        for event in events:
            event_id = event.get("id") or event.get("event_id")
            try:
                latest_event_id = max(latest_event_id, int(event_id))
            except (TypeError, ValueError):
                pass
        return latest_event_id

    def _maybe_mark_ticket_read(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        ticket_id = str(ticket.get("ticket_id") or "")
        if not ticket_id:
            return
        if not self._force_scroll_to_latest_on_next_render and not self._is_timeline_near_bottom(24):
            return
        last_read_event_id = self._latest_requester_read_event_id(ticket, messages, events)
        if last_read_event_id <= 0:
            return
        if last_read_event_id <= int(self._last_marked_read_event_id.get(ticket_id, 0)):
            return
        previous_value = int(self._last_marked_read_event_id.get(ticket_id, 0))
        previous_optimistic = int(self._optimistic_read_event_id.get(ticket_id, 0))
        self._last_marked_read_event_id[ticket_id] = last_read_event_id
        self._optimistic_read_event_id[ticket_id] = max(previous_optimistic, last_read_event_id)
        # Сразу убираем "непрочитано" локально, не дожидаясь roundtrip на сервер.
        self._apply_ticket_detail_header(ticket, messages, events)
        self._spawn_task(
            self._async_mark_ticket_read(
                ticket_id,
                last_read_event_id,
                previous_value,
                previous_optimistic,
            )
        )

    async def _async_mark_ticket_read(
        self,
        ticket_id: str,
        last_read_event_id: int,
        previous_value: int,
        previous_optimistic: int,
    ) -> None:
        try:
            await self.ticket_client.mark_ticket_read(ticket_id, last_read_event_id)
            await self._async_refresh_ticket_list()
        except Exception as exc:
            if not self._is_closing:
                logger.warning(f"Не удалось отметить сообщения как прочитанные для {ticket_id}: {exc}")
                self._last_marked_read_event_id[ticket_id] = previous_value
                if previous_optimistic > 0:
                    self._optimistic_read_event_id[ticket_id] = previous_optimistic
                else:
                    self._optimistic_read_event_id.pop(ticket_id, None)

    def _reset_active_ticket_cache(self) -> None:
        self._active_ticket_messages = []
        self._active_ticket_events = []
        self._last_detail_event_id = 0
        self._oldest_loaded_event_id = 0
        self._has_older_history = False
        self._loading_older_history = False
        self._last_timeline_item_signatures = []

    @staticmethod
    def _extract_oldest_event_id(messages: List[dict], events: List[dict]) -> int:
        oldest_event_id = 0
        for message in messages:
            try:
                event_id = int(message.get("event_id") or 0)
            except (TypeError, ValueError):
                continue
            if event_id > 0 and (oldest_event_id == 0 or event_id < oldest_event_id):
                oldest_event_id = event_id
        for event in events:
            try:
                event_id = int(event.get("id") or event.get("event_id") or 0)
            except (TypeError, ValueError):
                continue
            if event_id > 0 and (oldest_event_id == 0 or event_id < oldest_event_id):
                oldest_event_id = event_id
        return oldest_event_id

    def _consume_ticket_detail_payload(
        self,
        result: dict,
        *,
        mode: str,
    ) -> tuple[dict, List[dict], List[dict]]:
        ticket = result.get("ticket", {})
        messages = list(result.get("messages", []))
        events = list(result.get("events", []))
        if mode == "append":
            self._active_ticket_messages = merge_ticket_stream(
                self._active_ticket_messages,
                messages,
                key_fields=("message_id", "event_id", "id"),
            )
            self._active_ticket_events = merge_ticket_stream(
                self._active_ticket_events,
                events,
                key_fields=("id", "event_id", "message_id"),
            )
        elif mode == "prepend":
            self._active_ticket_messages = prepend_ticket_stream(
                self._active_ticket_messages,
                messages,
                key_fields=("message_id", "event_id", "id"),
            )
            self._active_ticket_events = prepend_ticket_stream(
                self._active_ticket_events,
                events,
                key_fields=("id", "event_id", "message_id"),
            )
        else:
            self._active_ticket_messages = messages
            self._active_ticket_events = events

        self._last_detail_event_id = max(
            int(result.get("last_event_id") or 0),
            int(self._last_detail_event_id or 0),
        )
        if mode in {"replace", "prepend"}:
            candidate_oldest_event_id = int(result.get("oldest_event_id") or 0)
            if candidate_oldest_event_id <= 0:
                candidate_oldest_event_id = self._extract_oldest_event_id(
                    self._active_ticket_messages,
                    self._active_ticket_events,
                )
            self._oldest_loaded_event_id = candidate_oldest_event_id
            self._has_older_history = bool(result.get("has_older"))
        return ticket, list(self._active_ticket_messages), list(self._active_ticket_events)

    async def _async_refresh_ticket_detail(self) -> None:
        if self._is_closing or not self.active_ticket_id:
            return
        self._ticket_detail_refresh_seq += 1
        my_seq = self._ticket_detail_refresh_seq
        initial_tail_load = (
            not self._active_ticket_messages
            and not self._active_ticket_events
            and int(self._last_detail_event_id or 0) <= 0
        )
        try:
            if initial_tail_load:
                result = await self.ticket_client.get_ticket(
                    self.active_ticket_id,
                    limit=TICKET_HISTORY_PAGE_SIZE,
                )
                consume_mode = "replace"
            else:
                result = await self.ticket_client.get_ticket(
                    self.active_ticket_id,
                    since_event_id=(self._last_detail_event_id or None),
                )
                consume_mode = "append"
            if self._is_closing or my_seq != self._ticket_detail_refresh_seq:
                return
            if result.get("status") != "ok":
                return
            ticket, messages, events = self._consume_ticket_detail_payload(result, mode=consume_mode)
            self._update_ticket_detail_ui(ticket, messages, events)
        except Exception as exc:
            if not self._is_closing:
                logger.exception(
                    "Ошибка загрузки обращения "
                    f"{self.active_ticket_id}: type={type(exc).__name__} detail={exc!r}"
                )

    def _load_older_history_async(self) -> None:
        if not self.active_ticket_id or not self._has_older_history or self._loading_older_history:
            return
        if self._oldest_loaded_event_id <= 0:
            return
        self._loading_older_history = True
        self._spawn_task(self._async_load_older_history())

    def _schedule_fill_viewport_with_history(self) -> None:
        if not self.active_ticket_id or not self._has_older_history or self._loading_older_history:
            return

        def maybe_load() -> None:
            if not self.active_ticket_id or not self._has_older_history or self._loading_older_history:
                return
            scroll_bar = self.timeline_scroll.verticalScrollBar()
            if scroll_bar.maximum() <= 0:
                self._load_older_history_async()

        QTimer.singleShot(0, maybe_load)
        QTimer.singleShot(40, maybe_load)

    async def _async_load_older_history(self) -> None:
        if self._is_closing or not self.active_ticket_id:
            return
        if not self._has_older_history or self._oldest_loaded_event_id <= 0:
            return
        try:
            result = await self.ticket_client.get_ticket(
                self.active_ticket_id,
                before_event_id=self._oldest_loaded_event_id,
                limit=TICKET_HISTORY_PAGE_SIZE,
            )
            if self._is_closing or result.get("status") != "ok":
                return
            ticket, messages, events = self._consume_ticket_detail_payload(result, mode="prepend")
            self._update_ticket_detail_ui(ticket, messages, events)
        except Exception as exc:
            if not self._is_closing:
                logger.error(f"Ошибка догрузки старой истории тикета {self.active_ticket_id}: {exc}")
        finally:
            self._loading_older_history = False

    def _detail_header_signature(self, ticket: dict, messages: List[dict]) -> str:
        return json.dumps(
            {
                "ticket_id": ticket.get("ticket_id"),
                "code": ticket.get("ticket_code"),
                "title": ticket.get("title"),
                "status": ticket.get("status"),
                "counters": ticket.get("chat_counters"),
                "updated_at": ticket.get("updated_at"),
                "resolved_at": ticket.get("resolved_at"),
                "closed_at": ticket.get("closed_at"),
                "public_access_url": ticket.get("public_access_url"),
                "public_access_code_hint": ticket.get("public_access_code_hint"),
                "extracted_code": self._extract_public_access_code(ticket, messages),
                "meta_html": self._build_ticket_meta_html(ticket),
                "optimistic_read_until": self._optimistic_read_event_id.get(str(ticket.get("ticket_id") or ""), 0),
            },
            sort_keys=True,
            default=str,
        )

    def _apply_ticket_detail_header(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        code = ticket.get("ticket_code") or ticket.get("ticket_id", "")
        title = ticket.get("title") or "Без названия"
        status = ticket.get("status") or "unknown"
        status_fg, status_bg = ticket_status_colors(status)
        ticket_id = str(ticket.get("ticket_id") or "")
        counters = ticket.get("chat_counters") or {}
        unread_messages = int(counters.get("requester_unread_messages") or 0)
        unread_tools = int(counters.get("requester_unread_tool_calls") or 0)
        optimistic_read_until = int(self._optimistic_read_event_id.get(ticket_id, 0))
        if unread_messages <= 0 and unread_tools <= 0:
            self._optimistic_read_event_id.pop(ticket_id, None)
        elif optimistic_read_until > 0:
            unread_anchor = self._latest_requester_read_event_id(ticket, messages, events)
            if unread_anchor > 0 and unread_anchor <= optimistic_read_until:
                unread_messages = 0
                unread_tools = 0
        status_suffix_parts: List[str] = []
        if unread_messages > 0:
            status_suffix_parts.append(f"сообщения: {unread_messages}")
        if unread_tools > 0:
            status_suffix_parts.append(f"вызовы: {unread_tools}")
        if bool((ticket.get("presence") or {}).get("support_online")):
            status_suffix_parts.append("поддержка онлайн")
        status_suffix = ""
        if status_suffix_parts:
            status_suffix = " • Непрочитано " + ", ".join(status_suffix_parts)
        safe_code = self._escape_html(str(code))
        safe_title = self._escape_html(str(title))
        info_html = f"Обращение <a href='copy_ticket_code:{safe_code}'>#{safe_code}</a><br>{safe_title}"
        status_text = f"Статус обращения: {ticket_status_label(status)}{status_suffix}"
        status_style = (
            f"font-weight: 700; padding: 10px 14px; border-radius: 14px; background: {status_bg}; color: {status_fg};"
        )
        meta_html = self._build_ticket_meta_html(ticket)
        self.ticket_info_label.setText(info_html)
        self.ticket_status_top.setText(status_text)
        self.ticket_status_top.setStyleSheet(status_style)
        self.ticket_meta_label.setText(meta_html)
        self._refresh_top_pinned_info(ticket, messages)
        self._refresh_pinned_messages_label(ticket.get("ticket_id") or "")
        self._apply_ticket_background(status)

    def _build_timeline_items(self, ticket: dict, messages: List[dict], events: List[dict]) -> List[tuple[float, str, dict]]:
        requester_name = ticket.get("requester_display_name") or "Пользователь"
        requester_profile = ticket.get("requester_profile") or {}
        requester_full_name = (
            requester_profile.get("full_name")
            or ticket.get("requester_display_name")
            or "Пользователь"
        )
        assignee_name = ticket.get("assignee_id") or "Поддержка"
        message_index: Dict[str, dict] = {
            str(msg.get("message_id") or ""): msg
            for msg in messages
            if str(msg.get("message_id") or "").strip()
        }
        items: List[tuple[float, str, dict]] = []
        for message in messages:
            ts = message.get("ts")
            text = (message.get("text") or "").strip()
            sender_kind = message_visual_role(message)
            sender = requester_name if sender_kind == "self" else assignee_name if sender_kind == "support" else "Система"
            reply_to = self._resolve_reply_reference(
                message.get("reply_to") or ((message.get("metadata") or {}).get("reply_to")),
                message_index,
            )
            message_context = {
                "message_id": message.get("message_id"),
                "preview": text or " ".join(self._message_attachment_labels(message)),
                "sender_role": message.get("from_role"),
                "sender_display_name": requester_full_name if sender_kind == "self" else sender,
                "ts": ts,
            }
            items.append(
                (
                    self._ts_sort_value(ts),
                    "msg",
                    {
                        "bubble_role": "self" if sender_kind == "self" else "support" if sender_kind == "support" else "event",
                        "sender": requester_full_name if sender_kind == "self" else sender,
                        "text": text or "Вложение",
                        "attachments": self._message_attachment_labels(message),
                        "ts_text": self._format_ts(ts),
                        "menu_text": text or " ".join(self._message_attachment_labels(message)),
                        "reply_to": reply_to,
                        "message_context": message_context,
                    },
                )
            )
        _HIDDEN = frozenset({
            "chat_message", "job_started", "job_running", "job_succeeded", "job_completed",
            "chat_session", "chat_ended", "event_delivered", "tool_response", "routing_applied",
            "initial_message_sent_to_agent", "initial_message_pending_delivery", "initial_message_send_failed",
            "no_active_job", "message_read",
        })
        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        for event in merged_events:
            ev_type = event.get("type") or event.get("event_type") or ""
            if ev_type in _HIDDEN:
                continue
            ts = event.get("ts")
            line = self._format_event_text(event)
            items.append(
                (
                    self._ts_sort_value(ts),
                    "event",
                    {
                        "bubble_role": "event",
                        "sender": "",
                        "text": f"⚙ {line}",
                        "attachments": [],
                        "ts_text": self._format_ts(ts),
                        "menu_text": "",
                    },
                )
            )
        items.sort(key=lambda x: x[0])
        return items

    @staticmethod
    def _append_contains_incoming_support_items(items: List[tuple[float, str, dict]]) -> bool:
        return any(
            item_type == "msg" and isinstance(payload, dict) and payload.get("bubble_role") == "support"
            for _sort_key, item_type, payload in items
        )

    def _update_ticket_detail_ui(self, ticket: dict, messages: List[dict], events: List[dict]) -> None:
        if self._bubble_menu_open:
            self._pending_ticket_snapshot = (dict(ticket), list(messages), list(events))
            return

        timeline_sig = self._build_timeline_signature(ticket, messages, events)
        header_sig = self._detail_header_signature(ticket, messages)

        if timeline_sig == self._last_timeline_html and header_sig == self._last_detail_header_sig:
            if (self._follow_latest_messages or self._force_scroll_to_latest_on_next_render) and not self._is_timeline_near_bottom(12):
                self._restore_timeline_scroll(0, 0, True)
            self._maybe_mark_ticket_read(ticket, messages, events)
            return

        header_changed = header_sig != self._last_detail_header_sig
        timeline_changed = timeline_sig != self._last_timeline_html

        if header_changed:
            self._last_detail_header_sig = header_sig
            self._apply_ticket_detail_header(ticket, messages, events)

        self._maybe_prompt_resolution_confirmation(ticket)

        if not timeline_changed:
            self._pending_ticket_snapshot = None
            self._maybe_mark_ticket_read(ticket, messages, events)
            return

        items = self._build_timeline_items(ticket, messages, events)
        item_signatures = self._timeline_item_signatures(items)
        if item_signatures == self._last_timeline_item_signatures:
            self._last_timeline_html = timeline_sig
            self._pending_ticket_snapshot = None
            self._refresh_jump_to_latest_button()
            self._maybe_mark_ticket_read(ticket, messages, events)
            return

        scroll_bar = self.timeline_scroll.verticalScrollBar()
        previous_value = scroll_bar.value()
        previous_max = scroll_bar.maximum()
        previous_bottom_gap = max(previous_max - previous_value, 0)
        force_to_bottom = self._force_scroll_to_latest_on_next_render
        append_only = self._can_incrementally_append_timeline(
            self._last_timeline_item_signatures,
            item_signatures,
        )
        prepend_only = self._can_incrementally_prepend_timeline(
            self._last_timeline_item_signatures,
            item_signatures,
        )
        if append_only:
            appended_items = items[len(self._last_timeline_item_signatures):]
            if self._append_contains_incoming_support_items(appended_items) and (
                self._follow_latest_messages or previous_max <= 0 or previous_bottom_gap <= 120
            ):
                force_to_bottom = True
        stick_to_bottom = force_to_bottom or self._follow_latest_messages or self._is_timeline_near_bottom(40)
        self.timeline_scroll.setUpdatesEnabled(False)
        try:
            if append_only:
                self._append_timeline_widgets(items[len(self._last_timeline_item_signatures):])
                self._apply_timeline_scroll(previous_value, previous_bottom_gap, stick_to_bottom)
            elif prepend_only:
                prepend_count = len(item_signatures) - len(self._last_timeline_item_signatures)
                self._prepend_timeline_widgets(items[:prepend_count])
                self._apply_prepend_timeline_scroll(previous_value, previous_max)
            else:
                self._render_timeline_widgets(items)
                self._apply_timeline_scroll(previous_value, previous_bottom_gap, stick_to_bottom)
        finally:
            self.timeline_scroll.setUpdatesEnabled(True)
        self._last_timeline_html = timeline_sig
        self._last_timeline_item_signatures = item_signatures
        if force_to_bottom:
            self._force_scroll_to_latest_on_next_render = False
        self._pending_ticket_snapshot = None
        if prepend_only:
            self._restore_prepend_timeline_scroll(previous_value, previous_max)
        else:
            self._restore_timeline_scroll(previous_value, previous_bottom_gap, stick_to_bottom)
        self._refresh_jump_to_latest_button()
        self._schedule_fill_viewport_with_history()
        self._maybe_mark_ticket_read(ticket, messages, events)

    def _support_presence_text(self, ticket: dict) -> str:
        presence = ticket.get("presence") or {}
        if bool(presence.get("support_online")):
            return "онлайн"
        last_seen = self._format_ts(presence.get("support_last_seen_at"))
        if last_seen:
            return f"офлайн, последний пинг {last_seen}"
        return "офлайн"

    def _build_ticket_meta_html(self, ticket: dict) -> str:
        requester = ticket.get("requester_display_name") or "Пользователь"
        profile = ticket.get("requester_profile") or {}
        location = " ".join(
            part for part in (profile.get("building"), profile.get("room")) if part
        ).strip() or "—"
        rows = [
            ("Пользователь", requester),
            ("ФИО", profile.get("full_name") or "—"),
            ("Кабинет", location),
            ("Телефон", profile.get("phone") or "—"),
            ("Приоритет", ticket.get("priority_class") or ticket.get("priority") or "—"),
            ("Очередь", ticket.get("queue_code") or ticket.get("queue_id") or "—"),
            ("Исполнитель", ticket.get("assignee_id") or "Не назначен"),
            ("Поддержка", self._support_presence_text(ticket)),
            ("Создан", self._format_ts(ticket.get("created_at")) or "—"),
            ("Обновлён", self._format_ts(ticket.get("updated_at")) or "—"),
            ("Решён", self._format_ts(ticket.get("resolved_at")) or "—"),
            ("Закрыт", self._format_ts(ticket.get("closed_at")) or "—"),
            ("Описание", (ticket.get("description") or "—").replace("\n", " ")),
        ]
        rows.insert(5, ("Ответить должны до", self._format_ts(ticket.get("first_response_due_at")) or "-"))
        rows.insert(6, ("Решение ожидается до", self._format_ts(ticket.get("resolution_due_at")) or "-"))
        rows.extend(ticket_request_form_summary_rows(ticket))
        return "".join(
            f"<div style='margin-bottom:8px; font-size:{theme.BODY_PT}pt; line-height:1.5;'>"
            f"<span style='color:{theme.TEXT_MUTED}; font-weight:600;'>{self._escape_html(label)}:</span> "
            f"<span style='color:{theme.TEXT_PRIMARY};'>{self._escape_html(str(value))}</span></div>"
            for label, value in rows
        )

    def _message_attachment_labels(self, message: dict) -> List[str]:
        attachments = message.get("attachments") or []
        attachment_refs = message.get("attachment_refs") or []
        labels: List[str] = []
        for item in attachments[:5]:
            if not isinstance(item, dict):
                continue
            label = item.get("name") or item.get("artifact_id") or item.get("mime_type") or "Вложение"
            mime = str(item.get("mime_type") or "").lower()
            prefix = "📷 " if mime.startswith("image/") else "📎 "
            labels.append(f"{prefix}{label}")
        if not labels and attachment_refs:
            labels = [f"📎 {ref}" for ref in attachment_refs[:5]]
        return labels

    def _resolve_reply_reference(self, raw_reply: Optional[dict], message_index: Optional[Dict[str, dict]] = None) -> Optional[dict]:
        if not isinstance(raw_reply, dict):
            return None
        parent_message_id = str(raw_reply.get("parent_message_id") or "").strip()
        preview = str(raw_reply.get("preview") or raw_reply.get("target_preview") or "").strip()
        sender_role = str(raw_reply.get("sender_role") or raw_reply.get("from_role") or "").strip().lower()
        sender_display_name = str(raw_reply.get("sender_display_name") or raw_reply.get("sender") or "").strip()
        ts = str(raw_reply.get("ts") or raw_reply.get("target_ts") or "").strip()
        if message_index and parent_message_id and parent_message_id in message_index:
            source = message_index[parent_message_id]
            preview = preview or str(source.get("text") or "").strip()
            sender_role = sender_role or str(source.get("from_role") or "").strip().lower()
            sender_display_name = sender_display_name or str(source.get("sender_display_name") or "").strip()
            ts = ts or str(source.get("ts") or "").strip()
        if not preview and not parent_message_id:
            return None
        if not sender_display_name:
            if sender_role in {"support", "admin"}:
                sender_display_name = "Поддержка"
            elif sender_role in {"user", "requester", "agent"}:
                sender_display_name = "Вы"
            else:
                sender_display_name = "Сообщение"
        return {
            "parent_message_id": parent_message_id,
            "preview": preview[:280],
            "sender_role": sender_role,
            "sender_display_name": sender_display_name,
            "ts": ts,
        }

    def _build_timeline_signature(self, ticket: dict, messages: List[dict], events: List[dict]) -> str:
        merged_events = list(events) + self.local_action_buffer.get(self.active_ticket_id, [])
        payload = {
            "ticket_id": ticket.get("ticket_id"),
            "ticket_status": ticket.get("status"),
            "ticket_updated_at": ticket.get("updated_at"),
            "messages": [
                {
                    "id": msg.get("message_id"),
                    "ts": msg.get("ts"),
                    "text": msg.get("text"),
                    "from_role": msg.get("from_role"),
                    "attachments": msg.get("attachments"),
                    "attachment_refs": msg.get("attachment_refs"),
                    "reply_to": msg.get("reply_to") or ((msg.get("metadata") or {}).get("reply_to")),
                }
                for msg in messages
            ],
            "events": merged_events,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _timeline_item_signature(item: tuple[float, str, dict]) -> str:
        sort_value, kind, payload = item
        return json.dumps(
            {
                "sort": sort_value,
                "kind": kind,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    def _timeline_item_signatures(self, items: List[tuple[float, str, dict]]) -> List[str]:
        return [self._timeline_item_signature(item) for item in items]

    @staticmethod
    def _can_incrementally_append_timeline(previous_signatures: List[str], new_signatures: List[str]) -> bool:
        if not previous_signatures or len(new_signatures) <= len(previous_signatures):
            return False
        return list(new_signatures[: len(previous_signatures)]) == list(previous_signatures)

    @staticmethod
    def _can_incrementally_prepend_timeline(previous_signatures: List[str], new_signatures: List[str]) -> bool:
        if not previous_signatures or len(new_signatures) <= len(previous_signatures):
            return False
        return list(new_signatures[-len(previous_signatures):]) == list(previous_signatures)

    def _restore_timeline_scroll(
        self,
        previous_value: int,
        previous_bottom_gap: int,
        stick_to_bottom: bool,
    ) -> None:
        self._timeline_scroll_restore_revision += 1
        revision = self._timeline_scroll_restore_revision

        def apply_scroll() -> None:
            if revision != self._timeline_scroll_restore_revision:
                return
            self._apply_timeline_scroll(previous_value, previous_bottom_gap, stick_to_bottom)

        QTimer.singleShot(0, apply_scroll)
        QTimer.singleShot(30, apply_scroll)

    def _restore_prepend_timeline_scroll(
        self,
        previous_value: int,
        previous_max: int,
    ) -> None:
        self._timeline_scroll_restore_revision += 1
        revision = self._timeline_scroll_restore_revision

        def apply_scroll() -> None:
            if revision != self._timeline_scroll_restore_revision:
                return
            self._apply_prepend_timeline_scroll(previous_value, previous_max)

        QTimer.singleShot(0, apply_scroll)
        QTimer.singleShot(30, apply_scroll)

    def _apply_timeline_scroll(
        self,
        previous_value: int,
        previous_bottom_gap: int,
        stick_to_bottom: bool,
    ) -> None:
        scroll_bar = self.timeline_scroll.verticalScrollBar()
        self._suspend_scroll_tracking = True
        try:
            if stick_to_bottom:
                scroll_bar.setValue(scroll_bar.maximum())
            else:
                target = max(scroll_bar.maximum() - previous_bottom_gap, 0)
                if target == 0 and previous_value > 0:
                    target = min(previous_value, scroll_bar.maximum())
                scroll_bar.setValue(target)
        finally:
            self._suspend_scroll_tracking = False
        if stick_to_bottom and self._is_timeline_near_bottom(12):
            self._force_scroll_to_latest_on_next_render = False
        self._refresh_jump_to_latest_button()

    def _apply_prepend_timeline_scroll(
        self,
        previous_value: int,
        previous_max: int,
    ) -> None:
        scroll_bar = self.timeline_scroll.verticalScrollBar()
        new_max = scroll_bar.maximum()
        delta = max(new_max - previous_max, 0)
        self._suspend_scroll_tracking = True
        try:
            scroll_bar.setValue(min(previous_value + delta, new_max))
        finally:
            self._suspend_scroll_tracking = False
        self._refresh_jump_to_latest_button()

    def _is_timeline_near_bottom(self, threshold_px: int = 32) -> bool:
        scroll_bar = self.timeline_scroll.verticalScrollBar()
        return scroll_bar.maximum() <= 0 or scroll_bar.value() >= max(scroll_bar.maximum() - threshold_px, 0)

    def _refresh_jump_to_latest_button(self, *_args) -> None:
        if not hasattr(self, "jump_to_latest_btn"):
            return
        self.jump_to_latest_btn.setVisible(not self._is_timeline_near_bottom(40))

    def _on_timeline_scroll_changed(self, *_args) -> None:
        if self._suspend_scroll_tracking:
            return
        if len(_args) >= 2:
            self._refresh_jump_to_latest_button()
            return
        scroll_value = int(_args[0]) if _args else self.timeline_scroll.verticalScrollBar().value()
        self._follow_latest_messages = self._is_timeline_near_bottom(40)
        self._force_scroll_to_latest_on_next_render = False
        self._refresh_jump_to_latest_button()
        if (
            scroll_value <= TICKET_HISTORY_TOP_THRESHOLD_PX
            and getattr(self, "active_ticket_id", None)
            and getattr(self, "_has_older_history", False)
            and not getattr(self, "_loading_older_history", False)
        ):
            self._load_older_history_async()

    def _ensure_timeline_bottom_follow(self) -> None:
        self._follow_latest_messages = True
        self._force_scroll_to_latest_on_next_render = True
        self._restore_timeline_scroll(0, 0, True)
        QTimer.singleShot(80, lambda: self._restore_timeline_scroll(0, 0, True))
        QTimer.singleShot(180, lambda: self._restore_timeline_scroll(0, 0, True))
        QTimer.singleShot(320, lambda: self._restore_timeline_scroll(0, 0, True))

    def _jump_to_latest_messages(self) -> None:
        self._ensure_timeline_bottom_follow()

    def _clear_timeline_widgets(self) -> None:
        self._timeline_bubbles.clear()
        if self.timeline_layout.count() == 0:
            self.timeline_layout.addStretch(1)
        while self.timeline_layout.count() > 1:
            item = self.timeline_layout.takeAt(1)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                # Важно сразу убрать из иерархии, иначе до следующего цикла event loop
                # старые виджеты могут визуально перекрывать новые.
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    sub_item = child_layout.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget is not None:
                        sub_widget.setParent(None)
                        sub_widget.deleteLater()

    def _message_bubble_max_width(self) -> int:
        viewport_width = max(self.timeline_scroll.viewport().width(), 480)
        return int(viewport_width * 0.68)

    def _create_timeline_row(self, bubble: MessageBubbleWidget, alignment: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        bubble.setMaximumWidth(self._message_bubble_max_width())
        self._timeline_bubbles.append(bubble)

        if alignment == "right":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        elif alignment == "center":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        return row

    def _append_timeline_widgets(self, items: List[tuple[float, str, dict]]) -> None:
        for _sort_value, kind, payload in items:
            bubble = MessageBubbleWidget(
                self,
                payload.get("bubble_role", "event"),
                payload.get("sender", ""),
                payload.get("text", ""),
                payload.get("ts_text", ""),
                payload.get("attachments", []),
                payload.get("menu_text", ""),
                payload.get("reply_to"),
                payload.get("message_context"),
            )
            alignment = "center" if kind == "event" else ("right" if payload.get("bubble_role") == "support" else "left")
            self.timeline_layout.addWidget(self._create_timeline_row(bubble, alignment))

    def _prepend_timeline_widgets(self, items: List[tuple[float, str, dict]]) -> None:
        insert_index = 1 if self.timeline_layout.count() > 0 else 0
        for _sort_value, kind, payload in reversed(items):
            bubble = MessageBubbleWidget(
                self,
                payload.get("bubble_role", "event"),
                payload.get("sender", ""),
                payload.get("text", ""),
                payload.get("ts_text", ""),
                payload.get("attachments", []),
                payload.get("menu_text", ""),
                payload.get("reply_to"),
                payload.get("message_context"),
            )
            alignment = "center" if kind == "event" else ("right" if payload.get("bubble_role") == "support" else "left")
            self.timeline_layout.insertWidget(insert_index, self._create_timeline_row(bubble, alignment))

    def _render_timeline_widgets(self, items: List[tuple[float, str, dict]]) -> None:
        self._clear_timeline_widgets()
        if not items:
            empty = MessageBubbleWidget(self, "event", "", "Пока нет сообщений.", "", [])
            self.timeline_layout.addWidget(self._create_timeline_row(empty, "center"))
            return

        self._append_timeline_widgets(items)

    def _update_timeline_bubble_widths(self) -> None:
        max_width = self._message_bubble_max_width()
        for bubble in self._timeline_bubbles:
            bubble.setMaximumWidth(max_width)

    def _maybe_prompt_resolution_confirmation(self, ticket: dict) -> None:
        if not ticket or not can_user_confirm_close(ticket):
            self.resolution_message_widget.hide()
            return
        ticket_id = str(ticket.get("ticket_id") or "")
        prompt_key = f"{ticket_id}:{ticket.get('resolved_at') or ticket.get('updated_at') or 'resolved'}"
        if not ticket_id or prompt_key in self._resolution_prompt_keys or self._resolution_prompt_open_for == ticket_id:
            return
        self._resolution_prompt_keys.add(prompt_key)
        self._resolution_prompt_open_for = ticket_id

        self.resolution_message_widget.show()

    def _ts_sort_value(self, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = normalize_iso_ts(value)
            if not raw:
                return 0.0
            try:
                return float(raw)
            except ValueError:
                pass
            try:
                return datetime.fromisoformat(raw).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    def _format_ts(self, value) -> str:
        return format_ts_short(value)

    @staticmethod
    def _escape_html(s: str) -> str:
        if not s:
            return ""
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _format_event_text(self, event: dict) -> str:
        event_type = event.get("type") or event.get("event_type") or "event"
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        tool_name = str(event.get("tool_name") or payload.get("tool_name") or "").strip()
        action = str(event.get("action") or payload.get("action") or "").strip()
        status = str(event.get("status") or payload.get("status") or "").strip().lower()
        message = str(event.get("message") or payload.get("message") or payload.get("description") or "").strip()
        error = str(payload.get("error") or payload.get("error_message") or "").strip()

        tool_label = self._friendly_tool_name(tool_name or action)
        status_label = self._friendly_status_label(status)

        if event_type == "tool_requested":
            return f"Запрошено действие {tool_label}."
        if event_type == "tool_started":
            return f"Запущено действие {tool_label}."
        if event_type == "tool_running":
            return message or f"Действие {tool_label} выполняется."
        if event_type == "tool_finished":
            if error:
                return f"Действие {tool_label} завершилось с ошибкой: {error}"
            if status_label:
                return f"Действие {tool_label} завершено: {status_label}."
            return f"Действие {tool_label} завершено."
        if event_type == "tool_result":
            if message:
                return f"Результат действия {tool_label}: {message}"
            return f"Получен результат действия {tool_label}."
        if event_type == "collect_progress":
            return message or f"Идёт выполнение действия {tool_label}."
        if event_type == "consent_required":
            return f"Нужно подтвердить действие {tool_label}."
        if event_type == "notification":
            return message or "Получено уведомление."
        if event_type == "module_observation":
            return message or f"Получено сообщение от модуля {tool_label}."
        if event_type == "agent_action":
            if action:
                return f"Агент выполняет действие: {self._friendly_action_label(action)}."
            return message or "Агент выполняет действие."

        if message:
            return message
        if action:
            return f"Событие: {self._friendly_action_label(action)}."
        return self._friendly_action_label(event_type)

    @staticmethod
    def _friendly_status_label(status: str) -> str:
        mapping = {
            "ok": "успешно",
            "success": "успешно",
            "succeeded": "успешно",
            "done": "успешно",
            "finished": "завершено",
            "running": "выполняется",
            "pending": "ожидание",
            "queued": "в очереди",
            "failed": "ошибка",
            "error": "ошибка",
            "denied": "отклонено",
            "cancelled": "отменено",
            "canceled": "отменено",
        }
        return mapping.get((status or "").strip().lower(), status or "")

    @staticmethod
    def _friendly_tool_name(name: str) -> str:
        raw = (name or "").strip()
        if not raw:
            return "«действие»"
        mapping = {
            "screen.collect": "«Скриншот экрана»",
            "screen.record": "«Запись экрана»",
            "screen.capture": "«Снимок экрана»",
        }
        return mapping.get(raw, f"«{raw}»")

    @staticmethod
    def _friendly_action_label(action: str) -> str:
        raw = (action or "").strip()
        if not raw:
            return "действие"
        mapping = {
            "prepare_screen_capture": "подготовка скриншота",
            "screen_capture_done": "скриншот готов",
            "prepare_screen_recording": "подготовка записи экрана",
            "screen_recording_done": "запись экрана завершена",
        }
        return mapping.get(raw, raw.replace("_", " "))

    def _on_create_ticket(self) -> None:
        if not self.has_active_profile():
            QMessageBox.warning(self, "Профиль обязателен", "Сначала заполните и выберите профиль инициатора.")
            self.open_profile_manager(start_new=True)
            return
        self._spawn_task(self._async_open_create_ticket_dialog())

    async def _async_open_create_ticket_dialog(self) -> None:
        self.create_ticket_btn.setEnabled(False)
        try:
            await self._async_refresh_ticket_form_pack()
            dialog = TicketCreateDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload = dialog.payload()
            await self._async_create_ticket(payload)
        finally:
            self.create_ticket_btn.setEnabled(True)

    @staticmethod
    def _attachment_kind_for_file(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            return "screenshot"
        if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
            return "screen_recording"
        return "file"

    async def _async_send_created_ticket_attachments(
        self,
        ticket_id: str,
        files: List[str],
        trace_parent_action_id: Optional[str] = None,
    ) -> None:
        refs: List[str] = []
        for file_path in files:
            uploaded = await self.ticket_client.upload_attachment(
                ticket_id,
                file_path,
                kind=self._attachment_kind_for_file(file_path),
                trace_parent_action_id=trace_parent_action_id,
            )
            artifact_id = uploaded.get("artifact_id")
            if artifact_id:
                refs.append(artifact_id)
        if not refs:
            return
        await self.ticket_client.send_message(
            ticket_id,
            "Материалы к заявке",
            from_role="user",
            attachment_refs=refs,
            trace_parent_action_id=trace_parent_action_id,
        )

    async def _async_create_ticket(
        self,
        payload: dict,
        *,
        show_success_dialog: bool = True,
        raise_errors: bool = False,
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        description = payload.get("description", "").strip()
        if not description:
            if raise_errors:
                raise ValueError("Опишите проблему")
            QMessageBox.warning(self, "Ошибка", "Опишите проблему")
            return {}

        urgency = bool(payload.get("urgency"))
        importance = bool(payload.get("importance"))
        urgency_reason = payload.get("urgency_reason") or ("Срочно" if urgency else "Несрочно")
        importance_reason = payload.get("importance_reason") or ("Важно" if importance else "Неважно")
        requester_profile, display_name = self._current_requester_payload()
        attachment_paths = list(payload.get("attachment_paths") or [])
        action_id = trace_parent_action_id or get_action_trace_recorder().context(
            source="gui_user",
            action="ticket.create",
            category="ticket",
            ticket_id=self.active_ticket_id,
        ).action_id

        try:
            result = await self.ticket_client.create_ticket(
                description=description,
                title=str(payload.get("title") or "Support Request"),
                tags=[],
                requester_profile=requester_profile,
                user_display_name=display_name,
                urgency=urgency,
                importance=importance,
                urgency_reason=urgency_reason,
                importance_reason=importance_reason,
                form_key=payload.get("form_key"),
                request_template_key=payload.get("request_template_key"),
                form_pack_key=payload.get("form_pack_key"),
                form_pack_version=payload.get("form_pack_version"),
                form_payload=payload.get("form_payload"),
                diagnostic_consent=payload.get("diagnostic_consent"),
                ticket_type=payload.get("ticket_type"),
                trace_parent_action_id=action_id,
            )
            if result.get("status") != "ok":
                raise RuntimeError(str(result))

            ticket = result.get("ticket", {})
            self.active_ticket_id = ticket.get("ticket_id")
            if self.active_ticket_id and attachment_paths:
                await self._async_send_created_ticket_attachments(
                    str(self.active_ticket_id),
                    attachment_paths,
                    trace_parent_action_id=action_id,
                )
            self._last_timeline_html = None
            self._last_detail_header_sig = None
            self._pending_ticket_snapshot = None
            self._reset_active_ticket_cache()
            self._ticket_detail_timer.start(TICKET_DETAIL_POLL_INTERVAL_MS)
            await self._async_refresh_ticket_list()
            self._refresh_ticket_detail_async()
            self._show_chat_screen()
            self._ensure_timeline_bottom_follow()

            code = result.get("public_access_code") or "—"
            url = result.get("public_access_url") or ""
            message = build_post_create_process_summary(ticket, public_access_code=str(code))
            if url:
                message = f"{message}\n\nСсылка для просмотра: {url}"
            if show_success_dialog:
                QMessageBox.information(self, "Обращение создано", message)
            return result
        except Exception as exc:
            logger.error(f"Ошибка создания обращения: {exc}")
            if raise_errors:
                raise
            QMessageBox.critical(self, "Ошибка", str(exc))
            return {}

    def _on_open_ticket(self) -> None:
        cur = self.tickets_list.currentIndex()
        if not cur.isValid() or self._tickets_model is None:
            return
        ticket = self._tickets_model.ticket_at_row(cur.row())
        if not ticket:
            return
        self.active_ticket_id = ticket.get("ticket_id")
        self._last_timeline_html = None
        self._last_detail_header_sig = None
        self._pending_ticket_snapshot = None
        self._reset_active_ticket_cache()
        self._ensure_timeline_bottom_follow()
        self._ticket_detail_timer.start(TICKET_DETAIL_POLL_INTERVAL_MS)
        self._refresh_ticket_detail_async()
        self._show_chat_screen()

    def _on_send(self) -> None:
        if not self.active_ticket_id:
            return
        text = self.input_line.text().strip()
        if not text:
            return
        self._spawn_task(self._async_send_message(text))

    async def _async_send_message(self, text: str, *, trace_parent_action_id: Optional[str] = None) -> None:
        try:
            self.send_btn.setEnabled(False)
            action_id = trace_parent_action_id or get_action_trace_recorder().context(
                source="gui_user",
                action="ticket.message.send",
                category="message",
                ticket_id=self.active_ticket_id,
            ).action_id
            metadata = None
            reply_to = None
            if self._reply_target:
                reply_to = {
                    "parent_message_id": self._reply_target.get("message_id"),
                    "preview": self._reply_target.get("preview", ""),
                    "sender_role": self._reply_target.get("sender_role"),
                    "sender_display_name": self._reply_target.get("sender_display_name"),
                    "target_ts": self._reply_target.get("ts"),
                }
                metadata = {
                    PINNED_STUB_META_KEY: {
                        "source": "agent_gui_stub",
                        "target_preview": self._reply_target.get("preview", ""),
                        "target_ts": self._reply_target.get("ts"),
                    }
                }
            await self.ticket_client.send_message(
                self.active_ticket_id,
                text,
                from_role="user",
                metadata=metadata,
                reply_to=reply_to,
                trace_parent_action_id=action_id,
            )
            self.input_line.clear()
            self._clear_reply_stub()
            self._refresh_ticket_detail_async()
            self._ensure_timeline_bottom_follow()
        except Exception as exc:
            logger.error(f"Ошибка отправки сообщения: {exc}")
            QMessageBox.critical(self, "Ошибка", str(exc))
        finally:
            self.send_btn.setEnabled(True)

    def _on_attach_files(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Обращение", "Сначала откройте обращение.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите вложения")
        if not files:
            return
        self._spawn_task(self._async_attach_files(files))

    def _on_attach_photo(self) -> None:
        self._pick_and_attach_files("Выберите фото", "Изображения (*.png *.jpg *.jpeg *.bmp *.webp)")

    def _on_attach_document(self) -> None:
        self._pick_and_attach_files(
            "Выберите документ",
            "Документы (*.pdf *.doc *.docx *.txt *.rtf *.xls *.xlsx *.csv *.ppt *.pptx)"
        )

    def _on_attach_any_file(self) -> None:
        self._pick_and_attach_files("Выберите файл", "Все файлы (*.*)")

    def _pick_and_attach_files(self, title: str, file_filter: str) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Обращение", "Сначала откройте обращение.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, title, "", file_filter)
        if not files:
            return
        self._spawn_task(self._async_attach_files(files))

    async def _async_attach_files(self, files: List[str], *, trace_parent_action_id: Optional[str] = None) -> None:
        refs: List[str] = []
        try:
            self.tool_status_label.setText("Загружаю вложения...")
            action_id = trace_parent_action_id or get_action_trace_recorder().context(
                source="gui_user",
                action="ticket.attach_files",
                category="attachment",
                ticket_id=self.active_ticket_id,
            ).action_id
            for file_path in files:
                ext = Path(file_path).suffix.lower()
                kind = "file"
                if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                    kind = "screenshot"
                elif ext in {".mp4", ".mov", ".mkv", ".avi"}:
                    kind = "screen_recording"
                uploaded = await self.ticket_client.upload_attachment(
                    self.active_ticket_id,
                    file_path,
                    kind=kind,
                    trace_parent_action_id=action_id,
                )
                artifact_id = uploaded.get("artifact_id")
                if artifact_id:
                    refs.append(artifact_id)
            if not refs:
                self.tool_status_label.setText("Нет загруженных файлов")
                return
            text = self.input_line.text().strip()
            if not text:
                text = "Вложение" if len(refs) == 1 else f"Вложения ({len(refs)})"
            reply_to = None
            metadata = None
            if self._reply_target:
                reply_to = {
                    "parent_message_id": self._reply_target.get("message_id"),
                    "preview": self._reply_target.get("preview", ""),
                    "sender_role": self._reply_target.get("sender_role"),
                    "sender_display_name": self._reply_target.get("sender_display_name"),
                    "target_ts": self._reply_target.get("ts"),
                }
                metadata = {
                    PINNED_STUB_META_KEY: {
                        "source": "agent_gui_stub",
                        "target_preview": self._reply_target.get("preview", ""),
                        "target_ts": self._reply_target.get("ts"),
                    }
                }
            await self.ticket_client.send_message(
                self.active_ticket_id,
                text,
                from_role="user",
                attachment_refs=refs,
                metadata=metadata,
                reply_to=reply_to,
                trace_parent_action_id=action_id,
            )
            self.input_line.clear()
            self._clear_reply_stub()
            self.tool_status_label.setText(f"Отправлено вложений: {len(refs)}")
            self._refresh_ticket_detail_async()
            self._ensure_timeline_bottom_follow()
        except Exception as exc:
            logger.error(f"Ошибка отправки вложений: {exc}")
            self.tool_status_label.setText("Ошибка отправки вложений")
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _on_send_screenshot(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Обращение", "Сначала откройте обращение.")
            return
        self._spawn_task(self._async_run_tool("screen.collect", {}, "Запрос на скриншот отправлен"))

    def _on_send_video(self) -> None:
        if not self.active_ticket_id:
            QMessageBox.information(self, "Обращение", "Сначала откройте обращение.")
            return
        self._spawn_task(
            self._async_run_tool(
                "screen.record",
                {"duration_sec": 60},
                "Запрос на запись видео отправлен",
            )
        )

    async def _async_run_tool(
        self,
        tool_name: str,
        params: dict,
        success_text: str,
        *,
        trace_parent_action_id: Optional[str] = None,
    ) -> None:
        try:
            self.tool_status_label.setText("Запускаю инструмент...")
            action_id = trace_parent_action_id or get_action_trace_recorder().context(
                source="gui_user",
                action="ticket.tool.run",
                category="tool",
                ticket_id=self.active_ticket_id,
                tool_name=tool_name,
            ).action_id
            await self.ticket_client.run_tool(
                device_id=self.device_id,
                ticket_id=self.active_ticket_id,
                tool_name=tool_name,
                params=params,
                trace_parent_action_id=action_id,
            )
            self.tool_status_label.setText(success_text)
            self._refresh_ticket_detail_async()
        except Exception as exc:
            logger.error(f"Ошибка запуска инструмента {tool_name}: {exc}")
            self.tool_status_label.setText(f"Ошибка {tool_name}")
            QMessageBox.warning(self, "Инструмент", str(exc))

    def _on_reject_resolution(self) -> None:
        self.resolution_message_widget.hide()
        QMessageBox.information(self, "Решение отклонено", "Вы можете продолжить переписку в обращении.")

    async def _async_close_ticket(self) -> None:
        try:
            action_id = get_action_trace_recorder().context(
                source="gui_user",
                action="ticket.confirm_resolution",
                category="ticket",
                ticket_id=self.active_ticket_id,
            ).action_id
            await self.ticket_client.close_ticket(
                self.active_ticket_id,
                reason="requester_confirmed_resolution",
                closed_by_role="user",
                trace_parent_action_id=action_id,
            )
            await self._async_refresh_ticket_list()
            await self._async_refresh_ticket_detail()
        except Exception as exc:
            logger.error(f"Ошибка закрытия тикета: {exc}")
            QMessageBox.critical(self, "Ошибка", str(exc))

    def add_local_event(self, ticket_id: str, event: dict) -> None:
        self.local_action_buffer.setdefault(ticket_id, []).append(event)
        if ticket_id == self.active_ticket_id:
            self._refresh_ticket_detail_async()

    def attach_to_job(self, job_id: str) -> None:
        self.current_job_id = job_id
        self.chatSessionChanged.emit(job_id or "")

    def append_event(self, event: dict, source: str = "agent") -> None:
        event_copy = dict(event or {})
        event_copy.setdefault("source", source)
        ticket_id = event_copy.get("ticket_id") or self.active_ticket_id
        if ticket_id:
            self.add_local_event(ticket_id, event_copy)

    def _stop_ticket_list_polling(self) -> None:
        if self._ticket_list_timer.isActive():
            self._ticket_list_timer.stop()
        self._cancel_pending_tasks()

    def _stop_ticket_detail_polling(self) -> None:
        if self._ticket_detail_timer.isActive():
            self._ticket_detail_timer.stop()
        self._cancel_pending_tasks()

    def _show_list_screen(self) -> None:
        if self._ticket_detail_timer.isActive():
            self._ticket_detail_timer.stop()
        if not self._ticket_list_timer.isActive() and not self._is_closing:
            self._ticket_list_timer.start(TICKET_LIST_POLL_INTERVAL_MS)
        self.listNavigationVisibilityChanged.emit(True)

    def _show_chat_screen(self) -> None:
        self.chat_screen.update()
        self.input_line.setFocus()
        if self.active_ticket_id:
            QTimer.singleShot(0, self._ensure_timeline_bottom_follow)
        self.listNavigationVisibilityChanged.emit(False)

    def _open_message_context_menu(self, global_pos, message_context: dict) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction("Копировать текст")
        reply_action = menu.addAction("Ответить")
        pin_action = menu.addAction("Закрепить сообщение")
        self._bubble_menu_open = True
        try:
            chosen = menu.exec(global_pos)
        finally:
            self._bubble_menu_open = False
        preview = str(message_context.get("preview") or "").strip()
        if chosen == copy_action:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(preview)
        elif chosen == reply_action:
            self._set_reply_target(message_context)
        elif chosen == pin_action:
            self._pin_selected_message(preview)
        if self._pending_ticket_snapshot:
            snapshot = self._pending_ticket_snapshot
            self._pending_ticket_snapshot = None
            QTimer.singleShot(0, lambda: self._update_ticket_detail_ui(*snapshot))

    def _set_reply_target(self, message_context: dict) -> None:
        if not self.active_ticket_id:
            return
        preview = str(message_context.get("preview") or "").strip()
        if not preview:
            QMessageBox.information(self, "Ответ", "Сначала выделите текст сообщения для ответа.")
            return
        preview = preview[:180]
        self._reply_target = {
            "message_id": str(message_context.get("message_id") or "").strip(),
            "preview": preview,
            "ts": message_context.get("ts") or datetime.now().isoformat(),
            "sender_role": str(message_context.get("sender_role") or "").strip().lower(),
            "sender_display_name": str(message_context.get("sender_display_name") or "").strip(),
        }
        author = self._reply_target.get("sender_display_name") or "сообщение"
        self.reply_stub_label.setText(f"Ответ на {author}: {preview}")
        self.reply_stub_label.show()
        self.input_line.setFocus()

    def _clear_reply_stub(self) -> None:
        self._reply_target = None
        self.reply_stub_label.hide()
        self.reply_stub_label.setText("")

    def _pin_selected_message(self, selected_text: str) -> None:
        ticket_id = self.active_ticket_id
        if not ticket_id:
            return
        preview = (selected_text or "").strip()
        if not preview:
            QMessageBox.information(self, "Закрепить", "Сначала выделите текст сообщения для закрепления.")
            return
        items = self._pinned_messages.setdefault(ticket_id, [])
        items.append({"text": preview[:220], "ts": datetime.now().isoformat()})
        self._refresh_pinned_messages_label(ticket_id)

    def _refresh_pinned_messages_label(self, ticket_id: str) -> None:
        items = self._pinned_messages.get(ticket_id) or []
        if not items:
            self.pinned_messages_widget.hide()
            return
        lines = [f"• {item.get('text', '')}" for item in items[-3:]]
        self.pinned_messages_label.setText("Закреплённые сообщения:\n" + "\n".join(lines))
        self.pinned_messages_widget.show()

    def _extract_public_access_code(self, ticket: dict, messages: List[dict]) -> str:
        code = str(ticket.get("public_access_code") or "").strip().upper()
        if code:
            return code
        for msg in reversed(messages or []):
            metadata = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
            candidate = str(metadata.get("public_access_code") or "").strip().upper()
            if candidate:
                return candidate
            text = str(msg.get("text") or "")
            if "Код авторизации" in text:
                match = re.search(r"\b[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}\b", text.upper())
                if match:
                    return match.group(0)
        return ""

    @staticmethod
    def _append_access_code_to_url(url: str, code: str) -> str:
        if not url or not code:
            return url or ""
        glue = "&" if "?" in url else "?"
        return f"{url}{glue}code={code}"

    def _refresh_top_pinned_info(self, ticket: dict, messages: List[dict]) -> None:
        full_code = self._extract_public_access_code(ticket, messages)
        code_hint = str(ticket.get("public_access_code_hint") or "").strip().upper()
        shown_code = full_code or (f"****{code_hint}" if code_hint else "—")
        raw_url = str(ticket.get("public_access_url") or "").strip()
        url = self._append_access_code_to_url(raw_url, full_code)
        if url:
            self.top_pinned_info.setText(
                f"Код авторизации: <a href='copy_auth_code:{self._escape_html(str(full_code or shown_code))}'><b>{self._escape_html(str(shown_code))}</b></a><br>"
                f"Ссылка на веб-обращение: <a href='{self._escape_html(str(url))}'>{self._escape_html(str(url))}</a>"
            )
        else:
            self.top_pinned_info.setText(
                f"Код авторизации: <a href='copy_auth_code:{self._escape_html(str(full_code or shown_code))}'><b>{self._escape_html(str(shown_code))}</b></a><br>Ссылка: —"
            )

    def _apply_ticket_background(self, status: str) -> None:
        normalized = str(status or "").strip().lower()
        bg = theme.CHAT_SCREEN_SOLID_OPEN
        if normalized == "resolved":
            bg = theme.CHAT_SCREEN_SOLID_RESOLVED
        elif normalized == "closed":
            bg = theme.CHAT_SCREEN_SOLID_CLOSED
        self.chat_screen.setStyleSheet(
            f"QWidget#ChatScreenRoot {{ background-color: {bg}; border-radius: 10px; }}"
        )
        pal = QPalette(self.chat_screen.palette())
        pal.setColor(QPalette.ColorRole.Window, QColor(bg))
        self.chat_screen.setPalette(pal)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_timeline_bubble_widths()

    def _clear_pinned_messages_for_active_ticket(self) -> None:
        if not self.active_ticket_id:
            return
        self._pinned_messages.pop(self.active_ticket_id, None)
        self._refresh_pinned_messages_label(self.active_ticket_id)

    def _on_ticket_code_clicked(self, link: str) -> None:
        prefix = "copy_ticket_code:"
        if not link.startswith(prefix):
            return
        code = link[len(prefix):].strip()
        if not code:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(code)
        QMessageBox.information(self, "Скопировано", f"Номер обращения скопирован: {code}")

    def _on_top_info_link_activated(self, link: str) -> None:
        prefix = "copy_auth_code:"
        if not link.startswith(prefix):
            return
        code = link[len(prefix):].strip()
        if not code or code == "—":
            QMessageBox.information(self, "Код", "Код авторизации пока недоступен.")
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(code)
        QMessageBox.information(self, "Скопировано", f"Код авторизации скопирован: {code}")
