"""Resolve ticket creation form submissions from legacy packs or the helpdesk registry."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.repos import TicketFormPacksRepo
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    resolve_ticket_form_pack,
    validate_form_pack_schema,
    validate_form_submission,
)


def _field_from_schema(raw_field: dict[str, Any]) -> dict[str, Any]:
    field = {
        "key": raw_field.get("key"),
        "label": raw_field.get("label"),
        "type": raw_field.get("type") or "text",
        "required": bool(raw_field.get("required")),
        "options": deepcopy(raw_field.get("options") or []),
        "validation": deepcopy(raw_field.get("validation") or {}),
        "process_mapping": deepcopy(raw_field.get("process_mapping") or {}),
    }
    visibility = raw_field.get("visibility")
    if isinstance(visibility, dict) and visibility:
        field["visible_when"] = deepcopy(visibility)
    return field


def _registry_pack_from_template(
    *,
    effective_template: dict[str, Any],
    form_schema: dict[str, Any],
    form_key: str,
) -> dict[str, Any]:
    template = effective_template.get("request_template") or {}
    resolved_policies = effective_template.get("resolved_policies") or {}
    policy_refs = effective_template.get("policy_refs") or {}
    config = template.get("config") if isinstance(template.get("config"), dict) else {}
    source_form = config.get("form") if isinstance(config.get("form"), dict) else {}
    field_roles = config.get("field_roles") if isinstance(config.get("field_roles"), dict) else {}

    raw_form: dict[str, Any] = {
        "key": form_key,
        "request_template_key": template.get("template_code") or form_key,
        "request_template_title": template.get("public_title") or form_schema.get("title") or form_key,
        "request_kind": (form_schema.get("config") or {}).get("request_kind") or source_form.get("request_kind") or form_key,
        "title": form_schema.get("title") or template.get("public_title") or form_key,
        "description": form_schema.get("description") or template.get("description") or "",
        "ticket_type": template.get("ticket_type") or form_schema.get("ticket_type") or "incident",
        "category_id": template.get("category_id"),
        "service_id": template.get("service_id"),
        "subcategory_id": template.get("subcategory_id"),
        "form_schema_id": form_schema.get("schema_id"),
        "workflow_profile_id": template.get("workflow_profile_id"),
        "priority_policy_code": template.get("priority_policy_code"),
        "routing_policy_code": template.get("routing_policy_code"),
        "sla_policy_id": template.get("sla_policy_id"),
        "sla_policy_code": template.get("sla_policy_code"),
        "ola_policy_code": template.get("ola_policy_code"),
        "approval_policy_code": template.get("approval_policy_code"),
        "diagnostic_policy_code": template.get("diagnostic_policy_code"),
        "closure_policy_code": template.get("closure_policy_code"),
        "visibility_policy_code": template.get("visibility_policy_code"),
        "notification_policy_code": template.get("notification_policy_code"),
        "reporting_policy_code": template.get("reporting_policy_code"),
        "policy_refs": deepcopy(policy_refs),
        "field_roles": deepcopy(field_roles),
        "fields": [_field_from_schema(field) for field in form_schema.get("fields") or []],
    }
    for target_key, raw_version in (
        ("form_schema_version", form_schema.get("version")),
        ("request_template_version", template.get("version")),
    ):
        version_text = str(raw_version or "").strip()
        if version_text.isdigit():
            raw_form[target_key] = int(version_text)
    for kind in (
        "priority",
        "routing",
        "sla",
        "approval",
        "diagnostic",
        "ola",
        "closure",
        "visibility",
        "notification",
        "reporting",
    ):
        policy = resolved_policies.get(kind)
        if isinstance(policy, dict) and policy:
            raw_form[f"{kind}_policy"] = deepcopy(policy)
    return validate_form_pack_schema(
        {
            "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
            "version": form_schema.get("version") or template.get("version") or "1.0.0",
            "title": "Helpdesk model registry",
            "forms": [raw_form],
        }
    )


def _find_registry_form_schema(
    schemas: list[dict[str, Any]],
    *,
    template_code: str,
    requested_form_key: str,
    preferred_schema_id: str | None,
) -> dict[str, Any] | None:
    for schema in schemas:
        if preferred_schema_id and schema.get("schema_id") == preferred_schema_id:
            return schema
    for schema in schemas:
        if schema.get("request_template_code") == template_code:
            return schema
    for schema in schemas:
        if schema.get("form_key") == requested_form_key or schema.get("schema_id") == requested_form_key:
            return schema
    return None


async def resolve_create_form_submission(
    session: Any,
    *,
    pack_key: str,
    pack_version: str | None,
    form_key: str,
    request_template_key: str,
    raw_values: Any,
) -> dict[str, Any]:
    """Validate a ticket creation form payload from either legacy packs or standalone registry templates."""

    try:
        form_pack = await resolve_ticket_form_pack(
            TicketFormPacksRepo(session),
            pack_key=pack_key,
            version=pack_version,
        )
        return validate_form_submission(
            form_pack,
            form_key=form_key,
            raw_values=raw_values or {},
        )
    except ValueError as legacy_error:
        template_code = str(request_template_key or form_key or "").strip()
        if not template_code:
            raise legacy_error
        repo = HelpdeskPolicyRepo(session)
        try:
            effective_template = await repo.resolve_effective_request_template(
                template_code=template_code,
                raise_if_missing=False,
            )
        except ValueError:
            effective_template = {}
        template = effective_template.get("request_template") if isinstance(effective_template, dict) else {}
        if not isinstance(template, dict) or not template:
            raise legacy_error
        schemas = await repo.list_form_schemas(include_inactive=False)
        form_schema = _find_registry_form_schema(
            schemas,
            template_code=str(template.get("template_code") or template_code),
            requested_form_key=form_key,
            preferred_schema_id=template.get("form_schema_id"),
        )
        if not form_schema:
            raise legacy_error
        registry_form_key = str(
            form_schema.get("form_key") or template.get("template_code") or form_key
        ).strip()
        registry_pack = _registry_pack_from_template(
            effective_template=effective_template,
            form_schema=form_schema,
            form_key=registry_form_key,
        )
        return validate_form_submission(
            registry_pack,
            form_key=registry_form_key,
            raw_values=raw_values or {},
        )
