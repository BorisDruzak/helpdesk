from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
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
from tickets.form_schema_validation import (
    _normalize_option,
    _normalize_visible_when,
    _normalize_condition_value,
    _normalize_optional_int,
    _normalize_optional_dict,
    _normalize_policy_bool,
    _normalize_policy_choice,
    _normalize_on_behalf_policy,
    _normalize_availability_policy,
    _normalize_process_mapping,
    _normalize_field_roles,
    next_form_pack_version,
    validate_form_pack_schema,
)
from tickets.form_field_values import (
    _field_is_visible,
    _condition_matches,
    _normalize_checkbox,
    _condition_values,
    _normalize_field_value,
    _validation_value,
    _validation_number,
    _validation_string,
    _is_text_validation_field,
    _is_valid_url,
    _field_constraint_error,
    _validate_field_pattern,
    validate_form_submission,
)

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
        base_version = _base_version_from_registry_augmented(version)
        if base_version and base_version != version:
            pack = await repo.get_pack(pack_key, base_version)
            if pack is not None and isinstance(pack.schema_json, dict):
                return _finalize(validate_form_pack_schema(pack.schema_json))
            if base_version == builtin.get("version") and pack_key == builtin.get("pack_key"):
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
