from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional
import math
import re
from urllib.parse import urlparse
from tickets.workflow_profiles import DEFAULT_WORKFLOW_PROFILE
from tickets.form_defaults import (
    MULTI_SELECT_FIELD_TYPES,
    OPTION_VALIDATED_FIELD_TYPES,
)

def _field_is_visible(field_def: dict[str, Any], values: dict[str, Any]) -> bool:
    rule = field_def.get("visible_when")
    if not isinstance(rule, dict):
        return True
    current_value = values.get(rule.get("field"))
    current_values = current_value if isinstance(current_value, list) else [current_value]
    if "equals" in rule:
        return any(_condition_matches(value, rule["equals"]) for value in current_values)
    return any(_condition_matches(value, expected) for value in current_values for expected in rule.get("in") or [])


def _condition_matches(current: Any, expected: Any) -> bool:
    if isinstance(current, bool):
        try:
            return current is _normalize_checkbox(expected)
        except ValueError:
            return False
    return ("" if current is None else str(current).strip()) == ("" if expected is None else str(expected).strip())


def _normalize_checkbox(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError("invalid checkbox")


def _condition_values(raw_value: Any) -> set[str]:
    if isinstance(raw_value, (list, tuple, set)):
        return {str(item).strip() for item in raw_value if str(item).strip()}
    text_value = "" if raw_value is None else str(raw_value).strip()
    return {text_value}


def _normalize_field_value(field_def: dict[str, Any], raw_value: Any) -> Any:
    field_type = field_def.get("type")
    if field_type == "checkbox":
        return _normalize_checkbox(raw_value)
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
    try:
        _validate_field_pattern(field_def)
    except ValueError:
        return "Ошибка настройки формата поля. Обратитесь в поддержку."
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
                return "Ошибка настройки формата поля. Обратитесь в поддержку."
        if field_type == "email" and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", text_value):
            return "Укажите корректный email."
        if field_type == "url" and not _is_valid_url(text_value):
            return "Укажите корректную ссылку."
    return None


def _validate_field_pattern(field_def: dict[str, Any]) -> None:
    pattern = _validation_string(field_def, ("pattern", "regex"))
    if not pattern:
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError("invalid validation pattern/regex") from exc
    if _has_python_only_pattern_syntax(pattern):
        raise ValueError("validation pattern/regex must use shared Python/JavaScript syntax")


def _has_python_only_pattern_syntax(pattern: str) -> bool:
    """Inspect tokens, keeping escaped literals and character classes intact."""
    in_class = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            if index + 1 < len(pattern) and pattern[index + 1] in "AZzNUG":
                return True
            index += 2
            continue
        if char == "[" and not in_class:
            in_class = True
        elif char == "]" and in_class:
            in_class = False
        elif not in_class:
            if pattern.startswith("(?", index) and index + 2 < len(pattern):
                if pattern[index + 2] in "PaiLmsux->(#":
                    return True
            if char in "+*?" and pattern[index + 1:index + 2] == "+":
                return True
            if char == "{" and re.match(r"\{\d+(?:,\d*)?\}\+", pattern[index:]):
                return True
        index += 1
    return False


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
            errors.pop(key, None)
            continue
        if key in errors:
            continue
        value = normalized_values.get(key)
        validation = field_def.get("validation") if isinstance(field_def.get("validation"), dict) else {}
        if validation.get("optional_when_legacy_missing") and key not in raw_values:
            continue
        if field_def.get("required"):
            if field_def.get("type") == "checkbox":
                is_empty = value is False
            elif field_def.get("type") == "number":
                is_empty = value is None
            elif isinstance(value, list):
                is_empty = not value
            elif isinstance(value, dict):
                is_empty = not any(str(item or "").strip() for item in value.values())
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
    defined_field_keys = {str(field.get("key") or "") for field in form.get("fields") or []}
    for key in sorted(item for item in priority_field_keys if item):
        if key in defined_field_keys or key in submitted_values or key not in raw_values:
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
