"""Ticket form pack defaults, validation, and submission normalization."""

from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from playbooks.form_triggers import normalize_form_playbook_triggers
from tickets.workflow_profiles import DEFAULT_WORKFLOW_PROFILE


DEFAULT_TICKET_FORM_PACK_KEY = "request_forms"
DEFAULT_TICKET_FORM_PACK_VERSION = "1.0.0"
ALLOWED_FIELD_TYPES = {
    "text",
    "textarea",
    "select",
    "multi_select",
    "radio",
    "checkbox",
    "date",
    "datetime",
    "file",
    "number",
    "user_picker",
    "department_picker",
    "location_picker",
    "device_picker",
    "service_picker",
    "url",
    "phone",
    "email",
}
OPTION_FIELD_TYPES = {"select", "radio"}
OPTION_VALIDATED_FIELD_TYPES = OPTION_FIELD_TYPES | {
    "user_picker",
    "department_picker",
    "location_picker",
    "device_picker",
    "service_picker",
}
MULTI_SELECT_FIELD_TYPES = {"multi_select"}
KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
_TICKET_TYPE_BY_FORM_KIND = {
    "breakage": "incident",
    "printer": "incident",
    "network": "incident",
    "site_system": "incident",
    "mail_issue": "incident",
    "access": "access_request",
    "new_account": "access_request",
    "software_install": "service_request",
    "hardware_replacement": "service_request",
    "profile_completion_help": "service_request",
    "agent_binding_help": "service_request",
}
_SETUP_ASSISTANCE_FORM_KEYS = ("profile_completion_help", "agent_binding_help")
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
    "impact_scope": ["priority_impact"],
    "work_continuity": ["priority_urgency"],
    "business_importance": ["priority_importance"],
    "critical_service": ["passport_fact"],
    "public_service": ["visibility_public"],
}
_REQUEST_KIND_FALLBACK_LABELS = {
    "request": "Запрос",
    "incident": "Инцидент",
}
_ROUTING_BASE_FIELDS = (
    {"field": "ticket_type", "label": "Тип тикета", "source": "ticket"},
    {"field": "request_kind", "label": "request_kind формы", "source": "ticket"},
    {"field": "custom_fields.request_kind", "label": "custom_fields.request_kind", "source": "ticket"},
    {"field": "request_form_key", "label": "Ключ формы", "source": "ticket"},
    {"field": "request_form_title", "label": "Название формы", "source": "ticket"},
    {"field": "priority", "label": "Приоритет", "source": "ticket"},
    {"field": "priority_class", "label": "Класс приоритета", "source": "ticket"},
    {"field": "status", "label": "Статус", "source": "ticket"},
    {"field": "requester_id", "label": "ID инициатора", "source": "ticket"},
    {"field": "requester_display_name", "label": "Имя инициатора", "source": "ticket"},
    {"field": "building", "label": "Корпус инициатора", "source": "requester_profile"},
    {"field": "room", "label": "Кабинет инициатора", "source": "requester_profile"},
    {"field": "phone", "label": "Телефон инициатора", "source": "requester_profile"},
    {"field": "requester_profile.building", "label": "requester_profile.building", "source": "requester_profile"},
    {"field": "requester_profile.room", "label": "requester_profile.room", "source": "requester_profile"},
    {"field": "requester_profile.phone", "label": "requester_profile.phone", "source": "requester_profile"},
    {"field": "location", "label": "Локация устройства", "source": "device"},
    {"field": "device_type", "label": "Тип устройства", "source": "device"},
    {"field": "device_metadata.location", "label": "device_metadata.location", "source": "device"},
    {"field": "device_metadata.device_type", "label": "device_metadata.device_type", "source": "device"},
    {"field": "queue_id", "label": "Текущая очередь", "source": "ticket"},
    {"field": "category_id", "label": "Категория", "source": "ticket"},
    {"field": "service_id", "label": "Сервис", "source": "ticket"},
    {"field": "subcategory_id", "label": "Подкатегория", "source": "ticket"},
    {"field": "assignee_id", "label": "Ответственный", "source": "ticket"},
    {"field": "is_public_ticket", "label": "Публичный тикет", "source": "ticket"},
    {"field": "public_ticket_unbound", "label": "Публичный без привязки", "source": "ticket"},
)
_ROUTING_OPERATOR_OPTIONS = (
    {"value": "eq", "label": "Равно"},
    {"value": "ne", "label": "Не равно"},
    {"value": "in", "label": "В списке"},
    {"value": "nin", "label": "Не в списке"},
    {"value": "contains", "label": "Содержит"},
    {"value": "is_null", "label": "Пусто / не пусто"},
)
_TEMPLATE_DICT_FIELDS = (
    "policy_refs",
    "priority_policy",
    "routing_policy",
    "sla_policy",
    "approval_policy",
    "diagnostic_policy",
    "ola_policy",
    "closure_policy",
    "visibility_policy",
    "notification_policy",
    "reporting_policy",
    "field_aliases",
    "migration",
)
_TEMPLATE_INT_FIELDS = (
    "category_id",
    "service_id",
    "subcategory_id",
    "default_queue_id",
    "sla_policy_id",
)
_TEMPLATE_VERSION_FIELDS = (
    "request_template_version",
    "form_schema_version",
)
_TEMPLATE_STRING_FIELDS = (
    "form_schema_id",
    "workflow_profile_id",
    "priority_policy_ref",
    "routing_policy_ref",
    "sla_policy_ref",
    "ola_policy_ref",
    "approval_policy_ref",
    "diagnostic_policy_ref",
    "closure_policy_ref",
    "visibility_policy_ref",
    "notification_policy_ref",
    "reporting_policy_ref",
    "priority_policy_code",
    "routing_policy_code",
    "sla_policy_code",
    "ola_policy_code",
    "approval_policy_code",
    "diagnostic_policy_code",
    "closure_policy_code",
    "visibility_policy_code",
    "notification_policy_code",
    "reporting_policy_code",
    "field_migration_note",
)
_POLICY_REF_FIELDS = {
    "priority": ("priority_policy_ref", "priority_policy_code"),
    "routing": ("routing_policy_ref", "routing_policy_code"),
    "sla": ("sla_policy_ref", "sla_policy_code"),
    "ola": ("ola_policy_ref", "ola_policy_code"),
    "approval": ("approval_policy_ref", "approval_policy_code"),
    "diagnostic": ("diagnostic_policy_ref", "diagnostic_policy_code"),
    "closure": ("closure_policy_ref", "closure_policy_code"),
    "visibility": ("visibility_policy_ref", "visibility_policy_code"),
    "notification": ("notification_policy_ref", "notification_policy_code"),
    "reporting": ("reporting_policy_ref", "reporting_policy_code"),
}
_TEMPLATE_LIST_FIELDS = (
    "route_preview_examples",
    "process_preview_examples",
    "preview_samples",
)
_ON_BEHALF_DEFAULT_LABEL = "Проблема у другого сотрудника"
_ON_BEHALF_ALLOWED_SCOPES = frozenset(
    {
        "same_department_or_privileged",
        "same_department",
        "direct_reports",
        "exact_search_only",
        "privileged_only",
        "self_only",
        "any_employee",
    }
)
_ON_BEHALF_DIAGNOSTIC_TARGETS = frozenset({"affected_person_primary_agent"})
_ON_BEHALF_KNOWLEDGE_VISIBILITY = frozenset({"creator_only"})
_ON_BEHALF_SUPPORT_VISIBILITY = frozenset({"creator_and_affected"})
_ON_BEHALF_NO_PRIMARY_AGENT_BEHAVIORS = frozenset(
    {
        "allow_ticket_no_diagnostics",
        "manual_support_review",
        "block_create",
    }
)
_AVAILABILITY_BOOL_FIELDS = (
    "available_without_completed_profile",
    "available_without_agent_binding",
    "requires_manual_triage",
    "contact_required",
    "allowed_for_anonymous",
)
FIELD_ROLE_OPTIONS = (
    {"value": "routing_field", "label": "Routing field"},
    {"value": "priority_impact", "label": "Priority impact"},
    {"value": "priority_urgency", "label": "Priority urgency"},
    {"value": "priority_importance", "label": "Priority importance"},
    {"value": "diagnostic_input", "label": "Diagnostic input"},
    {"value": "approval_subject", "label": "Approval subject"},
    {"value": "closure_evidence", "label": "Closure evidence"},
    {"value": "reporting_dimension", "label": "Reporting dimension"},
    {"value": "passport_fact", "label": "Passport fact"},
    {"value": "visibility_public", "label": "Requester-visible fact"},
    {"value": "display_only", "label": "Display only"},
)
FIELD_ROLE_VALUES = frozenset(item["value"] for item in FIELD_ROLE_OPTIONS)
LEGACY_FIELD_ROLE_VALUES = frozenset({"priority_field", "sla_field", "approval_field"})
_ALLOWED_FIELD_ROLES = FIELD_ROLE_VALUES | LEGACY_FIELD_ROLE_VALUES


