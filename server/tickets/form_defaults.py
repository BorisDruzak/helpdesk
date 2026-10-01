"""Ticket form pack defaults, validation, and submission normalization."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Optional

from playbooks.form_triggers import normalize_form_playbook_triggers
from tickets.workflow_profiles import DEFAULT_WORKFLOW_PROFILE


DEFAULT_TICKET_FORM_PACK_KEY = "request_forms"
DEFAULT_TICKET_FORM_PACK_VERSION = "1.0.0"
_REGISTRY_AUGMENTED_VERSION_SEPARATOR = "+registry."
ALLOWED_FIELD_TYPES = {
    "text",
    "textarea",
    "select",
    "multi_select",
    "radio",
    "checkbox",
    "date",
    "datetime",
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


def _base_version_from_registry_augmented(version: Optional[str]) -> Optional[str]:
    text = str(version or "").strip()
    if not text or _REGISTRY_AUGMENTED_VERSION_SEPARATOR not in text:
        return None
    base_version = text.split(_REGISTRY_AUGMENTED_VERSION_SEPARATOR, 1)[0].strip()
    return base_version or None


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
            "title": "Помощь с привязкой компьютера",
            "description": "Обращение в поддержку, если компьютер не удаётся привязать или получить код.",
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
