"""Ticket form pack defaults, validation, and submission normalization."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Optional

from app.repos.ticket_form_packs_repo import TicketFormPacksRepo


DEFAULT_TICKET_FORM_PACK_KEY = "request_forms"
DEFAULT_TICKET_FORM_PACK_VERSION = "1.0.0"
ALLOWED_FIELD_TYPES = {"text", "textarea", "select", "radio", "checkbox"}
OPTION_FIELD_TYPES = {"select", "radio"}
KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


def build_default_ticket_form_pack() -> dict[str, Any]:
    """Built-in baseline catalog used until admins publish their own versions."""
    forms = [
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
    return {
        "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
        "version": DEFAULT_TICKET_FORM_PACK_VERSION,
        "title": "Каталог заявок",
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
    title = str(raw_pack.get("title") or "").strip() or "Каталог заявок"
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
            if field_type in OPTION_FIELD_TYPES and not normalized_options:
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
                    "visible_when": _normalize_visible_when(raw_field.get("visible_when")),
                }
            )

        normalized_forms.append(
            {
                "key": form_key,
                "request_kind": request_kind,
                "title": form_title,
                "description": str(raw_form.get("description") or "").strip(),
                "fields": normalized_fields,
            }
        )

    return {
        "pack_key": pack_key,
        "version": version,
        "title": title,
        "description": description,
        "forms": normalized_forms,
    }


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
    text_value = str(raw_value or "").strip()
    if field_type in OPTION_FIELD_TYPES and text_value:
        allowed_values = {str(option.get("value") or "") for option in field_def.get("options") or []}
        if text_value not in allowed_values:
            raise ValueError("invalid option")
    return text_value


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
        if field_def.get("required"):
            is_empty = value is False if field_def.get("type") == "checkbox" else not str(value or "").strip()
            if is_empty:
                errors[key] = "Поле обязательно"
                continue
        if field_def.get("type") == "checkbox":
            submitted_values[key] = bool(value)
            display_value = "Да" if value else "Нет"
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

    return {
        "pack_key": pack.get("pack_key"),
        "pack_version": pack.get("version"),
        "form_key": form.get("key"),
        "request_kind": form.get("request_kind"),
        "form_title": form.get("title"),
        "submitted_values": submitted_values,
        "summary_rows": summary_rows,
    }


def build_form_custom_fields(validated_submission: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_kind": validated_submission.get("request_kind"),
        "request_form_pack_key": validated_submission.get("pack_key"),
        "request_form_version": validated_submission.get("pack_version"),
        "request_form_key": validated_submission.get("form_key"),
        "request_form_title": validated_submission.get("form_title"),
        "request_form_data": deepcopy(validated_submission.get("submitted_values") or {}),
        "request_form_summary": deepcopy(validated_submission.get("summary_rows") or []),
    }


async def resolve_ticket_form_pack(
    repo: TicketFormPacksRepo,
    *,
    pack_key: str = DEFAULT_TICKET_FORM_PACK_KEY,
    version: Optional[str] = None,
) -> dict[str, Any]:
    builtin = validate_form_pack_schema(build_default_ticket_form_pack())
    if version:
        pack = await repo.get_pack(pack_key, version)
        if pack is not None and isinstance(pack.schema_json, dict):
            return validate_form_pack_schema(pack.schema_json)
        if version == builtin.get("version") and pack_key == builtin.get("pack_key"):
            return builtin
        raise ValueError(f"ticket form pack not found: {pack_key}@{version}")

    preferred = await repo.get_preferred(pack_key)
    if preferred:
        preferred_pack = await repo.get_pack(pack_key, str(preferred.get("version") or ""))
        if preferred_pack is not None and isinstance(preferred_pack.schema_json, dict):
            return validate_form_pack_schema(preferred_pack.schema_json)
    if pack_key == builtin.get("pack_key"):
        return builtin

    packs = await repo.list_packs(pack_key=pack_key)
    for pack in packs:
        if isinstance(pack.schema_json, dict):
            return validate_form_pack_schema(pack.schema_json)
    return builtin