def build_default_priority_fields() -> list[dict[str, Any]]:
    return [
        {
            "key": "impact_scope",
            "label": "Кого затронула проблема?",
            "type": "radio",
            "required": True,
            "options": [
                {"value": "single_user", "label": "Только меня"},
                {"value": "group", "label": "Несколько человек"},
                {"value": "department", "label": "Весь отдел"},
                {"value": "building_or_org", "label": "Здание / организация / критичная система"},
            ],
        },
        {
            "key": "work_continuity",
            "label": "Можно ли продолжать работу?",
            "type": "radio",
            "required": True,
            "options": [
                {"value": "work_stopped_no_workaround", "label": "Нет, работа остановлена"},
                {"value": "partial_work", "label": "Можно работать частично"},
                {"value": "workaround_available", "label": "Есть обходной путь"},
                {"value": "inconvenience_only", "label": "Неудобно, но не блокирует"},
            ],
        },
        {
            "key": "business_importance",
            "label": "Есть важный срок или критичный процесс?",
            "type": "radio",
            "required": False,
            "options": [
                {"value": "normal", "label": "Нет, обычная рабочая ситуация"},
                {"value": "deadline", "label": "Есть важный срок"},
                {"value": "deadline_today", "label": "Сегодня / завтра крайний срок"},
                {"value": "security", "label": "ИБ / публичная услуга / критичный процесс"},
            ],
        },
        {
            "key": "critical_service",
            "label": "Затронута критичная система",
            "type": "checkbox",
            "required": False,
            "placeholder": "Да",
        },
        {
            "key": "public_service",
            "label": "Затронут прием граждан / публичная услуга",
            "type": "checkbox",
            "required": False,
            "placeholder": "Да",
        },
    ]


def _attach_default_priority_context(form: dict[str, Any]) -> None:
    existing_keys = {
        str(field.get("key") or "").strip()
        for field in form.get("fields") or []
        if isinstance(field, dict)
    }
    for field in build_default_priority_fields():
        if field["key"] not in existing_keys:
            form.setdefault("fields", []).append(deepcopy(field))
    form["priority_policy"] = deepcopy(DEFAULT_PRIORITY_POLICY)
    roles = deepcopy(DEFAULT_PRIORITY_FIELD_ROLES)
    roles.update(form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {})
    form["field_roles"] = roles


def infer_ticket_type_for_form(form_key: str | None, request_kind: str | None) -> str:
    """Backfill process type for old form packs that predate ticket_type."""
    normalized_request_kind = str(request_kind or "").strip().lower()
    normalized_form_key = str(form_key or "").strip().lower()
    return (
        _TICKET_TYPE_BY_FORM_KIND.get(normalized_request_kind)
        or _TICKET_TYPE_BY_FORM_KIND.get(normalized_form_key)
        or DEFAULT_WORKFLOW_PROFILE
    )


