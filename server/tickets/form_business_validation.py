"""Business preflight validation for request-form packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


POLICY_REF_FIELDS = {
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


@dataclass(frozen=True)
class FormBusinessValidationContext:
    queue_ids: set[int] | None = None
    queue_codes: set[str] | None = None
    queue_ola_queue_ids: set[int] | None = None
    sla_policy_ids: set[int] | None = None
    playbook_keys: set[str] | None = None
    diagnostic_playbook_keys: set[str] | None = None
    policy_refs: dict[str, set[str]] = field(default_factory=dict)
    base_pack: dict[str, Any] | None = None


@dataclass(frozen=True)
class FormBusinessValidationReport:
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


def _issue(
    code: str,
    message: str,
    *,
    path: str | None = None,
    severity: str = "error",
    blocking: bool | None = None,
    recommendation: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "path": path,
        "severity": severity,
        "blocking": severity == "error" if blocking is None else blocking,
        "recommendation": recommendation,
        "source": source,
    }


def _path(form_index: int, suffix: str) -> str:
    return f"forms[{form_index}].{suffix}"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "required", "on"}
    return bool(value)


def _field_roles(form: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    raw_roles = _as_dict(form.get("field_roles"))
    for field_key, values in raw_roles.items():
        if isinstance(values, list):
            roles[str(field_key)] = {str(item) for item in values if str(item or "").strip()}
        elif values:
            roles[str(field_key)] = {str(values)}

    for field in fields:
        key = str(field.get("key") or "")
        mapping = _as_dict(field.get("process_mapping"))
        for raw in (mapping.get("roles"), mapping.get("role")):
            if isinstance(raw, list):
                roles.setdefault(key, set()).update(str(item) for item in raw if str(item or "").strip())
            elif raw:
                roles.setdefault(key, set()).add(str(raw))
    return roles


def _has_role(roles: dict[str, set[str]], role: str) -> bool:
    return any(role in values for values in roles.values())


def _fields_with_role(roles: dict[str, set[str]], role: str) -> list[str]:
    return [field_key for field_key, values in roles.items() if role in values]


def _fields_by_key(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(field.get("key") or "").strip(): field
        for field in fields
        if str(field.get("key") or "").strip()
    }


def _has_priority_facts(form: dict[str, Any], roles: dict[str, set[str]], field_keys: set[str]) -> bool:
    priority_roles = {"priority_impact", "priority_urgency", "priority_importance", "priority_field"}
    if any(priority_roles & values for values in roles.values()):
        return True
    policy = _as_dict(form.get("priority_policy"))
    for key in ("impact_field", "urgency_field", "importance_field"):
        if str(policy.get(key) or "").strip() in field_keys:
            return True
    return False


def _singleton_role_duplicates(roles: dict[str, set[str]]) -> dict[str, list[str]]:
    singleton_roles = {"priority_impact", "priority_urgency", "priority_importance"}
    by_role: dict[str, list[str]] = {role: [] for role in singleton_roles}
    for field_key, field_roles in roles.items():
        for role in singleton_roles & field_roles:
            by_role[role].append(field_key)
    return {role: field_keys for role, field_keys in by_role.items() if len(field_keys) > 1}


def _iter_routing_targets(form: dict[str, Any]) -> list[tuple[str, Any, str]]:
    targets: list[tuple[str, Any, str]] = []
    if form.get("default_queue_id") is not None:
        targets.append(("id", form.get("default_queue_id"), "default_queue_id"))
    if form.get("default_queue_code"):
        targets.append(("code", form.get("default_queue_code"), "default_queue_code"))

    routing_policy = _as_dict(form.get("routing_policy"))
    for index, rule in enumerate(_as_list(routing_policy.get("rules"))):
        if not isinstance(rule, dict):
            continue
        action = _as_dict(rule.get("action"))
        for source, base_path in ((rule, f"routing_policy.rules[{index}]"), (action, f"routing_policy.rules[{index}].action")):
            if source.get("target_queue_id") is not None:
                targets.append(("id", source.get("target_queue_id"), f"{base_path}.target_queue_id"))
            if source.get("queue_id") is not None:
                targets.append(("id", source.get("queue_id"), f"{base_path}.queue_id"))
            for key in ("target_queue_code", "queue_code"):
                if source.get(key):
                    targets.append(("code", source.get(key), f"{base_path}.{key}"))
    return targets


def _iter_playbook_keys(form: dict[str, Any]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    suggested = str(form.get("suggested_playbook_id") or "").strip()
    if suggested:
        keys.append((suggested, "suggested_playbook_id"))

    for index, trigger in enumerate(_as_list(form.get("playbook_triggers"))):
        if isinstance(trigger, dict) and _truthy(trigger.get("enabled", True)):
            key = str(trigger.get("playbook_key") or "").strip()
            if key:
                keys.append((key, f"playbook_triggers[{index}].playbook_key"))

    diagnostic = _as_dict(form.get("diagnostic_policy"))
    for index, item in enumerate(_as_list(diagnostic.get("suggested_playbooks"))):
        if isinstance(item, str) and item.strip():
            keys.append((item.strip(), f"diagnostic_policy.suggested_playbooks[{index}]"))
        elif isinstance(item, dict):
            key = str(item.get("playbook_key") or item.get("key") or "").strip()
            if key:
                keys.append((key, f"diagnostic_policy.suggested_playbooks[{index}]"))
    return keys


def _has_ola_policy(form: dict[str, Any]) -> bool:
    if form.get("ola_policy_ref") or form.get("ola_policy_code"):
        return True
    policy_refs = _as_dict(form.get("policy_refs"))
    if policy_refs.get("ola"):
        return True
    ola_policy = _as_dict(form.get("ola_policy"))
    return bool(ola_policy)


def _needs_preview_sample(form: dict[str, Any]) -> bool:
    process_keys = (
        "default_queue_id",
        "default_queue_code",
        "sla_policy_id",
        "suggested_playbook_id",
        "priority_policy_ref",
        "routing_policy_ref",
        "sla_policy_ref",
        "ola_policy_ref",
        "approval_policy_ref",
        "diagnostic_policy_ref",
        "closure_policy_ref",
        "priority_policy_code",
        "routing_policy_code",
        "sla_policy_code",
        "ola_policy_code",
        "approval_policy_code",
        "diagnostic_policy_code",
        "closure_policy_code",
    )
    if any(form.get(key) for key in process_keys):
        return True
    if _as_list(form.get("playbook_triggers")):
        return True
    for key in (
        "priority_policy",
        "routing_policy",
        "sla_policy",
        "ola_policy",
        "approval_policy",
        "diagnostic_policy",
        "closure_policy",
    ):
        if _as_dict(form.get(key)):
            return True
    return False


def _has_preview_sample(form: dict[str, Any]) -> bool:
    for key in ("route_preview_examples", "process_preview_examples", "preview_samples"):
        value = form.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _form_by_key(pack: dict[str, Any] | None, form_key: str) -> dict[str, Any] | None:
    for form in _as_list((pack or {}).get("forms")):
        if isinstance(form, dict) and str(form.get("key") or "").strip() == form_key:
            return form
    return None


def _alias_values(form: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    field_aliases = _as_dict(form.get("field_aliases"))
    for key, value in field_aliases.items():
        aliases.add(str(key or "").strip())
        aliases.add(str(value or "").strip())
        if isinstance(value, list):
            aliases.update(str(item or "").strip() for item in value)
    for field in _as_list(form.get("fields")):
        if not isinstance(field, dict):
            continue
        aliases.add(str(field.get("alias_from") or "").strip())
        aliases.update(str(item or "").strip() for item in _as_list(field.get("aliases")))
    aliases.discard("")
    return aliases


def _has_field_migration_note(form: dict[str, Any]) -> bool:
    return bool(
        str(form.get("field_migration_note") or "").strip()
        or str(_as_dict(form.get("migration")).get("field_key_note") or "").strip()
    )


def _approval_requires_source(policy: dict[str, Any]) -> bool:
    if not _truthy(policy.get("required")):
        return False
    source_keys = {
        "approver_source",
        "approver_source_kind",
        "source",
        "source_type",
        "approver_role",
        "approver_group",
        "approver_field",
    }
    if any(str(policy.get(key) or "").strip() for key in source_keys):
        return False
    return not any(policy.get(key) for key in ("approvers", "approver_user_ids", "approver_groups"))


def _closure_requires_evidence(policy: dict[str, Any]) -> bool:
    evidence = _as_dict(policy.get("evidence"))
    before_resolved = _as_dict(policy.get("before_resolved"))
    return any(
        _truthy(value)
        for value in (
            policy.get("evidence_required"),
            policy.get("require_evidence"),
            evidence.get("required"),
            evidence.get("required_for_resolution"),
            before_resolved.get("evidence_required"),
        )
    )


def _diagnostic_autorun_enabled(form: dict[str, Any]) -> bool:
    diagnostic = _as_dict(form.get("diagnostic_policy"))
    auto_run = _as_dict(diagnostic.get("auto_run"))
    if _truthy(auto_run.get("enabled")):
        return True
    for trigger in _as_list(form.get("playbook_triggers")):
        if isinstance(trigger, dict) and _truthy(trigger.get("enabled", True)):
            return True
    return False


def _diagnostic_input_has_param_mapping(
    *,
    form: dict[str, Any],
    field: dict[str, Any],
    field_key: str,
) -> bool:
    mapping = _as_dict(field.get("process_mapping"))
    for key in (
        "diagnostic_param",
        "diagnostic_parameter",
        "playbook_param",
        "playbook_parameter",
    ):
        if str(mapping.get(key) or "").strip():
            return True
    for key in ("diagnostic_params", "playbook_params", "param_mappings"):
        value = mapping.get(key)
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and value:
            return True

    diagnostic = _as_dict(form.get("diagnostic_policy"))
    for key in ("input_mappings", "field_mappings", "param_mappings", "playbook_params"):
        mappings = diagnostic.get(key)
        if not isinstance(mappings, dict):
            continue
        if field_key in mappings:
            return True
        if field_key in {str(value or "").strip() for value in mappings.values()}:
            return True
    return False


def _approval_source_config(policy: dict[str, Any]) -> tuple[str, str]:
    source = _as_dict(policy.get("approver_source"))
    source_type = str(
        source.get("type")
        or policy.get("approver_source_kind")
        or policy.get("source_type")
        or policy.get("approver_source")
        or policy.get("source")
        or ""
    ).strip()
    source_field = str(
        source.get("field")
        or policy.get("approver_field")
        or policy.get("approval_subject_field")
        or ""
    ).strip()
    return source_type, source_field


def _approval_subject_is_compatible(field: dict[str, Any]) -> bool:
    field_type = str(field.get("type") or "").strip()
    if field_type in {"user_picker", "service_picker"}:
        return True
    mapping = _as_dict(field.get("process_mapping"))
    subject_type = str(
        mapping.get("approval_subject_type")
        or mapping.get("subject_type")
        or mapping.get("approval_type")
        or ""
    ).strip()
    return subject_type in {"user", "service", "role", "group"}


def _closure_evidence_is_compatible(field: dict[str, Any]) -> bool:
    field_type = str(field.get("type") or "").strip()
    if field_type in {"file", "url", "textarea", "text"}:
        return True
    mapping = _as_dict(field.get("process_mapping"))
    evidence_type = str(
        mapping.get("closure_evidence_type")
        or mapping.get("evidence_type")
        or mapping.get("artifact_type")
        or ""
    ).strip()
    return evidence_type in {
        "file",
        "attachment",
        "url",
        "text",
        "worklog",
        "operation_log",
        "approval",
        "passport_fact",
    }


def _add_policy_ref_errors(
    *,
    form: dict[str, Any],
    form_index: int,
    context: FormBusinessValidationContext,
    errors: list[dict[str, Any]],
) -> None:
    for kind, fields in POLICY_REF_FIELDS.items():
        known_refs = context.policy_refs.get(kind)
        if known_refs is None:
            continue
        checked_refs: set[str] = set()
        for field_name in fields:
            ref = str(form.get(field_name) or "").strip()
            if ref:
                checked_refs.add(ref)
            if ref and ref not in known_refs:
                errors.append(
                    _issue(
                        "POLICY_REF_NOT_FOUND",
                        f"Policy {kind} with key {ref} was not found or is inactive.",
                        path=_path(form_index, field_name),
                        source="policy_ref",
                    )
                )
        refs = _as_dict(form.get("policy_refs"))
        raw_ref = refs.get(kind)
        if isinstance(raw_ref, dict):
            ref = str(raw_ref.get("code") or "").strip()
        else:
            ref = str(raw_ref or "").strip()
        if ref in checked_refs:
            continue
        if ref and ref not in known_refs:
            errors.append(
                _issue(
                    "POLICY_REF_NOT_FOUND",
                    f"Policy {kind} with key {ref} was not found or is inactive.",
                    path=_path(form_index, f"policy_refs.{kind}"),
                    source="policy_ref",
                )
            )


def validate_form_pack_business(
    pack: dict[str, Any],
    *,
    context: FormBusinessValidationContext | None = None,
) -> FormBusinessValidationReport:
    context = context or FormBusinessValidationContext()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    forms = [form for form in _as_list(pack.get("forms")) if isinstance(form, dict)]
    for form_index, form in enumerate(forms):
        fields = [field for field in _as_list(form.get("fields")) if isinstance(field, dict)]
        field_keys = {str(field.get("key") or "") for field in fields if str(field.get("key") or "").strip()}
        field_by_key = _fields_by_key(fields)
        roles = _field_roles(form, fields)
        for role, field_keys_for_role in sorted(_singleton_role_duplicates(roles).items()):
            errors.append(
                _issue(
                    "FIELD_ROLE_DUPLICATE_SINGLETON",
                    f"Role {role} can be assigned to only one field, but it is used by: {', '.join(field_keys_for_role)}.",
                    path=_path(form_index, "field_roles"),
                    recommendation=f"Keep one field with role={role} or move the others to a non-singleton role.",
                )
            )

        title = str(form.get("title") or "").strip()
        if not title or title.lower() in {str(form.get("key") or "").strip().lower(), "form", "template"}:
            warnings.append(
                _issue(
                    "PUBLIC_TITLE_MISSING",
                    "The form does not have a clear public title.",
                    path=_path(form_index, "title"),
                    severity="warning",
                    blocking=False,
                    recommendation="Add a user-facing title.",
                )
            )

        if not _has_priority_facts(form, roles, field_keys):
            warnings.append(
                _issue(
                    "PRIORITY_FACT_FIELDS_MISSING",
                    "The form does not contain impact, urgency, or importance questions.",
                    path=_path(form_index, "field_roles"),
                    severity="warning",
                    blocking=False,
                    recommendation="Add priority_impact, priority_urgency, and priority_importance roles.",
                )
            )

        if not (
            form.get("sla_policy_id")
            or form.get("sla_policy_ref")
            or form.get("sla_policy_code")
            or _as_dict(form.get("policy_refs")).get("sla")
            or isinstance(form.get("sla_policy"), dict) and form.get("sla_policy")
        ):
            warnings.append(
                _issue(
                    "SLA_POLICY_MISSING",
                    "The form does not define an SLA policy.",
                    path=_path(form_index, "sla_policy"),
                    severity="warning",
                    blocking=False,
                    recommendation="Attach an SLA policy ref or a legacy SLA policy.",
                )
            )

        if _needs_preview_sample(form) and not _has_preview_sample(form):
            warnings.append(
                _issue(
                    "PREVIEW_SAMPLE_MISSING",
                    "The form does not have saved route/process preview samples.",
                    path=_path(form_index, "process_preview_examples"),
                    severity="warning",
                    blocking=False,
                    recommendation="Save at least one route or process preview example for publication review.",
                )
            )

        base_form = _form_by_key(context.base_pack, str(form.get("key") or "").strip())
        if base_form is not None:
            base_field_keys = {
                str(field.get("key") or "").strip()
                for field in _as_list(base_form.get("fields"))
                if isinstance(field, dict) and str(field.get("key") or "").strip()
            }
            removed_field_keys = base_field_keys - field_keys
            uncovered_removed_keys = removed_field_keys - _alias_values(form)
            if uncovered_removed_keys and not _has_field_migration_note(form):
                warnings.append(
                    _issue(
                        "FIELD_KEY_CHANGED_WITHOUT_ALIAS",
                        "One or more field keys changed compared with the base version without alias or migration note.",
                        path=_path(form_index, "fields"),
                        severity="warning",
                        blocking=False,
                        recommendation=(
                            "Add field_aliases, field aliases, or field_migration_note before publishing."
                        ),
                    )
                )

        for field_index, field in enumerate(fields):
            field_key = str(field.get("key") or "").strip()
            visible_when = _as_dict(field.get("visible_when"))
            if visible_when:
                dependency = str(visible_when.get("field") or "").strip()
                if dependency and dependency not in field_keys:
                    errors.append(
                        _issue(
                            "VISIBLE_WHEN_FIELD_NOT_FOUND",
                            f"Field {field_key} depends on missing field {dependency}.",
                            path=_path(form_index, f"fields[{field_index}].visible_when.field"),
                        )
                    )
                if bool(field.get("required")) and not (visible_when.get("equals") or visible_when.get("in")):
                    errors.append(
                        _issue(
                            "REQUIRED_FIELD_HIDDEN_WITHOUT_CONDITION",
                            f"Required field {field_key} is hidden without a checkable condition.",
                            path=_path(form_index, f"fields[{field_index}].visible_when"),
                        )
                    )

            if bool(field.get("required")) and not str(field.get("help_text") or "").strip():
                warnings.append(
                    _issue(
                        "REQUIRED_FIELD_HELP_TEXT_MISSING",
                        f"Required field {field_key} does not contain help text.",
                        path=_path(form_index, f"fields[{field_index}].help_text"),
                        severity="warning",
                        blocking=False,
                        recommendation="Add help text for the required field.",
                    )
                )

        for target_kind, target_value, target_path in _iter_routing_targets(form):
            if target_kind == "id" and context.queue_ids is not None:
                try:
                    queue_id = int(target_value)
                except (TypeError, ValueError):
                    queue_id = -1
                if queue_id not in context.queue_ids:
                    errors.append(
                        _issue(
                            "ROUTING_QUEUE_NOT_FOUND",
                            f"Routing policy references missing queue {target_value}.",
                            path=_path(form_index, target_path),
                        )
                    )
            if target_kind == "code" and context.queue_codes is not None:
                queue_code = str(target_value or "").strip()
                if queue_code and queue_code not in context.queue_codes:
                    errors.append(
                        _issue(
                            "ROUTING_QUEUE_NOT_FOUND",
                            f"Routing policy references missing queue {queue_code}.",
                            path=_path(form_index, target_path),
                        )
                    )

        if form.get("sla_policy_id") is not None and context.sla_policy_ids is not None:
            try:
                sla_policy_id = int(form.get("sla_policy_id"))
            except (TypeError, ValueError):
                sla_policy_id = -1
            if sla_policy_id not in context.sla_policy_ids:
                errors.append(
                    _issue(
                        "SLA_POLICY_NOT_FOUND",
                        f"SLA policy {form.get('sla_policy_id')} was not found or is inactive.",
                        path=_path(form_index, "sla_policy_id"),
                    )
                )

        if form.get("default_queue_id") is not None and context.queue_ola_queue_ids is not None:
            try:
                queue_id = int(form.get("default_queue_id"))
            except (TypeError, ValueError):
                queue_id = -1
            if queue_id in context.queue_ola_queue_ids and not _has_ola_policy(form):
                errors.append(
                    _issue(
                        "OLA_POLICY_MISSING",
                        f"Queue {queue_id} has OLA targets, but the form does not define an OLA policy.",
                        path=_path(form_index, "ola_policy"),
                    )
                )

        for playbook_key, playbook_path in _iter_playbook_keys(form):
            if context.playbook_keys is not None and playbook_key not in context.playbook_keys:
                errors.append(
                    _issue(
                        "DIAGNOSTIC_PLAYBOOK_NOT_FOUND",
                        f"Diagnostic playbook {playbook_key} was not found.",
                        path=_path(form_index, playbook_path),
                    )
                )
                continue
            if (
                context.diagnostic_playbook_keys is not None
                and playbook_key not in context.diagnostic_playbook_keys
            ):
                errors.append(
                    _issue(
                        "DIAGNOSTIC_PLAYBOOK_NOT_DIAGNOSTIC_SAFE",
                        f"Playbook {playbook_key} is not marked as diagnostic-safe.",
                        path=_path(form_index, playbook_path),
                    )
                )

        approval_policy = _as_dict(form.get("approval_policy"))
        if _approval_requires_source(approval_policy):
            errors.append(
                _issue(
                    "APPROVAL_APPROVER_SOURCE_MISSING",
                    "Approval policy requires approval, but approver source is not set.",
                    path=_path(form_index, "approval_policy"),
                )
            )
        if _truthy(approval_policy.get("required")):
            approval_source_type, approval_source_field = _approval_source_config(approval_policy)
            approval_subject_fields = _fields_with_role(roles, "approval_subject")
            if approval_source_type == "form_field":
                if not approval_source_field:
                    errors.append(
                        _issue(
                            "APPROVAL_SUBJECT_FIELD_MISSING",
                            "Approval policy uses form_field approver source, but the source field is not set.",
                            path=_path(form_index, "approval_policy.approver_source.field"),
                        )
                    )
                elif approval_source_field not in field_by_key:
                    errors.append(
                        _issue(
                            "APPROVAL_SUBJECT_FIELD_NOT_FOUND",
                            f"Approval policy references missing approver field {approval_source_field}.",
                            path=_path(form_index, "approval_policy.approver_source.field"),
                        )
                    )
                elif "approval_subject" not in roles.get(approval_source_field, set()):
                    errors.append(
                        _issue(
                            "APPROVAL_SUBJECT_FIELD_ROLE_MISSING",
                            f"Approver field {approval_source_field} must have role=approval_subject.",
                            path=_path(form_index, "field_roles"),
                        )
                    )
            for field_key in approval_subject_fields:
                field = field_by_key.get(field_key)
                if field is not None and not _approval_subject_is_compatible(field):
                    errors.append(
                        _issue(
                            "APPROVAL_SUBJECT_FIELD_INCOMPATIBLE",
                            (
                                f"Field {field_key} has role=approval_subject, but it is not typed as "
                                "user/service/role/group."
                            ),
                            path=_path(form_index, "field_roles"),
                            recommendation=(
                                "Use user_picker/service_picker or set process_mapping.subject_type to user, "
                                "service, role, or group."
                            ),
                        )
                    )

        if _diagnostic_autorun_enabled(form):
            for field_key in _fields_with_role(roles, "diagnostic_input"):
                field = field_by_key.get(field_key)
                if field is not None and not _diagnostic_input_has_param_mapping(
                    form=form,
                    field=field,
                    field_key=field_key,
                ):
                    errors.append(
                        _issue(
                            "DIAGNOSTIC_INPUT_MAPPING_MISSING",
                            f"Field {field_key} has role=diagnostic_input, but no playbook parameter mapping is set.",
                            path=_path(form_index, "field_roles"),
                            recommendation=(
                                "Set process_mapping.diagnostic_param on the field or diagnostic_policy.input_mappings."
                            ),
                        )
                    )

        closure_policy = _as_dict(form.get("closure_policy"))
        if _closure_requires_evidence(closure_policy) and not _has_role(roles, "closure_evidence"):
            errors.append(
                _issue(
                    "CLOSURE_EVIDENCE_FIELD_MISSING",
                    "Closure policy requires evidence, but no field has role=closure_evidence.",
                    path=_path(form_index, "closure_policy"),
                )
            )
        if _closure_requires_evidence(closure_policy):
            for field_key in _fields_with_role(roles, "closure_evidence"):
                field = field_by_key.get(field_key)
                if field is not None and not _closure_evidence_is_compatible(field):
                    errors.append(
                        _issue(
                            "CLOSURE_EVIDENCE_FIELD_INCOMPATIBLE",
                            (
                                f"Field {field_key} has role=closure_evidence, but its type cannot carry "
                                "closure evidence."
                            ),
                            path=_path(form_index, "field_roles"),
                            recommendation=(
                                "Use file, url, text, textarea, or set process_mapping.evidence_type explicitly."
                            ),
                        )
                    )

        _add_policy_ref_errors(form=form, form_index=form_index, context=context, errors=errors)

    summary = {
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "can_publish": not errors,
    }
    return FormBusinessValidationReport(summary=summary, errors=errors, warnings=warnings)
