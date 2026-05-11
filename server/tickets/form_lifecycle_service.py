"""Request-form builder draft/publish lifecycle orchestration."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db import get_session
from app.db.models import Playbook, TicketQueue, TicketQueueOlaTarget, TicketSlaPolicy
from app.repos.form_drafts_repo import FormDraftsRepo
from app.repos.helpdesk_policy_repo import POLICY_MODELS
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from auth.context import AuthContext
from tickets.form_business_validation import (
    FormBusinessValidationContext,
    FormBusinessValidationReport,
    validate_form_pack_business,
)
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    build_default_ticket_form_pack,
    next_form_pack_version,
    resolve_ticket_form_pack,
    validate_form_pack_schema,
)
from web_api.dto.admin import (
    AdminFilterOption,
    AdminFormsDraftSaveRequest,
    AdminFormsDraftSaveResult,
    AdminFormsFieldItem,
    AdminFormsFieldOption,
    AdminFormsFormItem,
    AdminFormsPreferredUpdateRequest,
    AdminFormsPreferredUpdateResult,
    AdminFormsPublishRequest,
    AdminFormsPublishResult,
    AdminFormsSaveFieldRequest,
    AdminFormsSaveRequest,
    AdminFormsSaveResult,
    AdminFormsSummary,
    AdminFormsValidateRequest,
    AdminFormsValidateResult,
    AdminFormsVisibleWhen,
)


FORM_FIELD_TYPE_LABELS = {
    "text": "Текст",
    "textarea": "Большой текст",
    "select": "Список",
    "multi_select": "Множественный выбор",
    "radio": "Переключатель",
    "checkbox": "Флажок",
    "date": "Дата",
    "datetime": "Дата и время",
    "file": "Файл",
    "user": "Пользователь",
    "department": "Отдел",
    "location": "Локация",
    "device": "Устройство",
    "service_picker": "Сервис",
}


def form_field_type_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "text"
    return FORM_FIELD_TYPE_LABELS.get(normalized, normalized.replace("_", " "))


def form_field_type_options() -> list[AdminFilterOption]:
    return [
        AdminFilterOption(value=field_type, label=label)
        for field_type, label in FORM_FIELD_TYPE_LABELS.items()
    ]


def map_admin_form_visible_when(raw_rule: dict | None) -> AdminFormsVisibleWhen | None:
    if not isinstance(raw_rule, dict):
        return None
    values = raw_rule.get("in")
    normalized_values = [str(item) for item in values] if isinstance(values, list) else []
    return AdminFormsVisibleWhen(
        field=str(raw_rule.get("field") or ""),
        equals=str(raw_rule.get("equals") or "").strip() or None,
        values=normalized_values,
    )


def map_admin_form_field(raw_field: dict | None) -> AdminFormsFieldItem:
    field = raw_field or {}
    return AdminFormsFieldItem(
        key=str(field.get("key") or ""),
        label=str(field.get("label") or ""),
        type=str(field.get("type") or "text"),
        type_label=form_field_type_label(field.get("type")),
        required=bool(field.get("required", False)),
        placeholder=str(field.get("placeholder") or "").strip() or None,
        help_text=str(field.get("help_text") or "").strip() or None,
        options=[
            AdminFormsFieldOption(
                value=str(option.get("value") or ""),
                label=str(option.get("label") or ""),
            )
            for option in (field.get("options") or [])
            if isinstance(option, dict)
        ],
        visible_when=map_admin_form_visible_when(field.get("visible_when")),
        validation=field.get("validation") if isinstance(field.get("validation"), dict) else {},
        process_mapping=field.get("process_mapping") if isinstance(field.get("process_mapping"), dict) else {},
    )


def map_admin_form_item(raw_form: dict | None) -> AdminFormsFormItem:
    form = raw_form or {}
    return AdminFormsFormItem(
        key=str(form.get("key") or ""),
        request_kind=str(form.get("request_kind") or form.get("key") or ""),
        ticket_type=str(form.get("ticket_type") or "").strip() or None,
        title=str(form.get("title") or ""),
        description=str(form.get("description") or "").strip() or None,
        category_id=form.get("category_id") if form.get("category_id") is not None else None,
        service_id=form.get("service_id") if form.get("service_id") is not None else None,
        subcategory_id=form.get("subcategory_id") if form.get("subcategory_id") is not None else None,
        default_queue_id=form.get("default_queue_id") if form.get("default_queue_id") is not None else None,
        sla_policy_id=form.get("sla_policy_id") if form.get("sla_policy_id") is not None else None,
        suggested_playbook_id=str(form.get("suggested_playbook_id") or "").strip() or None,
        field_roles=form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
        priority_policy=form.get("priority_policy") if isinstance(form.get("priority_policy"), dict) else {},
        routing_policy=form.get("routing_policy") if isinstance(form.get("routing_policy"), dict) else {},
        approval_policy=form.get("approval_policy") if isinstance(form.get("approval_policy"), dict) else {},
        diagnostic_policy=form.get("diagnostic_policy") if isinstance(form.get("diagnostic_policy"), dict) else {},
        ola_policy=form.get("ola_policy") if isinstance(form.get("ola_policy"), dict) else {},
        closure_policy=form.get("closure_policy") if isinstance(form.get("closure_policy"), dict) else {},
        visibility_policy=form.get("visibility_policy") if isinstance(form.get("visibility_policy"), dict) else {},
        notification_policy=form.get("notification_policy") if isinstance(form.get("notification_policy"), dict) else {},
        reporting_policy=form.get("reporting_policy") if isinstance(form.get("reporting_policy"), dict) else {},
        priority_policy_ref=str(form.get("priority_policy_ref") or "").strip() or None,
        routing_policy_ref=str(form.get("routing_policy_ref") or "").strip() or None,
        sla_policy_ref=str(form.get("sla_policy_ref") or "").strip() or None,
        ola_policy_ref=str(form.get("ola_policy_ref") or "").strip() or None,
        approval_policy_ref=str(form.get("approval_policy_ref") or "").strip() or None,
        diagnostic_policy_ref=str(form.get("diagnostic_policy_ref") or "").strip() or None,
        closure_policy_ref=str(form.get("closure_policy_ref") or "").strip() or None,
        visibility_policy_ref=str(form.get("visibility_policy_ref") or "").strip() or None,
        notification_policy_ref=str(form.get("notification_policy_ref") or "").strip() or None,
        reporting_policy_ref=str(form.get("reporting_policy_ref") or "").strip() or None,
        route_preview_examples=form.get("route_preview_examples") if isinstance(form.get("route_preview_examples"), list) else [],
        process_preview_examples=form.get("process_preview_examples") if isinstance(form.get("process_preview_examples"), list) else [],
        field_aliases=form.get("field_aliases") if isinstance(form.get("field_aliases"), dict) else {},
        field_migration_note=str(form.get("field_migration_note") or "").strip() or None,
        fields=[
            map_admin_form_field(field)
            for field in (form.get("fields") or [])
            if isinstance(field, dict)
        ],
        playbook_triggers=[
            {
                "event": str(trigger.get("event") or "ticket_created"),
                "playbook_key": str(trigger.get("playbook_key") or ""),
                "module_kind": str(trigger.get("module_kind") or "diagnostic"),
                "enabled": bool(trigger.get("enabled", True)),
            }
            for trigger in (form.get("playbook_triggers") or [])
            if isinstance(trigger, dict)
        ],
    )


def build_admin_forms_summary(
    pack: dict | None,
    *,
    last_published_at: str | None = None,
    last_published_by: str | None = None,
) -> AdminFormsSummary:
    resolved_pack = pack or validate_form_pack_schema(build_default_ticket_form_pack())
    forms = [form for form in (resolved_pack.get("forms") or []) if isinstance(form, dict)]
    fields = [
        field
        for form in forms
        for field in (form.get("fields") or [])
        if isinstance(field, dict)
    ]
    required_fields_count = sum(1 for field in fields if bool(field.get("required", False)))
    return AdminFormsSummary(
        pack_key=str(resolved_pack.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY),
        version=str(resolved_pack.get("version") or ""),
        title=str(resolved_pack.get("title") or "Каталог заявок"),
        description=str(resolved_pack.get("description") or "").strip() or None,
        forms_count=len(forms),
        fields_count=len(fields),
        required_fields_count=required_fields_count,
        last_published_at=last_published_at,
        last_published_by=last_published_by,
    )


def serialize_admin_form_visible_when(payload: object | None) -> dict | None:
    if payload is None:
        return None
    field = str(getattr(payload, "field", "") or "").strip()
    if not field:
        return None
    equals = str(getattr(payload, "equals", "") or "").strip()
    values = [
        str(item or "").strip()
        for item in (getattr(payload, "values", None) or [])
        if str(item or "").strip()
    ]
    if values:
        return {"field": field, "in": values}
    if equals:
        return {"field": field, "equals": equals}
    return None


def serialize_admin_form_field_request(payload: AdminFormsSaveFieldRequest) -> dict[str, object]:
    field_payload: dict[str, object] = {
        "key": str(payload.key or "").strip(),
        "label": str(payload.label or "").strip(),
        "type": str(payload.type or "").strip().lower() or "text",
        "required": bool(payload.required),
    }
    placeholder = str(payload.placeholder or "").strip()
    if placeholder:
        field_payload["placeholder"] = placeholder
    help_text = str(payload.help_text or "").strip()
    if help_text:
        field_payload["help_text"] = help_text
    if field_payload["type"] in {"select", "radio", "multi_select"}:
        field_payload["options"] = [
            {
                "value": str(option.value or "").strip(),
                "label": str(option.label or "").strip(),
            }
            for option in payload.options
        ]
    visible_when = serialize_admin_form_visible_when(payload.visible_when)
    if visible_when:
        field_payload["visible_when"] = visible_when
    if payload.validation:
        field_payload["validation"] = dict(payload.validation)
    if payload.process_mapping:
        field_payload["process_mapping"] = dict(payload.process_mapping)
    return field_payload


def serialize_admin_form_request(payload) -> dict[str, object]:
    form_payload: dict[str, object] = {
        "key": str(payload.key or "").strip(),
        "request_kind": str(payload.request_kind or payload.key or "").strip(),
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "fields": [serialize_admin_form_field_request(field) for field in payload.fields],
        "playbook_triggers": [
            {
                "event": str(trigger.event or "ticket_created").strip() or "ticket_created",
                "playbook_key": str(trigger.playbook_key or "").strip(),
                "module_kind": str(trigger.module_kind or "diagnostic").strip() or "diagnostic",
                "enabled": bool(trigger.enabled),
            }
            for trigger in getattr(payload, "playbook_triggers", [])
            if str(trigger.playbook_key or "").strip()
        ],
    }
    for key in (
        "ticket_type",
        "suggested_playbook_id",
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
    ):
        value = str(getattr(payload, key, None) or "").strip()
        if value:
            form_payload[key] = value
    for key in ("category_id", "service_id", "subcategory_id", "default_queue_id", "sla_policy_id"):
        value = getattr(payload, key, None)
        if value is not None:
            form_payload[key] = value
    for key in (
        "field_roles",
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
    ):
        value = getattr(payload, key, None)
        if isinstance(value, dict) and value:
            form_payload[key] = value
    for key in ("route_preview_examples", "process_preview_examples"):
        value = getattr(payload, key, None)
        if isinstance(value, list) and value:
            form_payload[key] = [dict(item) for item in value if isinstance(item, dict)]
    field_migration_note = str(getattr(payload, "field_migration_note", None) or "").strip()
    if field_migration_note:
        form_payload["field_migration_note"] = field_migration_note
    return form_payload


def serialize_admin_forms_save_request(payload: AdminFormsSaveRequest) -> dict[str, object]:
    return {
        "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
        "title": str(payload.title or "").strip() or "Каталог заявок",
        "description": str(payload.description or "").strip(),
        "forms": [serialize_admin_form_request(form) for form in payload.forms],
    }


def admin_forms_actor_id(auth_context: AuthContext) -> str:
    return str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"


async def build_form_business_validation_context(
    session,
    *,
    base_pack: dict | None = None,
) -> FormBusinessValidationContext:
    queue_rows = (
        await session.execute(
            select(TicketQueue.id, TicketQueue.code).where(TicketQueue.is_active.is_(True))
        )
    ).all()
    sla_policy_ids = set(
        (
            await session.execute(
                select(TicketSlaPolicy.id).where(TicketSlaPolicy.is_active.is_(True))
            )
        ).scalars().all()
    )
    ola_queue_ids = set(
        (
            await session.execute(select(TicketQueueOlaTarget.queue_id).distinct())
        ).scalars().all()
    )
    playbook_rows = (
        await session.execute(
            select(Playbook.key, Playbook.domain).where(Playbook.archived.is_(False))
        )
    ).all()
    policy_refs: dict[str, set[str]] = {}
    for kind, model in POLICY_MODELS.items():
        policy_refs[kind] = set(
            (
                await session.execute(
                    select(model.code).where(model.is_active.is_(True))
                )
            ).scalars().all()
        )
    return FormBusinessValidationContext(
        queue_ids={int(row.id) for row in queue_rows},
        queue_codes={str(row.code) for row in queue_rows if str(row.code or "").strip()},
        queue_ola_queue_ids={int(queue_id) for queue_id in ola_queue_ids},
        sla_policy_ids={int(policy_id) for policy_id in sla_policy_ids},
        playbook_keys={str(row[0]) for row in playbook_rows if str(row[0] or "").strip()},
        diagnostic_playbook_keys={
            str(row[0])
            for row in playbook_rows
            if str(row[0] or "").strip()
            and str(row[1] or "").strip().lower() in {"diag", "diagnostic", "diagnostics"}
        },
        policy_refs=policy_refs,
        base_pack=base_pack,
    )


def admin_forms_validation_result_from_report(
    report: FormBusinessValidationReport,
) -> AdminFormsValidateResult:
    return AdminFormsValidateResult(
        status="validated",
        summary=report.summary,
        errors=report.errors,
        warnings=report.warnings,
        message=(
            "Preflight validation completed: publication is blocked."
            if report.errors
            else "Preflight validation completed: publication is allowed."
        ),
    )


def assert_business_preflight_allows_publish(report: FormBusinessValidationReport) -> None:
    if not report.errors:
        return
    first_error = report.errors[0]
    code = str(first_error.get("code") or "BUSINESS_VALIDATION_ERROR")
    message = str(first_error.get("message") or "Business validation failed")
    raise ValueError(f"{code}: {message}")


async def save_admin_forms_pack(
    *,
    auth_context: AuthContext,
    payload: AdminFormsSaveRequest,
) -> AdminFormsSaveResult:
    publish_payload = AdminFormsPublishRequest.model_validate(payload.model_dump(mode="json"))
    result = await publish_admin_forms_draft(auth_context=auth_context, payload=publish_payload)
    return AdminFormsSaveResult(
        summary=result.summary,
        forms=result.forms,
        message=result.message,
    )


async def save_admin_forms_draft(
    *,
    auth_context: AuthContext,
    payload: AdminFormsDraftSaveRequest,
) -> AdminFormsDraftSaveResult:
    raw_pack = serialize_admin_forms_save_request(payload)
    normalized_pack = validate_form_pack_schema(raw_pack, require_version=False)
    actor_id = admin_forms_actor_id(auth_context)
    draft_id = str(payload.draft_id or "").strip() or str(uuid.uuid4())

    async with get_session() as session:
        pack_repo = TicketFormPacksRepo(session)
        draft_repo = FormDraftsRepo(session)
        preferred = await pack_repo.get_preferred(DEFAULT_TICKET_FORM_PACK_KEY)
        base_version = str(payload.base_version or (preferred or {}).get("version") or "").strip() or None
        await draft_repo.upsert_draft(
            draft_id=draft_id,
            pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
            base_version=base_version,
            schema_json=normalized_pack,
            status="draft",
            actor_id=actor_id,
        )
        await session.commit()

    return AdminFormsDraftSaveResult(
        draft_id=draft_id,
        pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
        base_version=base_version,
        status="draft",
        summary=build_admin_forms_summary(normalized_pack),
        published_version=None,
        preferred_version=(preferred or {}).get("version"),
        message="Черновик сохранён. Активная версия не изменилась.",
    )


def build_admin_forms_validation_report(payload: AdminFormsValidateRequest) -> AdminFormsValidateResult:
    try:
        validate_form_pack_schema(serialize_admin_forms_save_request(payload), require_version=False)
    except ValueError as exc:
        return AdminFormsValidateResult(
            status="validated",
            summary={"errors_count": 1, "warnings_count": 0, "can_publish": False},
            errors=[
                {
                    "code": "FORM_SCHEMA_INVALID",
                    "message": str(exc) or "Проверьте структуру каталога форм",
                    "path": "forms",
                    "severity": "error",
                    "blocking": True,
                }
            ],
            warnings=[],
            message="Проверка завершена: публикация заблокирована.",
        )
    return AdminFormsValidateResult(
        status="validated",
        summary={"errors_count": 0, "warnings_count": 0, "can_publish": True},
        errors=[],
        warnings=[],
        message="Проверка завершена: публикация разрешена.",
    )


async def validate_admin_forms_draft(
    *,
    payload: AdminFormsValidateRequest,
) -> AdminFormsValidateResult:
    try:
        raw_pack = serialize_admin_forms_save_request(payload)
        normalized_pack = validate_form_pack_schema(raw_pack, require_version=False)
    except ValueError:
        return build_admin_forms_validation_report(payload)

    async with get_session() as session:
        base_version = str(payload.base_version or "").strip()
        base_pack = None
        if base_version:
            pack_repo = TicketFormPacksRepo(session)
            base_pack = await pack_repo.get_pack(DEFAULT_TICKET_FORM_PACK_KEY, base_version)
        context = await build_form_business_validation_context(session, base_pack=base_pack)
    report = validate_form_pack_business(normalized_pack, context=context)
    return admin_forms_validation_result_from_report(report)


async def publish_admin_forms_draft(
    *,
    auth_context: AuthContext,
    payload: AdminFormsPublishRequest,
) -> AdminFormsPublishResult:
    actor_id = admin_forms_actor_id(auth_context)
    prevalidated_pack: dict[str, object] | None = None
    if not payload.draft_id:
        prevalidated_pack = validate_form_pack_schema(
            serialize_admin_forms_save_request(payload),
            require_version=False,
        )

    async with get_session() as session:
        pack_repo = TicketFormPacksRepo(session)
        draft_repo = FormDraftsRepo(session)
        draft = await draft_repo.get_draft(payload.draft_id) if payload.draft_id else None
        raw_pack = draft.schema_json if draft is not None else prevalidated_pack
        normalized_pack = validate_form_pack_schema(raw_pack, require_version=False)
        base_version = str(
            (draft.base_version if draft is not None else payload.base_version) or ""
        ).strip()
        base_pack = await pack_repo.get_pack(DEFAULT_TICKET_FORM_PACK_KEY, base_version) if base_version else None
        context = await build_form_business_validation_context(session, base_pack=base_pack)
        assert_business_preflight_allows_publish(
            validate_form_pack_business(normalized_pack, context=context)
        )
        current = await resolve_ticket_form_pack(pack_repo, pack_key=DEFAULT_TICKET_FORM_PACK_KEY)
        next_version = next_form_pack_version(current.get("version") if isinstance(current, dict) else None)
        while await pack_repo.get_pack(DEFAULT_TICKET_FORM_PACK_KEY, next_version) is not None:
            next_version = next_form_pack_version(next_version)
        normalized_pack["version"] = next_version
        stored_pack = await pack_repo.upsert_pack(
            pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
            version=next_version,
            schema_json=normalized_pack,
            created_by=actor_id,
            notes=str(normalized_pack.get("description") or ""),
        )
        previous_preferred = await pack_repo.get_preferred(DEFAULT_TICKET_FORM_PACK_KEY)
        preferred_version = (previous_preferred or {}).get("version")
        made_preferred = bool(payload.make_preferred)
        if made_preferred:
            preferred = await pack_repo.set_preferred(
                pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
                version=next_version,
                updated_by=actor_id,
            )
            preferred_version = preferred.get("version")
        if draft is not None:
            await draft_repo.mark_published(
                draft_id=draft.id,
                published_version=next_version,
                actor_id=actor_id,
            )
        await session.commit()

    message = (
        f"Каталог опубликован как версия {next_version}. "
        + (
            "Изменения уже активны в /help и в интерфейсе агента."
            if made_preferred
            else "Активная версия не изменилась."
        )
    )
    return AdminFormsPublishResult(
        summary=build_admin_forms_summary(
            normalized_pack,
            last_published_at=stored_pack.created_at.isoformat() if stored_pack.created_at else None,
            last_published_by=stored_pack.created_by or actor_id,
        ),
        forms=[
            map_admin_form_item(form)
            for form in (normalized_pack.get("forms") or [])
            if isinstance(form, dict)
        ],
        published_version=next_version,
        preferred_version=preferred_version,
        made_preferred=made_preferred,
        message=message,
    )


async def set_admin_forms_preferred(
    *,
    auth_context: AuthContext,
    payload: AdminFormsPreferredUpdateRequest,
) -> AdminFormsPreferredUpdateResult:
    actor_id = admin_forms_actor_id(auth_context)
    version = str(payload.version or "").strip()
    if not version:
        raise ValueError("Укажите версию каталога форм")

    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        pack = await repo.get_pack(DEFAULT_TICKET_FORM_PACK_KEY, version)
        if pack is None:
            raise ValueError(f"Версия каталога форм {version} не найдена")
        previous = await repo.get_preferred(DEFAULT_TICKET_FORM_PACK_KEY)
        preferred = await repo.set_preferred(
            pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
            version=version,
            updated_by=actor_id,
        )
        await session.commit()

    return AdminFormsPreferredUpdateResult(
        pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
        previous_version=(previous or {}).get("version"),
        preferred_version=str(preferred.get("version") or version),
        message=f"Активная версия каталога обновлена: {version}.",
    )