def build_default_ticket_form_pack() -> dict[str, Any]:
    """Built-in baseline catalog used until admins publish their own versions."""
    forms = [
        {
            "key": "profile_completion_help",
            "request_kind": "profile_completion_help",
            "title": "Помощь с заполнением профиля",
            "description": "Обращение в поддержку, если не получается заполнить профиль пользователя.",
            "availability_policy": {
                "available_without_completed_profile": True,
                "available_without_agent_binding": True,
                "requires_manual_triage": True,
                "contact_required": True,
            },
            "fields": [
                {"key": "contact_phone", "label": "Телефон для связи", "type": "phone", "required": True},
                {"key": "problem_details", "label": "Что не получается заполнить", "type": "textarea", "required": False},
            ],
        },
        {
            "key": "agent_binding_help",
            "request_kind": "agent_binding_help",
            "title": "Помощь с привязкой агента",
            "description": "Обращение в поддержку, если агент не привязывается к аккаунту или не показывает код.",
            "availability_policy": {
                "available_without_completed_profile": True,
                "available_without_agent_binding": True,
                "requires_manual_triage": True,
                "contact_required": True,
            },
            "fields": [
                {"key": "contact_phone", "label": "Телефон для связи", "type": "phone", "required": True},
                {"key": "agent_problem", "label": "Что происходит в агенте", "type": "textarea", "required": False},
            ],
        },
        {
            "key": "breakage",
            "request_kind": "breakage",
            "title": "Поломка",
            "description": "Проблема с оборудованием или рабочим местом.",
            "fields": [
                {"key": "asset_name", "label": "Что сломалось", "type": "text", "required": True, "placeholder": "Компьютер, монитор, МФУ"},
                {"key": "room", "label": "Кабинет", "type": "text", "required": False},
                {"key": "inventory_number", "label": "Инвентарный номер", "type": "text", "required": False},
            ],
        },
        {
            "key": "access",
            "request_kind": "access",
            "title": "Доступ",
            "description": "Выдача, изменение или восстановление доступа.",
            "fields": [
                {"key": "system_name", "label": "В какую систему", "type": "text", "required": True},
                {"key": "role_name", "label": "Какая роль", "type": "text", "required": False},
                {"key": "approver", "label": "Кто согласует", "type": "text", "required": False},
            ],
        },
        {
            "key": "software_install",
            "request_kind": "software_install",
            "title": "Установка ПО",
            "description": "Запрос на установку или обновление программного обеспечения.",
            "fields": [
                {"key": "software_name", "label": "Какое ПО", "type": "text", "required": True},
                {"key": "version", "label": "Нужная версия", "type": "text", "required": False},
                {"key": "license_owner", "label": "Есть лицензия / кто владелец", "type": "text", "required": False},
            ],
        },
        {
            "key": "hardware_replacement",
            "request_kind": "hardware_replacement",
            "title": "Замена техники",
            "description": "Замена ПК, периферии или другого рабочего оборудования.",
            "fields": [
                {"key": "replace_what", "label": "Что нужно заменить", "type": "text", "required": True},
                {"key": "room", "label": "Кабинет", "type": "text", "required": False},
                {"key": "reason", "label": "Причина замены", "type": "textarea", "required": False},
            ],
        },
        {
            "key": "printer",
            "request_kind": "printer",
            "title": "Печать / принтер",
            "description": "Проблемы с печатью, очередью или самим устройством.",
            "fields": [
                {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                {"key": "printer_model", "label": "Модель", "type": "text", "required": False},
                {"key": "printer_number", "label": "Номер принтера", "type": "text", "required": False},
            ],
        },
        {
            "key": "network",
            "request_kind": "network",
            "title": "Сеть / интернет",
            "description": "Проблемы с подключением, интернетом или сетью в кабинете.",
            "fields": [
                {"key": "room", "label": "Кабинет", "type": "text", "required": False},
                {"key": "pc_name", "label": "С какого ПК", "type": "text", "required": False},
                {
                    "key": "affected_scope",
                    "label": "У всех или у одного",
                    "type": "radio",
                    "required": False,
                    "options": [
                        {"value": "single", "label": "У одного"},
                        {"value": "multiple", "label": "У нескольких"},
                        {"value": "all", "label": "У всех"},
                    ],
                },
            ],
        },
        {
            "key": "site_system",
            "request_kind": "site_system",
            "title": "Сайт / система",
            "description": "Проблемы с внутренним сайтом, сервисом или бизнес-системой.",
            "fields": [
                {
                    "key": "issue_kind",
                    "label": "Тип проблемы",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "site_down", "label": "Сайт не открывается"},
                        {"value": "auth", "label": "Не удаётся войти"},
                        {"value": "functional", "label": "Ошибка в работе функции"},
                    ],
                },
                {"key": "system_name", "label": "Система / сайт", "type": "text", "required": True},
                {"key": "url", "label": "URL", "type": "text", "required": False, "visible_when": {"field": "issue_kind", "equals": "site_down"}},
                {"key": "pc_name", "label": "С какого ПК", "type": "text", "required": False, "visible_when": {"field": "issue_kind", "equals": "site_down"}},
                {
                    "key": "affected_scope",
                    "label": "У всех или у одного",
                    "type": "radio",
                    "required": False,
                    "visible_when": {"field": "issue_kind", "equals": "site_down"},
                    "options": [
                        {"value": "single", "label": "У одного"},
                        {"value": "multiple", "label": "У нескольких"},
                        {"value": "all", "label": "У всех"},
                    ],
                },
            ],
        },
        {
            "key": "new_account",
            "request_kind": "new_account",
            "title": "Новая учётка",
            "description": "Создание новой учётной записи.",
            "fields": [
                {"key": "employee_name", "label": "Для кого", "type": "text", "required": True},
                {"key": "department", "label": "Подразделение", "type": "text", "required": False},
                {"key": "systems", "label": "Какие системы нужны", "type": "textarea", "required": False},
            ],
        },
        {
            "key": "mail_issue",
            "request_kind": "mail_issue",
            "title": "Проблема с почтой",
            "description": "Не приходит, не отправляется или неверно работает почта.",
            "fields": [
                {"key": "mailbox", "label": "Почтовый ящик", "type": "text", "required": False},
                {
                    "key": "problem_type",
                    "label": "Проблема",
                    "type": "select",
                    "required": False,
                    "options": [
                        {"value": "send", "label": "Не отправляется"},
                        {"value": "receive", "label": "Не приходит"},
                        {"value": "auth", "label": "Не удаётся войти"},
                        {"value": "other", "label": "Другое"},
                    ],
                },
            ],
        },
    ]
    for form in forms:
        form["ticket_type"] = infer_ticket_type_for_form(form.get("key"), form.get("request_kind"))
        if form.get("key") in _SETUP_ASSISTANCE_FORM_KEYS:
            form["priority_policy"] = {}
            form["field_roles"] = {}
        else:
            _attach_default_priority_context(form)

    return {
        "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
        "version": DEFAULT_TICKET_FORM_PACK_VERSION,
        "title": "Каталог обращений",
        "description": "Базовый каталог интеллектуальных форм для helpdesk.",
        "forms": forms,
    }


def _normalize_option(raw_option: Any) -> dict[str, str]:
    if not isinstance(raw_option, dict):
        raise ValueError("field option must be an object")
    value = str(raw_option.get("value") or "").strip()
    label = str(raw_option.get("label") or "").strip()
    if not value:
        raise ValueError("field option value is required")
    if not label:
        raise ValueError("field option label is required")
    return {"value": value, "label": label}


def _normalize_visible_when(raw_rule: Any) -> Optional[dict[str, Any]]:
    if raw_rule in (None, ""):
        return None
    if not isinstance(raw_rule, dict):
        raise ValueError("visible_when must be an object")
    field = str(raw_rule.get("field") or "").strip()
    if not field:
        raise ValueError("visible_when.field is required")
    if "equals" in raw_rule:
        return {"field": field, "equals": str(raw_rule.get("equals") or "").strip()}
    values = raw_rule.get("in")
    if isinstance(values, list) and values:
        return {"field": field, "in": [str(item or "").strip() for item in values if str(item or "").strip()]}
    raise ValueError("visible_when requires equals or in")


def _normalize_optional_int(raw_value: Any, field_name: str) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be integer") from exc


def _normalize_optional_dict(raw_value: Any, field_name: str) -> dict[str, Any]:
    if raw_value in (None, ""):
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError(f"{field_name} must be an object")
    return deepcopy(raw_value)


def _normalize_policy_bool(raw_value: Any, *, default: bool = False) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(raw_value)


def _normalize_policy_choice(
    raw_value: Any,
    *,
    field_name: str,
    allowed_values: frozenset[str],
    default: str,
) -> str:
    value = str(raw_value or default).strip() or default
    if value not in allowed_values:
        raise ValueError(f"on_behalf_policy.{field_name} has unsupported value {value!r}")
    return value


def _normalize_on_behalf_policy(raw_value: Any) -> dict[str, Any] | None:
    if raw_value in (None, ""):
        return None
    if not isinstance(raw_value, dict):
        raise ValueError("on_behalf_policy must be an object")
    if not raw_value:
        return None

    allowed = _normalize_policy_bool(raw_value.get("allowed"))
    if not allowed:
        return {"allowed": False}

    label = str(raw_value.get("label") or _ON_BEHALF_DEFAULT_LABEL).strip() or _ON_BEHALF_DEFAULT_LABEL
    return {
        "allowed": True,
        "label": label,
        "affected_person_required": _normalize_policy_bool(
            raw_value.get("affected_person_required"),
            default=False,
        ),
        "reason_required": _normalize_policy_bool(raw_value.get("reason_required"), default=False),
        "allowed_scope": _normalize_policy_choice(
            raw_value.get("allowed_scope"),
            field_name="allowed_scope",
            allowed_values=_ON_BEHALF_ALLOWED_SCOPES,
            default="same_department_or_privileged",
        ),
        "diagnostic_target": _normalize_policy_choice(
            raw_value.get("diagnostic_target"),
            field_name="diagnostic_target",
            allowed_values=_ON_BEHALF_DIAGNOSTIC_TARGETS,
            default="affected_person_primary_agent",
        ),
        "knowledge_visibility": _normalize_policy_choice(
            raw_value.get("knowledge_visibility"),
            field_name="knowledge_visibility",
            allowed_values=_ON_BEHALF_KNOWLEDGE_VISIBILITY,
            default="creator_only",
        ),
        "support_visibility": _normalize_policy_choice(
            raw_value.get("support_visibility"),
            field_name="support_visibility",
            allowed_values=_ON_BEHALF_SUPPORT_VISIBILITY,
            default="creator_and_affected",
        ),
        "no_primary_agent_behavior": _normalize_policy_choice(
            raw_value.get("no_primary_agent_behavior"),
            field_name="no_primary_agent_behavior",
            allowed_values=_ON_BEHALF_NO_PRIMARY_AGENT_BEHAVIORS,
            default="allow_ticket_no_diagnostics",
        ),
        "support_override_allowed": _normalize_policy_bool(
            raw_value.get("support_override_allowed"),
            default=False,
        ),
    }


