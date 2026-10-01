from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Optional
from playbooks.form_triggers import normalize_form_playbook_triggers
from tickets.workflow_profiles import DEFAULT_WORKFLOW_PROFILE
from tickets.form_defaults import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    DEFAULT_TICKET_FORM_PACK_VERSION,
    _REGISTRY_AUGMENTED_VERSION_SEPARATOR,
    ALLOWED_FIELD_TYPES,
    OPTION_FIELD_TYPES,
    OPTION_VALIDATED_FIELD_TYPES,
    MULTI_SELECT_FIELD_TYPES,
    KEY_PATTERN,
    _TICKET_TYPE_BY_FORM_KIND,
    _SETUP_ASSISTANCE_FORM_KEYS,
    DEFAULT_PRIORITY_POLICY,
    DEFAULT_PRIORITY_FIELD_ROLES,
    _base_version_from_registry_augmented,
    _REQUEST_KIND_FALLBACK_LABELS,
    _ROUTING_BASE_FIELDS,
    _ROUTING_OPERATOR_OPTIONS,
    _TEMPLATE_DICT_FIELDS,
    _TEMPLATE_INT_FIELDS,
    _TEMPLATE_VERSION_FIELDS,
    _TEMPLATE_STRING_FIELDS,
    _POLICY_REF_FIELDS,
    _TEMPLATE_LIST_FIELDS,
    _ON_BEHALF_DEFAULT_LABEL,
    _ON_BEHALF_ALLOWED_SCOPES,
    _ON_BEHALF_DIAGNOSTIC_TARGETS,
    _ON_BEHALF_KNOWLEDGE_VISIBILITY,
    _ON_BEHALF_SUPPORT_VISIBILITY,
    _ON_BEHALF_NO_PRIMARY_AGENT_BEHAVIORS,
    _AVAILABILITY_BOOL_FIELDS,
    FIELD_ROLE_OPTIONS,
    FIELD_ROLE_VALUES,
    LEGACY_FIELD_ROLE_VALUES,
    _ALLOWED_FIELD_ROLES,
    build_default_priority_fields,
    _attach_default_priority_context,
    infer_ticket_type_for_form,
    build_default_ticket_form_pack,
)
from tickets.form_field_values import _validate_field_pattern

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
        return {"field": field, "equals": _normalize_condition_value(raw_rule["equals"])}
    values = raw_rule.get("in")
    if isinstance(values, list) and values:
        return {"field": field, "in": [_normalize_condition_value(item) for item in values]}
    raise ValueError("visible_when requires equals or in")


def _normalize_condition_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.strip()
    raise ValueError("visible_when values must be scalar")


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
        field: _normalize_policy_bool(raw_form.get(field, policy.get(field)),
            default=field == "available_without_agent_binding")
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

        normalized_fields, seen_fields = _normalize_fields(raw_fields, form_key)

        priority_policy_refs = _add_priority_compatibility(raw_form, normalized_fields, seen_fields)

        ticket_type = str(
            raw_form.get("ticket_type") or infer_ticket_type_for_form(form_key, request_kind)
        ).strip() or DEFAULT_WORKFLOW_PROFILE
        normalized_field_roles = _normalize_form_roles(raw_form, raw_fields, normalized_fields, seen_fields, priority_policy_refs, form_key)
        template_context = _build_template_context(raw_form, normalized_fields, normalized_field_roles, ticket_type)

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




def _normalize_fields(raw_fields: list, form_key: str) -> tuple[list[dict[str, Any]], set[str]]:
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

        _validate_field_pattern(raw_field)

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

    return normalized_fields, seen_fields


def _add_priority_compatibility(raw_form: dict, normalized_fields: list, seen_fields: set[str]) -> set[str]:
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

    return priority_policy_refs


def _normalize_form_roles(raw_form: dict, raw_fields: list, normalized_fields: list, seen_fields: set[str], priority_policy_refs: set[str], form_key: str) -> dict[str, list[str]]:
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
    return normalized_field_roles


def _build_template_context(raw_form: dict, normalized_fields: list, normalized_field_roles: dict, ticket_type: str) -> dict[str, Any]:
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
    if availability_policy["available_without_agent_binding"]:
        for field in normalized_fields:
            if field.get("type") == "device_picker":
                field["required"] = False
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

    return template_context