def _normalize_availability_policy(raw_form: dict[str, Any]) -> dict[str, bool]:
    raw_policy = raw_form.get("availability_policy")
    policy = raw_policy if isinstance(raw_policy, dict) else {}
    return {
        field: _normalize_policy_bool(raw_form.get(field, policy.get(field)), default=False)
        for field in _AVAILABILITY_BOOL_FIELDS
    }


def _normalize_process_mapping(raw_value: Any, *, roles: list[str] | None = None) -> dict[str, Any]:
    mapping = _normalize_optional_dict(raw_value, "process_mapping")
    normalized_roles: list[str] = []
    for raw_role in list(roles or []) + list(mapping.get("roles") or []):
        role = str(raw_role or "").strip()
        if not role:
            continue
        if role not in _ALLOWED_FIELD_ROLES:
            raise ValueError(f"process_mapping.roles has unsupported role {role!r}")
        if role not in normalized_roles:
            normalized_roles.append(role)
    if normalized_roles:
        mapping["roles"] = normalized_roles
    elif "roles" in mapping:
        mapping.pop("roles", None)
    return mapping


def _normalize_field_roles(raw_value: Any, field_keys: set[str], *, form_key: str) -> dict[str, list[str]]:
    if raw_value in (None, ""):
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError(f"form {form_key!r} field_roles must be an object")
    normalized: dict[str, list[str]] = {}
    for raw_field_key, raw_roles in raw_value.items():
        field_key = str(raw_field_key or "").strip()
        if not field_key:
            continue
        if field_key not in field_keys:
            raise ValueError(f"form {form_key!r} field_roles references unknown field {field_key!r}")
        if not isinstance(raw_roles, list):
            raise ValueError(f"form {form_key!r} field_roles.{field_key} must be an array")
        roles: list[str] = []
        for raw_role in raw_roles:
            role = str(raw_role or "").strip()
            if not role:
                continue
            if role not in _ALLOWED_FIELD_ROLES:
                raise ValueError(f"form {form_key!r} field_roles.{field_key} has unsupported role {role!r}")
            if role not in roles:
                roles.append(role)
        if roles:
            normalized[field_key] = roles
    return normalized


def next_form_pack_version(current_version: Optional[str]) -> str:
    version = str(current_version or "").strip()
    if not version:
        return "1.0.1"
    parts = version.split(".")
    if all(part.isdigit() for part in parts):
        numeric_parts = [int(part) for part in parts]
        numeric_parts[-1] += 1
        return ".".join(str(part) for part in numeric_parts)
    match = re.match(r"^(.*?)(\d+)$", version)
    if match:
        prefix, tail = match.groups()
        return f"{prefix}{int(tail) + 1}"
    return f"{version}.1"


def validate_form_pack_schema(raw_pack: Any, *, require_version: bool = True) -> dict[str, Any]:
    if not isinstance(raw_pack, dict):
        raise ValueError("form pack must be an object")

    pack_key = str(raw_pack.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    version = str(raw_pack.get("version") or "").strip()
    title = str(raw_pack.get("title") or "").strip() or "Каталог обращений"
    description = str(raw_pack.get("description") or "").strip()
    raw_forms = raw_pack.get("forms")
    if require_version and not version:
        raise ValueError("version is required")
    if not isinstance(raw_forms, list) or not raw_forms:
        raise ValueError("forms must be a non-empty array")

    normalized_forms: list[dict[str, Any]] = []
    seen_forms: set[str] = set()
    for raw_form in raw_forms:
        if not isinstance(raw_form, dict):
            raise ValueError("each form must be an object")
        form_key = str(raw_form.get("key") or "").strip()
        form_title = str(raw_form.get("title") or "").strip()
        request_kind = str(raw_form.get("request_kind") or form_key).strip() or form_key
        if not form_key:
            raise ValueError("form key is required")
        if not KEY_PATTERN.match(form_key):
            raise ValueError(f"form {form_key!r} key must use latin snake_case")
        if not form_title:
            raise ValueError(f"form {form_key!r} title is required")
        if not KEY_PATTERN.match(request_kind):
            raise ValueError(f"form {form_key!r} request_kind must use latin snake_case")
        request_template_key = str(raw_form.get("request_template_key") or form_key).strip() or form_key
        if not KEY_PATTERN.match(request_template_key):
            raise ValueError(f"form {form_key!r} request_template_key must use latin snake_case")
        request_template_title = str(raw_form.get("request_template_title") or form_title).strip() or form_title
        if form_key in seen_forms:
            raise ValueError(f"duplicate form key: {form_key}")
        seen_forms.add(form_key)

        raw_fields = raw_form.get("fields") or []
        if not isinstance(raw_fields, list):
            raise ValueError(f"form {form_key!r} fields must be an array")

        normalized_fields: list[dict[str, Any]] = []
        seen_fields: set[str] = set()
        for raw_field in raw_fields:
            if not isinstance(raw_field, dict):
                raise ValueError(f"form {form_key!r} field must be an object")
            field_key = str(raw_field.get("key") or "").strip()
            field_label = str(raw_field.get("label") or "").strip()
            field_type = str(raw_field.get("type") or "text").strip().lower()
            if not field_key:
                raise ValueError(f"form {form_key!r} field key is required")
            if not KEY_PATTERN.match(field_key):
                raise ValueError(f"form {form_key!r} field {field_key!r} key must use latin snake_case")
            if field_key in seen_fields:
                raise ValueError(f"form {form_key!r} has duplicate field key {field_key!r}")
            if not field_label:
                raise ValueError(f"form {form_key!r} field {field_key!r} label is required")
            if field_type not in ALLOWED_FIELD_TYPES:
                raise ValueError(f"form {form_key!r} field {field_key!r} has unsupported type {field_type!r}")
            seen_fields.add(field_key)

            options = raw_field.get("options") or []
            normalized_options = [_normalize_option(option) for option in options] if options else []
            if field_type in OPTION_FIELD_TYPES | MULTI_SELECT_FIELD_TYPES and not normalized_options:
                raise ValueError(f"form {form_key!r} field {field_key!r} requires options")

            normalized_fields.append(
                {
                    "key": field_key,
                    "label": field_label,
                    "type": field_type,
                    "required": bool(raw_field.get("required")),
                    "placeholder": str(raw_field.get("placeholder") or "").strip(),
                    "help_text": str(raw_field.get("help_text") or "").strip(),
                    "options": normalized_options,
                    "validation": _normalize_optional_dict(raw_field.get("validation"), "validation"),
                    "process_mapping": _normalize_process_mapping(raw_field.get("process_mapping")),
                    "visible_when": _normalize_visible_when(raw_field.get("visible_when")),
                }
            )

        for normalized_field in normalized_fields:
            visible_when = normalized_field.get("visible_when")
            if not isinstance(visible_when, dict):
                continue
            dependency_key = str(visible_when.get("field") or "").strip()
            if dependency_key and dependency_key not in seen_fields:
                raise ValueError(
                    f"form {form_key!r} field {normalized_field['key']!r} "
                    f"references unknown visible_when.field {dependency_key!r}"
                )

        priority_policy_for_fields = (
            raw_form.get("priority_policy")
            if isinstance(raw_form.get("priority_policy"), dict)
            else DEFAULT_PRIORITY_POLICY
        )
        priority_policy_refs = {
            str(priority_policy_for_fields.get(policy_key) or "").strip()
            for policy_key in ("impact_field", "urgency_field", "importance_field")
        }
        modifier_fields_for_refs = (
            priority_policy_for_fields.get("modifier_fields")
            if isinstance(priority_policy_for_fields.get("modifier_fields"), dict)
            else {}
        )
        priority_policy_refs.update(str(value or "").strip() for value in modifier_fields_for_refs.values())
        priority_policy_refs.discard("")
        existing_field_keys = {field["key"] for field in normalized_fields}
        for priority_field in build_default_priority_fields():
            priority_key = str(priority_field.get("key") or "").strip()
            if priority_key not in priority_policy_refs:
                continue
            if priority_key in existing_field_keys:
                continue
            compatibility_field = deepcopy(priority_field)
            validation = compatibility_field.get("validation") if isinstance(compatibility_field.get("validation"), dict) else {}
            compatibility_field["validation"] = {
                **validation,
                "optional_when_legacy_missing": True,
            }
            normalized_fields.append(compatibility_field)
            existing_field_keys.add(priority_key)
            seen_fields.add(priority_key)

        ticket_type = str(
            raw_form.get("ticket_type") or infer_ticket_type_for_form(form_key, request_kind)
        ).strip() or DEFAULT_WORKFLOW_PROFILE
        raw_field_roles = raw_form.get("field_roles")
        merged_field_roles = {
            field_key: deepcopy(roles)
            for field_key, roles in DEFAULT_PRIORITY_FIELD_ROLES.items()
            if field_key in seen_fields
        }
        for policy_field_key in priority_policy_refs:
            if policy_field_key in seen_fields:
                merged_field_roles.setdefault(policy_field_key, ["priority_field"])
        if isinstance(raw_field_roles, dict):
            merged_field_roles.update(raw_field_roles)
        for raw_field in raw_fields:
            if not isinstance(raw_field, dict):
                continue
            field_key = str(raw_field.get("key") or "").strip()
            process_mapping = raw_field.get("process_mapping")
            if not field_key or not isinstance(process_mapping, dict):
                continue
            roles = process_mapping.get("roles")
            if not isinstance(roles, list):
                continue
            for role in roles:
                merged_field_roles.setdefault(field_key, [])
                if role not in merged_field_roles[field_key]:
                    merged_field_roles[field_key].append(role)
        normalized_field_roles = _normalize_field_roles(merged_field_roles, seen_fields, form_key=form_key)
        for normalized_field in normalized_fields:
            field_key = str(normalized_field.get("key") or "").strip()
            normalized_field["process_mapping"] = _normalize_process_mapping(
                normalized_field.get("process_mapping"),
                roles=normalized_field_roles.get(field_key, []),
            )
        template_context: dict[str, Any] = {
            "ticket_type": ticket_type,
            "field_roles": normalized_field_roles,
        }
        for string_field in _TEMPLATE_STRING_FIELDS:
            value = str(raw_form.get(string_field) or "").strip()
            if value:
                template_context[string_field] = value
        for int_field in _TEMPLATE_INT_FIELDS:
            value = _normalize_optional_int(raw_form.get(int_field), int_field)
            if value is not None:
                template_context[int_field] = value
        for version_field in _TEMPLATE_VERSION_FIELDS:
            raw_value = raw_form.get(version_field)
            if isinstance(raw_value, int):
                template_context[version_field] = raw_value
                continue
            value = str(raw_value or "").strip()
            if value:
                template_context[version_field] = value
        suggested_playbook_id = str(raw_form.get("suggested_playbook_id") or "").strip()
        if suggested_playbook_id:
            template_context["suggested_playbook_id"] = suggested_playbook_id
        if "priority_policy" not in raw_form:
            raw_form["priority_policy"] = deepcopy(DEFAULT_PRIORITY_POLICY)

        on_behalf_policy = _normalize_on_behalf_policy(raw_form.get("on_behalf_policy"))
        if on_behalf_policy is not None:
            template_context["on_behalf_policy"] = on_behalf_policy
        availability_policy = _normalize_availability_policy(raw_form)
        template_context["availability_policy"] = availability_policy
        template_context.update(availability_policy)

        for dict_field in _TEMPLATE_DICT_FIELDS:
            value = _normalize_optional_dict(raw_form.get(dict_field), dict_field)
            if value:
                template_context[dict_field] = value
        normalized_policy_refs = (
            deepcopy(template_context.get("policy_refs"))
            if isinstance(template_context.get("policy_refs"), dict)
            else {}
        )
        for kind, (ref_field, code_field) in _POLICY_REF_FIELDS.items():
            explicit_ref = str(template_context.get(ref_field) or "").strip()
            legacy_code = str(template_context.get(code_field) or "").strip()
            effective_ref = explicit_ref or legacy_code
            if not effective_ref:
                continue
            normalized_policy_refs[kind] = effective_ref
            template_context[ref_field] = effective_ref
            template_context[code_field] = effective_ref
        if normalized_policy_refs:
            template_context["policy_refs"] = normalized_policy_refs
        for list_field in _TEMPLATE_LIST_FIELDS:
            value = raw_form.get(list_field)
            if isinstance(value, list) and value:
                template_context[list_field] = [deepcopy(item) for item in value if isinstance(item, dict)]

        normalized_forms.append(
            {
                "key": form_key,
                "request_template_key": request_template_key,
                "request_template_title": request_template_title,
                "request_kind": request_kind,
                "title": form_title,
                "description": str(raw_form.get("description") or "").strip(),
                "fields": normalized_fields,
                "playbook_triggers": normalize_form_playbook_triggers(raw_form.get("playbook_triggers")),
                **template_context,
            }
        )

    return {
        "pack_key": pack_key,
        "version": version,
        "title": title,
        "description": description,
        "forms": normalized_forms,
    }


def ensure_setup_assistance_forms(pack: dict[str, Any]) -> dict[str, Any]:
    """Expose mandatory setup-help forms even when an older pack is preferred."""
    normalized = validate_form_pack_schema(pack)
    if normalized.get("pack_key") != DEFAULT_TICKET_FORM_PACK_KEY:
        return normalized

    forms = normalized.get("forms") if isinstance(normalized.get("forms"), list) else []
    existing_keys = {str(form.get("key") or "").strip() for form in forms if isinstance(form, dict)}
    missing_keys = [key for key in _SETUP_ASSISTANCE_FORM_KEYS if key not in existing_keys]
    if not missing_keys:
        return normalized

    builtin = validate_form_pack_schema(build_default_ticket_form_pack())
    builtin_by_key = {
        str(form.get("key") or "").strip(): form
        for form in builtin.get("forms") or []
        if isinstance(form, dict)
    }
    setup_forms = [deepcopy(builtin_by_key[key]) for key in missing_keys if key in builtin_by_key]
    if not setup_forms:
        return normalized

    augmented = deepcopy(normalized)
    augmented["forms"] = setup_forms + [deepcopy(form) for form in forms if isinstance(form, dict)]
    return validate_form_pack_schema(augmented)


def requester_safe_form_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Return a requester/public projection without legacy request wording."""
    safe_pack = ensure_setup_assistance_forms(pack)
    if safe_pack.get("pack_key") != DEFAULT_TICKET_FORM_PACK_KEY:
        return safe_pack

    title = str(safe_pack.get("title") or "").strip()
    if title == "Каталог заявок":
        safe_pack = deepcopy(safe_pack)
        safe_pack["title"] = "Каталог обращений"
    return safe_pack


def pack_summary(pack: dict[str, Any]) -> dict[str, Any]:
    forms = pack.get("forms") or []
    return {
        "pack_key": pack.get("pack_key"),
        "version": pack.get("version"),
        "title": pack.get("title"),
        "description": pack.get("description"),
        "forms_count": len(forms),
        "request_kinds": [form.get("request_kind") for form in forms],
    }


def _field_is_visible(field_def: dict[str, Any], values: dict[str, Any]) -> bool:
    rule = field_def.get("visible_when")
    if not isinstance(rule, dict):
        return True
    current_value = values.get(rule.get("field"))
    if "equals" in rule:
        return str(current_value or "").strip() == str(rule.get("equals") or "").strip()
    allowed_values = {str(item or "").strip() for item in rule.get("in") or []}
    return str(current_value or "").strip() in allowed_values


def _normalize_field_value(field_def: dict[str, Any], raw_value: Any) -> Any:
    field_type = field_def.get("type")
    if field_type == "checkbox":
        return bool(raw_value)
    if field_type == "number":
        if raw_value in (None, ""):
            return None
        text_value = str(raw_value).strip().replace(",", ".")
        try:
            number_value = float(text_value)
        except (TypeError, ValueError):
            raise ValueError("invalid number")
        if not math.isfinite(number_value):
            raise ValueError("invalid number")
        return int(number_value) if number_value.is_integer() else number_value
    if field_type == "file":
        if raw_value in (None, ""):
            return {}
        if isinstance(raw_value, dict):
            path = str(raw_value.get("path") or "").strip()
            filename = str(raw_value.get("filename") or "").strip()
        else:
            path = str(raw_value or "").strip()
            filename = ""
        if not filename and path:
            filename = path.replace("\\", "/").rstrip("/").split("/")[-1]
        if not path and not filename:
            return {}
        return {"path": path, "filename": filename}
    if field_type in MULTI_SELECT_FIELD_TYPES:
        if raw_value in (None, ""):
            return []
        if isinstance(raw_value, list):
            values = [str(item or "").strip() for item in raw_value]
        else:
            values = [item.strip() for item in str(raw_value or "").split(",")]
        values = [item for item in values if item]
        allowed_values = {str(option.get("value") or "") for option in field_def.get("options") or []}
        invalid = [item for item in values if item not in allowed_values]
        if invalid:
            raise ValueError("invalid option")
        return values
    text_value = str(raw_value or "").strip()
    if field_type in OPTION_VALIDATED_FIELD_TYPES and text_value:
        allowed_values = {str(option.get("value") or "") for option in field_def.get("options") or []}
        if allowed_values and text_value not in allowed_values:
            raise ValueError("invalid option")
    return text_value


def _validation_value(field_def: dict[str, Any], keys: tuple[str, ...]) -> Any:
    validation = field_def.get("validation") if isinstance(field_def.get("validation"), dict) else {}
    for key in keys:
        value = validation.get(key)
        if value not in (None, ""):
            return value
        value = field_def.get(key)
        if value not in (None, ""):
            return value
    return None


def _validation_number(field_def: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    value = _validation_value(field_def, keys)
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _validation_string(field_def: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _validation_value(field_def, keys)
    text_value = str(value or "").strip()
    return text_value or None


def _is_text_validation_field(field_def: dict[str, Any]) -> bool:
    return field_def.get("type") in {"text", "textarea", "email", "url", "phone"}


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _field_constraint_error(field_def: dict[str, Any], value: Any) -> str | None:
    field_type = field_def.get("type")
    if field_type == "number":
        if value is None:
            return None
        min_value = _validation_number(field_def, ("min", "minimum", "min_value"))
        max_value = _validation_number(field_def, ("max", "maximum", "max_value"))
        if min_value is not None and float(value) < min_value:
            return f"Минимальное значение: {min_value:g}."
        if max_value is not None and float(value) > max_value:
            return f"Максимальное значение: {max_value:g}."

    if _is_text_validation_field(field_def):
        text_value = str(value or "").strip()
        if not text_value:
            return None
        min_length = _validation_number(field_def, ("min_length", "minLength"))
        max_length = _validation_number(field_def, ("max_length", "maxLength"))
        pattern = _validation_string(field_def, ("pattern", "regex"))
        if min_length is not None and len(text_value) < int(min_length):
            return f"Минимум символов: {int(min_length)}."
        if max_length is not None and len(text_value) > int(max_length):
            return f"Максимум символов: {int(max_length)}."
        if pattern:
            try:
                if not re.search(pattern, text_value):
                    return "Проверьте формат поля."
            except re.error:
                pass
        if field_type == "email" and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", text_value):
            return "Укажите корректный email."
        if field_type == "url" and not _is_valid_url(text_value):
            return "Укажите корректную ссылку."
    return None


def validate_form_submission(
    pack: dict[str, Any],
    *,
    form_key: str,
    raw_values: Any,
) -> dict[str, Any]:
    if not isinstance(raw_values, dict):
        raise ValueError("form payload must be an object")

    form = next((item for item in pack.get("forms") or [] if item.get("key") == form_key), None)
    if form is None:
        raise ValueError(f"unknown form key: {form_key}")

    normalized_values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for field_def in form.get("fields") or []:
        key = str(field_def.get("key") or "")
        try:
            value = _normalize_field_value(field_def, raw_values.get(key))
        except ValueError:
            errors[key] = "Недопустимое значение"
            continue
        normalized_values[key] = value

    submitted_values: dict[str, Any] = {}
    summary_rows: list[dict[str, str]] = []
    for field_def in form.get("fields") or []:
        key = str(field_def.get("key") or "")
        if not _field_is_visible(field_def, normalized_values):
            continue
        value = normalized_values.get(key)
        validation = field_def.get("validation") if isinstance(field_def.get("validation"), dict) else {}
        if validation.get("optional_when_legacy_missing") and key not in raw_values:
            continue
        if field_def.get("required"):
            if field_def.get("type") == "checkbox":
                is_empty = value is False
            elif isinstance(value, list):
                is_empty = not value
            elif isinstance(value, dict):
                is_empty = not str(value.get("path") or value.get("filename") or "").strip()
            else:
                is_empty = not str(value or "").strip()
            if is_empty:
                required_message = str(validation.get("required_message") or "").strip()
                errors[key] = required_message or "Поле обязательно"
                continue
        constraint_error = _field_constraint_error(field_def, value)
        if constraint_error:
            errors[key] = constraint_error
            continue
        if field_def.get("type") == "checkbox":
            submitted_values[key] = bool(value)
            display_value = "Да" if value else "Нет"
        elif field_def.get("type") == "number":
            if value is None:
                continue
            submitted_values[key] = value
            display_value = f"{value:g}" if isinstance(value, float) else str(value)
        elif field_def.get("type") == "file":
            file_value = value if isinstance(value, dict) else {}
            filename = str(file_value.get("filename") or "").strip()
            path = str(file_value.get("path") or "").strip()
            if not filename and not path:
                continue
            submitted_values[key] = {"path": path, "filename": filename}
            display_value = filename or path
        elif field_def.get("type") in MULTI_SELECT_FIELD_TYPES:
            selected_values = value if isinstance(value, list) else []
            if not selected_values:
                continue
            submitted_values[key] = list(selected_values)
            option_map = {opt["value"]: opt["label"] for opt in field_def.get("options") or []}
            display_value = ", ".join(option_map.get(item, item) for item in selected_values)
        else:
            text_value = str(value or "").strip()
            if not text_value:
                continue
            submitted_values[key] = text_value
            option_map = {opt["value"]: opt["label"] for opt in field_def.get("options") or []}
            display_value = option_map.get(text_value, text_value)
        summary_rows.append({"key": key, "label": field_def.get("label") or key, "value": display_value})

    if errors:
        raise ValueError(errors)

    priority_policy = form.get("priority_policy") if isinstance(form.get("priority_policy"), dict) else {}
    priority_field_keys = {
        str(priority_policy.get("impact_field") or "").strip(),
        str(priority_policy.get("urgency_field") or "").strip(),
        str(priority_policy.get("importance_field") or "").strip(),
    }
    modifier_fields = priority_policy.get("modifier_fields") if isinstance(priority_policy.get("modifier_fields"), dict) else {}
    priority_field_keys.update(str(value or "").strip() for value in modifier_fields.values())
    for key in sorted(item for item in priority_field_keys if item):
        if key in submitted_values or key not in raw_values:
            continue
        value = raw_values.get(key)
        if isinstance(value, bool):
            submitted_values[key] = value
        else:
            text_value = str(value or "").strip()
            if text_value:
                submitted_values[key] = text_value

    return {
        "pack_key": pack.get("pack_key"),
        "pack_version": pack.get("version"),
        "form_key": form.get("key"),
        "request_template_key": form.get("request_template_key") or form.get("key"),
        "request_kind": form.get("request_kind"),
        "ticket_type": form.get("ticket_type") or DEFAULT_WORKFLOW_PROFILE,
        "form_title": form.get("title"),
        "submitted_values": submitted_values,
        "summary_rows": summary_rows,
        "playbook_triggers": deepcopy(form.get("playbook_triggers") or []),
        "template_context": {
            "key": form.get("request_template_key") or form.get("key"),
            "title": form.get("request_template_title") or form.get("title"),
            "form_key": form.get("key"),
            "request_kind": form.get("request_kind"),
            "ticket_type": form.get("ticket_type") or DEFAULT_WORKFLOW_PROFILE,
            "category_id": form.get("category_id"),
            "service_id": form.get("service_id"),
            "subcategory_id": form.get("subcategory_id"),
            "default_queue_id": form.get("default_queue_id"),
            "sla_policy_id": form.get("sla_policy_id"),
            "suggested_playbook_id": form.get("suggested_playbook_id"),
            "form_schema_id": form.get("form_schema_id"),
            "workflow_profile_id": form.get("workflow_profile_id"),
            "priority_policy_code": form.get("priority_policy_code"),
            "routing_policy_code": form.get("routing_policy_code"),
            "sla_policy_code": form.get("sla_policy_code"),
            "ola_policy_code": form.get("ola_policy_code"),
            "approval_policy_code": form.get("approval_policy_code"),
            "diagnostic_policy_code": form.get("diagnostic_policy_code"),
            "closure_policy_code": form.get("closure_policy_code"),
            "visibility_policy_code": form.get("visibility_policy_code"),
            "notification_policy_code": form.get("notification_policy_code"),
            "reporting_policy_code": form.get("reporting_policy_code"),
            "request_template_version": form.get("request_template_version"),
            "form_schema_version": form.get("form_schema_version"),
            "policy_refs": deepcopy(form.get("policy_refs") or {}),
            "field_roles": deepcopy(form.get("field_roles") or {}),
            "priority_policy": deepcopy(form.get("priority_policy") or {}),
            "routing_policy": deepcopy(form.get("routing_policy") or {}),
            "sla_policy": deepcopy(form.get("sla_policy") or {}),
            "approval_policy": deepcopy(form.get("approval_policy") or {}),
            "diagnostic_policy": deepcopy(form.get("diagnostic_policy") or {}),
            "ola_policy": deepcopy(form.get("ola_policy") or {}),
            "closure_policy": deepcopy(form.get("closure_policy") or {}),
            "visibility_policy": deepcopy(form.get("visibility_policy") or {}),
            "notification_policy": deepcopy(form.get("notification_policy") or {}),
            "reporting_policy": deepcopy(form.get("reporting_policy") or {}),
            "on_behalf_policy": deepcopy(form.get("on_behalf_policy") or {}),
        },
    }


def build_form_custom_fields(validated_submission: dict[str, Any]) -> dict[str, Any]:
    template_context = deepcopy(validated_submission.get("template_context") or {})
    resolved_from = validated_submission.get("resolved_from") or "legacy_pack"
    resolved_pack_key = validated_submission.get("resolved_pack_key") or validated_submission.get("pack_key")
    resolved_pack_version = validated_submission.get("resolved_pack_version") or validated_submission.get("pack_version")
    resolved_template_key = (
        validated_submission.get("resolved_template_key")
        or template_context.get("key")
        or validated_submission.get("request_template_key")
    )
    resolved_template_version = (
        validated_submission.get("resolved_template_version")
        or template_context.get("request_template_version")
    )
    resolved_form_schema_id = (
        validated_submission.get("resolved_form_schema_id")
        or template_context.get("form_schema_id")
    )
    resolved_form_schema_version = (
        validated_submission.get("resolved_form_schema_version")
        or template_context.get("form_schema_version")
    )
    if resolved_template_version is not None:
        template_context.setdefault("version", resolved_template_version)
        template_context.setdefault("request_template_version", resolved_template_version)
    if resolved_template_key:
        template_context.setdefault("key", resolved_template_key)
    if resolved_form_schema_id:
        template_context.setdefault("form_schema_id", resolved_form_schema_id)
    if resolved_form_schema_version is not None:
        template_context.setdefault("form_schema_version", resolved_form_schema_version)
    template_context.setdefault("source", resolved_from)
    request_form_snapshot = {
        "source": resolved_from,
        "pack_key": resolved_pack_key,
        "pack_version": resolved_pack_version,
        "form_key": validated_submission.get("form_key"),
        "form_title": validated_submission.get("form_title"),
    }
    if resolved_template_key:
        request_form_snapshot["request_template_key"] = resolved_template_key
    if resolved_template_version is not None:
        request_form_snapshot["request_template_version"] = resolved_template_version
    if resolved_form_schema_id:
        request_form_snapshot["form_schema_id"] = resolved_form_schema_id
    if resolved_form_schema_version is not None:
        request_form_snapshot["form_schema_version"] = resolved_form_schema_version
    return {
        "request_kind": validated_submission.get("request_kind"),
        "request_form_pack_key": validated_submission.get("pack_key"),
        "request_form_version": validated_submission.get("pack_version"),
        "request_form_key": validated_submission.get("form_key"),
        "request_form_title": validated_submission.get("form_title"),
        "request_form": request_form_snapshot,
        "resolved_from": resolved_from,
        "resolved_pack_key": resolved_pack_key,
        "resolved_pack_version": resolved_pack_version,
        "resolved_template_key": resolved_template_key,
        "resolved_template_version": resolved_template_version,
        "resolved_form_schema_id": resolved_form_schema_id,
        "resolved_form_schema_version": resolved_form_schema_version,
        "request_form_data": deepcopy(validated_submission.get("submitted_values") or {}),
        "request_form_summary": deepcopy(validated_submission.get("summary_rows") or []),
        "request_form_playbook_triggers": deepcopy(validated_submission.get("playbook_triggers") or []),
        "request_template": template_context,
    }


def _routing_rule_identifier(rule: Any) -> str | int | None:
    if not isinstance(rule, dict):
        return None
    for key in ("code", "key", "id", "priority_order", "index"):
        value = rule.get(key)
        if value not in (None, ""):
            return value
    return None


def attach_request_template_computed_snapshot(
    custom_fields: dict[str, Any] | None,
    *,
    priority_decision: dict[str, Any] | None = None,
    routing_decision: dict[str, Any] | None = None,
    queue: Any | None = None,
) -> dict[str, Any]:
    result = deepcopy(custom_fields or {})
    request_template = result.get("request_template") if isinstance(result.get("request_template"), dict) else {}
    request_template = deepcopy(request_template)
    computed = request_template.get("computed") if isinstance(request_template.get("computed"), dict) else {}
    computed = deepcopy(computed)

    priority = priority_decision if isinstance(priority_decision, dict) else result.get("priority_decision")
    if isinstance(priority, dict):
        priority_class = (
            priority.get("effective_priority")
            or priority.get("priority_class")
            or priority.get("computed_priority")
        )
        if priority_class:
            computed["priority"] = priority_class
        if priority.get("priority_source"):
            computed["priority_source"] = priority.get("priority_source")
        if priority.get("computed_priority"):
            computed["computed_priority"] = priority.get("computed_priority")
        if priority.get("manual_priority"):
            computed["manual_priority"] = priority.get("manual_priority")

    routing = routing_decision if isinstance(routing_decision, dict) else result.get("routing_decision")
    if isinstance(routing, dict):
        queue_id = routing.get("to_queue_id") if routing.get("to_queue_id") is not None else routing.get("queue_id")
        if queue_id is not None:
            computed["queue_id"] = queue_id
        if routing.get("source"):
            computed["routing_source"] = routing.get("source")
        matched_rule = _routing_rule_identifier(routing.get("matched_rule"))
        if matched_rule is not None:
            computed["matched_routing_rule"] = matched_rule

    if queue is not None:
        queue_id = getattr(queue, "id", None)
        if queue_id is not None:
            computed["queue_id"] = queue_id
        queue_code = getattr(queue, "code", None)
        queue_name = getattr(queue, "name", None)
        if queue_code:
            computed["queue_code"] = queue_code
        if queue_name:
            computed["queue_name"] = queue_name

    approval_policy = request_template.get("approval_policy") if isinstance(request_template.get("approval_policy"), dict) else {}
    if approval_policy:
        computed["approval_required"] = bool(approval_policy.get("required"))
    diagnostic_policy = request_template.get("diagnostic_policy") if isinstance(request_template.get("diagnostic_policy"), dict) else {}
    playbooks = diagnostic_policy.get("suggested_playbooks") or diagnostic_policy.get("playbooks") or []
    if isinstance(playbooks, list):
        computed["suggested_diagnostics"] = [
            str(item.get("playbook_key") if isinstance(item, dict) else item or "").strip()
            for item in playbooks
            if str(item.get("playbook_key") if isinstance(item, dict) else item or "").strip()
        ]

    request_template["computed"] = computed
    result["request_template"] = request_template
    return result


def build_request_kind_title_map(pack: dict[str, Any]) -> dict[str, str]:
    labels = dict(_REQUEST_KIND_FALLBACK_LABELS)
    for form in pack.get("forms") or []:
        if not isinstance(form, dict):
            continue
        request_kind = str(form.get("request_kind") or form.get("key") or "").strip().lower()
        title = str(form.get("title") or "").strip()
        if request_kind and title:
            labels[request_kind] = title
    return labels


def humanize_request_kind(value: str | None, *, label_map: Optional[dict[str, str]] = None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Прочее"
    labels = label_map or _REQUEST_KIND_FALLBACK_LABELS
    if normalized in labels:
        return labels[normalized]
    readable = normalized.replace("_", " ").strip()
    if not readable:
        return "Прочее"
    return readable[0].upper() + readable[1:]


def build_routing_builder_catalog(pack: dict[str, Any]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [dict(item) for item in _ROUTING_BASE_FIELDS]
    forms: list[dict[str, Any]] = []
    flat_field_map = {item["field"]: item for item in fields}

    for form in pack.get("forms") or []:
        if not isinstance(form, dict):
            continue
        form_key = str(form.get("key") or "").strip()
        request_kind = str(form.get("request_kind") or form_key).strip()
        form_title = str(form.get("title") or form_key or "Форма").strip() or "Форма"
        form_fields: list[dict[str, Any]] = []
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            field_key = str(field.get("key") or "").strip()
            if not field_key:
                continue
            label = str(field.get("label") or field_key).strip() or field_key
            field_type = str(field.get("type") or "text").strip().lower() or "text"
            route_field = f"request_form_data.{field_key}"
            form_fields.append(
                {
                    "key": field_key,
                    "label": label,
                    "field": route_field,
                    "type": field_type,
                }
            )
            flat_field_map.setdefault(
                route_field,
                {
                    "field": route_field,
                    "label": f"{form_title} → {label}",
                    "source": "form",
                    "form_key": form_key or None,
                    "form_title": form_title,
                    "field_type": field_type,
                },
            )

        forms.append(
            {
                "key": form_key,
                "request_kind": request_kind,
                "title": form_title,
                "fields": form_fields,
            }
        )

    return {
        "fields": list(flat_field_map.values()),
        "forms": forms,
        "operators": [dict(item) for item in _ROUTING_OPERATOR_OPTIONS],
    }


async def resolve_ticket_form_pack(
    repo: TicketFormPacksRepo,
    *,
    pack_key: str = DEFAULT_TICKET_FORM_PACK_KEY,
    version: Optional[str] = None,
    include_setup_assistance: bool = False,
) -> dict[str, Any]:
    def _finalize(pack: dict[str, Any]) -> dict[str, Any]:
        return ensure_setup_assistance_forms(pack) if include_setup_assistance else pack

    builtin = validate_form_pack_schema(build_default_ticket_form_pack())
    if version:
        pack = await repo.get_pack(pack_key, version)
        if pack is not None and isinstance(pack.schema_json, dict):
            return _finalize(validate_form_pack_schema(pack.schema_json))
        if version == builtin.get("version") and pack_key == builtin.get("pack_key"):
            return _finalize(builtin)
        raise ValueError(f"ticket form pack not found: {pack_key}@{version}")

    preferred = await repo.get_preferred(pack_key)
    if preferred:
        preferred_pack = await repo.get_pack(pack_key, str(preferred.get("version") or ""))
        if preferred_pack is not None and isinstance(preferred_pack.schema_json, dict):
            return _finalize(validate_form_pack_schema(preferred_pack.schema_json))
    if pack_key == builtin.get("pack_key"):
        return _finalize(builtin)

    packs = await repo.list_packs(pack_key=pack_key)
    for pack in packs:
        if isinstance(pack.schema_json, dict):
            return _finalize(validate_form_pack_schema(pack.schema_json))
    return _finalize(builtin)
