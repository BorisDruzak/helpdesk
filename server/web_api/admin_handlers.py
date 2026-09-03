from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import uuid

from aiohttp import web
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db import get_session
from app.db.models import Device, DeviceToolsetSnapshot, Operation, Playbook, PlaybookStep, PlaybookVersion, Ticket, TicketEvent, TicketQueue
from app.repos.devices_repo import DevicesRepo
from app.repos.helpdesk_policy_repo import (
    POLICY_MODELS,
    HelpdeskPolicyRepo,
    normalize_template_code,
)
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from observer.service import ObserverOverlayService, TraceOverlayFilters
from playbooks.catalog import DIAGNOSTIC_MODULE_CATALOG, SCENARIO_TEMPLATES, normalize_playbook_draft
from diagnostics.capability_registry import CapabilityRegistry
from playbooks.tool_catalog import normalize_capability_catalog_entry, normalize_tool_catalog_entry
from auth.context import AuthContext
from auth.middleware import require_auth
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    FIELD_ROLE_OPTIONS,
    build_form_custom_fields,
    build_default_ticket_form_pack,
    resolve_ticket_form_pack,
    validate_form_pack_schema,
    validate_form_submission,
)
from tickets.form_lifecycle_service import (
    publish_admin_forms_draft as _publish_admin_forms_draft_service,
    save_admin_forms_draft as _save_admin_forms_draft_service,
    save_admin_forms_pack as _save_admin_forms_pack_service,
    set_admin_forms_preferred as _set_admin_forms_preferred_service,
    validate_admin_forms_draft as _validate_admin_forms_draft_service,
)
from tickets.form_process_preview import build_form_process_preview
from tickets.routing_service import (
    FALLBACK_QUEUE_CODE,
    build_form_routing_context,
    find_matching_routing_rule,
)
from tickets.smart_views import validate_smart_view_definition
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.admin import (
    AdminBootstrapPayload,
    AdminObserverDangerousFlowItem,
    AdminObserverDegradationItem,
    AdminObserverQuickLinks,
    AdminObserverQuickPayload,
    AdminObserverQuickSummary,
    AdminObserverQuickTrace,
    AdminObserverRuntimeSummary,
    AdminObserverSignatureItem,
    AdminObserverTraceDetailPayload,
    AdminObserverTraceDetailSummary,
    AdminObserverTraceErrorOccurrenceItem,
    AdminObserverTraceExplanation,
    AdminObserverTraceItem,
    AdminObserverTraceSpanItem,
    AdminObserverTraceSpanLinkItem,
    AdminObserverTracesFilters,
    AdminObserverTracesLinks,
    AdminObserverTracesPayload,
    AdminObserverTracesQuery,
    AdminObserverTracesSummary,
    AdminDeviceItem,
    AdminDeviceCleanupCandidate,
    AdminDeviceCleanupPayload,
    AdminDeviceDuplicateWarning,
    AdminDeviceIdentitySummary,
    AdminDeviceRestorePayload,
    AdminDevicesFilters,
    AdminDevicesPayload,
    AdminDevicesSummary,
    AdminFilterOption,
    AdminFormsBuilderCapabilities,
    AdminFormsDraftSaveRequest,
    AdminFormsDraftSaveResult,
    AdminFormsFieldItem,
    AdminFormsFieldOption,
    AdminFormsFormItem,
    AdminFormsPayload,
    AdminFormsPreferredUpdateRequest,
    AdminFormsPreferredUpdateResult,
    AdminFormsProcessPreviewRequest,
    AdminFormsProcessPreviewResult,
    AdminFormsPublishRequest,
    AdminFormsPublishResult,
    AdminFormsRoutePreviewMatchedRule,
    AdminFormsRoutePreviewRequest,
    AdminFormsRoutePreviewResult,
    AdminFormsRoutePreviewSummaryRow,
    AdminFormsSaveFieldRequest,
    AdminFormsSaveRequest,
    AdminFormsSaveResult,
    AdminFormsSummary,
    AdminFormsValidateRequest,
    AdminFormsValidateResult,
    AdminFormsVisibleWhen,
    AdminHelpdeskModelCapabilities,
    AdminHelpdeskModelPayload,
    AdminHelpdeskModelSummary,
    AdminHelpdeskPolicyDeactivateRequest,
    AdminHelpdeskPolicyDeactivateResult,
    AdminHelpdeskPolicyDiffRequest,
    AdminHelpdeskPolicyDiffResult,
    AdminHelpdeskDataQualityItem,
    AdminHelpdeskPolicyItem,
    AdminHelpdeskFormSchemaItem,
    AdminHelpdeskPublishFormSchemaRequest,
    AdminHelpdeskPublishFormSchemaResult,
    AdminHelpdeskPublishPolicyRequest,
    AdminHelpdeskPublishPolicyResult,
    AdminHelpdeskPublishSmartViewRequest,
    AdminHelpdeskPublishSmartViewResult,
    AdminHelpdeskPublishTicketTypeRequest,
    AdminHelpdeskPublishTicketTypeResult,
    AdminHelpdeskPolicyRollbackRequest,
    AdminHelpdeskPolicyRollbackResult,
    AdminHelpdeskPublishFromFormRequest,
    AdminHelpdeskPublishFromFormResult,
    AdminHelpdeskRepublishLegacyFormsItem,
    AdminHelpdeskRepublishLegacyFormsRequest,
    AdminHelpdeskRepublishLegacyFormsResult,
    AdminHelpdeskRepublishLegacyFormsSummary,
    AdminHelpdeskRequestTemplateItem,
    AdminHelpdeskSmartViewItem,
    AdminHelpdeskTicketTypeDeactivateRequest,
    AdminHelpdeskTicketTypeDeactivateResult,
    AdminHelpdeskTicketTypeItem,
    AdminHelpdeskTicketTypeRollbackRequest,
    AdminHelpdeskTicketTypeRollbackResult,
    AdminObserverCapabilities,
    AdminPlaybookBlockCatalogItem,
    AdminPlaybookBuilderCapabilities,
    AdminPlaybookDraftRequest,
    AdminPlaybookItem,
    AdminPlaybookPayload,
    AdminPlaybookSaveResult,
    AdminScenarioTemplateItem,
)
from utils.versioning import version_key
from utils.versioning import compare_versions


STATUS_OPTIONS = [
    AdminFilterOption(value="all", label="Все устройства"),
    AdminFilterOption(value="online", label="Только онлайн"),
    AdminFilterOption(value="offline", label="Только офлайн"),
]

_IDENTITY_SOURCE_LABELS = {
    "windows_machine_guid": "Windows MachineGuid",
    "linux_machine_id": "Linux machine-id",
    "env_uuid": "Тестовый ENV UUID",
    "env_seed": "Тестовый ENV seed",
}
_STABLE_IDENTITY_SOURCES = {"windows_machine_guid", "linux_machine_id"}

_MODULE_VALIDATION_STATUS_LABELS = {
    "passed": "Проверен",
    "warning": "Есть предупреждения",
    "failed": "Ошибка валидации",
    "unknown": "Статус неизвестен",
}

_MODULE_ROLLOUT_MODE_LABELS = {
    "manual": "Только вручную",
    "installed_devices": "Обновлять установленные устройства",
}

_OS_TYPE_TO_TARGET = {
    "windows": "windows_amd64",
    "windows 11": "windows_amd64",
    "windows 10": "windows_amd64",
    "linux": "linux_alt_x86_64",
    "alt linux": "linux_alt_x86_64",
    "linux_alt": "linux_alt_x86_64",
}

_OBSERVER_ROOT_KIND_LABELS = {
    "ticket": "Тикет",
    "tool_call": "Инструмент",
    "requester_web": "Кабинет пользователя",
    "agent_update": "Обновление агента",
    "module_install": "Установка модуля",
    "module_remove": "Удаление модуля",
    "consent": "Запрос согласия",
}

_OBSERVER_ROOT_KIND_LABELS.update(
    {
        "module_reconcile": "Module reconcile",
        "playbook_run": "Playbook run",
        "web_auth": "Web auth",
        "observer_runtime": "Observer runtime",
    }
)

_OBSERVER_STATUS_LABELS = {
    "queued": "В очереди",
    "sent": "Отправлено",
    "accepted": "Принято агентом",
    "running": "В работе",
    "waiting_consent": "Ждёт согласия",
    "cancel_requested": "Отменяется",
    "succeeded": "Успешно",
    "success": "Успешно",
    "failed": "Ошибка",
    "timed_out": "Таймаут",
    "canceled": "Отменено",
}

_OBSERVER_RUNTIME_STATUS_LABELS = {
    "ok": "Норма",
    "degraded": "Есть отставание",
    "down": "Не запущен",
    "unknown": "Статус неизвестен",
}

_OBSERVER_QUICK_ENDPOINT = "/api/web/admin/observer/quick"
_OBSERVER_TRACES_ENDPOINT = "/api/web/admin/observer/traces"
_OBSERVER_TRACE_DETAIL_TEMPLATE = "/api/web/admin/observer/traces/{trace_id}"
_OBSERVER_RUNTIME_ENDPOINT = "/api/web/admin/observer/runtime"
_OBSERVER_ACTIVE_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
_OBSERVER_ERROR_STATUSES = {"failed", "timed_out", "error"}
_OBSERVER_TRACE_STATUS_OPTIONS = [
    AdminFilterOption(value="all", label="Все статусы"),
    AdminFilterOption(value="running", label="В работе"),
    AdminFilterOption(value="failed", label="С ошибкой"),
    AdminFilterOption(value="succeeded", label="Успешно"),
    AdminFilterOption(value="timed_out", label="Таймаут"),
]
_OBSERVER_TRACE_ROOT_KIND_OPTIONS = [
    AdminFilterOption(value="all", label="Все потоки"),
    AdminFilterOption(value="ticket", label="Тикет"),
    AdminFilterOption(value="tool_call", label="Инструмент"),
    AdminFilterOption(value="requester_web", label="Кабинет пользователя"),
    AdminFilterOption(value="agent_update", label="Обновление агента"),
    AdminFilterOption(value="module_install", label="Установка модуля"),
    AdminFilterOption(value="module_remove", label="Удаление модуля"),
    AdminFilterOption(value="consent", label="Запрос согласия"),
]

_OBSERVER_TRACE_ROOT_KIND_OPTIONS.extend(
    [
        AdminFilterOption(value="module_reconcile", label="Module reconcile"),
        AdminFilterOption(value="playbook_run", label="Playbook run"),
        AdminFilterOption(value="web_auth", label="Web auth"),
        AdminFilterOption(value="observer_runtime", label="Observer runtime"),
    ]
)

_FORMS_CURRENT_ENDPOINT = "/api/web/admin/forms/current"
_FORMS_SAVE_ENDPOINT = "/api/web/admin/forms/save"
_FORMS_PREVIEW_ENDPOINT = "/api/web/admin/forms/route-preview"
_FORMS_PROCESS_PREVIEW_ENDPOINT = "/api/web/admin/forms/process-preview"
_HELPDESK_MODEL_REGISTRY_ENDPOINT = "/api/web/admin/helpdesk-model/policies"
_HELPDESK_MODEL_PUBLISH_FROM_FORM_ENDPOINT = "/api/web/admin/helpdesk-model/request-templates/publish-from-form"
_HELPDESK_MODEL_REPUBLISH_LEGACY_FORMS_ENDPOINT = "/api/web/admin/helpdesk-model/request-templates/republish-legacy-forms"
_HELPDESK_MODEL_PUBLISH_POLICY_ENDPOINT = "/api/web/admin/helpdesk-model/policies/publish"
_HELPDESK_MODEL_POLICY_DIFF_ENDPOINT = "/api/web/admin/helpdesk-model/policies/diff"
_HELPDESK_MODEL_POLICY_DEACTIVATE_ENDPOINT = "/api/web/admin/helpdesk-model/policies/deactivate"
_HELPDESK_MODEL_POLICY_ROLLBACK_ENDPOINT = "/api/web/admin/helpdesk-model/policies/rollback"
_HELPDESK_MODEL_PUBLISH_TICKET_TYPE_ENDPOINT = "/api/web/admin/helpdesk-model/ticket-types/publish"
_HELPDESK_MODEL_TICKET_TYPE_DEACTIVATE_ENDPOINT = "/api/web/admin/helpdesk-model/ticket-types/deactivate"
_HELPDESK_MODEL_TICKET_TYPE_ROLLBACK_ENDPOINT = "/api/web/admin/helpdesk-model/ticket-types/rollback"
_HELPDESK_MODEL_PUBLISH_FORM_SCHEMA_ENDPOINT = "/api/web/admin/helpdesk-model/form-schemas/publish"
_HELPDESK_MODEL_PUBLISH_SMART_VIEW_ENDPOINT = "/api/web/admin/helpdesk-model/smart-views/publish"
_PLAYBOOKS_CATALOG_ENDPOINT = "/api/web/admin/playbooks/catalog"
_PLAYBOOKS_SAVE_ENDPOINT = "/api/web/admin/playbooks/save"
_FORM_FIELD_TYPE_LABELS = {
    "text": "Текст",
    "textarea": "Большой текст",
    "select": "Список",
    "radio": "Переключатель",
    "checkbox": "Флажок",
}


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_status_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"online", "offline"}:
        return normalized
    return "all"


def _truthy_query_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _empty_devices_payload(*, query: str, status_filter: str, include_archived: bool = False) -> AdminDevicesPayload:
    return AdminDevicesPayload(
        query=query,
        status_filter=status_filter,
        summary=AdminDevicesSummary(
            visible_count=0,
            online_count=0,
            duplicate_hosts=0,
            cleanup_candidates=0,
            archived_count=0,
        ),
        filters=AdminDevicesFilters(status_options=STATUS_OPTIONS, include_archived=include_archived),
        devices=[],
    )


def _module_validation_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "unknown"
    return _MODULE_VALIDATION_STATUS_LABELS.get(normalized, normalized.replace("_", " "))


def _module_rollout_mode_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "manual"
    return _MODULE_ROLLOUT_MODE_LABELS.get(normalized, normalized.replace("_", " "))


def _module_tool_ids(manifest_json: dict | None) -> list[str]:
    if not isinstance(manifest_json, dict):
        return []
    tool_ids: list[str] = []
    for raw_tool in manifest_json.get("tools") or []:
        if not isinstance(raw_tool, dict):
            continue
        tool_id = str(raw_tool.get("tool") or raw_tool.get("name") or "").strip()
        if tool_id:
            tool_ids.append(tool_id)
    return tool_ids


def _module_file_exists(module: object) -> bool:
    storage_path = str(getattr(module, "storage_path", "") or "").strip()
    if not storage_path:
        return False
    return (MODULES_STORAGE_DIR / storage_path).exists()


def _pick_primary_module_record(modules: list[object], preferred_version: str | None) -> object | None:
    if not modules:
        return None
    if preferred_version:
        for module in modules:
            if str(getattr(module, "version", "") or "").strip() == preferred_version:
                return module
    return max(
        modules,
        key=lambda module: (
            version_key(str(getattr(module, "version", "") or "")).key,
            getattr(module, "created_at", None).isoformat() if getattr(module, "created_at", None) else "",
        ),
    )


def _map_admin_module_version_item(module: object, *, preferred_version: str | None) -> AdminModuleVersionItem:
    manifest_json = get_module_manifest(module)
    validation_json = get_module_validation(module)
    validation_status = str(validation_json.get("validation_status") or "unknown").strip().lower() or "unknown"
    preflight_status = str(validation_json.get("preflight_status") or "unknown").strip().lower() or "unknown"
    return AdminModuleVersionItem(
        version=str(getattr(module, "version", "") or ""),
        created_at=getattr(module, "created_at", None).isoformat() if getattr(module, "created_at", None) else None,
        uploaded_by=getattr(module, "uploaded_by", None),
        manifest_version=1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version"),
        module_api_version=manifest_json.get("module_api_version"),
        owner_scope=manifest_json.get("owner_scope"),
        validation_status=validation_status,
        validation_status_label=_module_validation_label(validation_status),
        preflight_status=preflight_status,
        preflight_status_label=_module_validation_label(preflight_status),
        is_preferred=preferred_version == str(getattr(module, "version", "") or ""),
        tools_count=len(manifest_json.get("tools") or []),
        platforms=[str(item) for item in (manifest_json.get("platforms") or ["any"])],
        tool_ids=_module_tool_ids(manifest_json),
        warnings_count=len(validation_json.get("warnings") or []),
        file_exists=_module_file_exists(module),
    )


def _empty_admin_modules_payload(*, query: str) -> AdminModulesPayload:
    return AdminModulesPayload(
        query=query,
        summary=AdminModulesSummary(
            visible_count=0,
            preferred_count=0,
            invalid_count=0,
            missing_files_count=0,
        ),
        rollout_settings=AdminModulesRolloutSettings(
            preferred_version_rollout_mode="manual",
            preferred_version_rollout_mode_label=_module_rollout_mode_label("manual"),
            sync_after_preferred_change=True,
        ),
        modules=[],
    )


def _form_field_type_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "text"
    return _FORM_FIELD_TYPE_LABELS.get(normalized, normalized.replace("_", " "))


def _form_field_type_options() -> list[AdminFilterOption]:
    return [
        AdminFilterOption(value=field_type, label=label)
        for field_type, label in _FORM_FIELD_TYPE_LABELS.items()
    ]


def _form_field_role_options() -> list[AdminFilterOption]:
    return [
        AdminFilterOption(value=str(item["value"]), label=str(item["label"]))
        for item in FIELD_ROLE_OPTIONS
    ]


def _map_admin_form_visible_when(raw_rule: dict | None) -> AdminFormsVisibleWhen | None:
    if not isinstance(raw_rule, dict):
        return None
    values = raw_rule.get("in")
    normalized_values = [str(item) for item in values] if isinstance(values, list) else []
    return AdminFormsVisibleWhen(
        field=str(raw_rule.get("field") or ""),
        equals=str(raw_rule.get("equals") or "").strip() or None,
        values=normalized_values,
    )


def _map_admin_form_field(raw_field: dict | None) -> AdminFormsFieldItem:
    field = raw_field or {}
    return AdminFormsFieldItem(
        key=str(field.get("key") or ""),
        label=str(field.get("label") or ""),
        type=str(field.get("type") or "text"),
        type_label=_form_field_type_label(field.get("type")),
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
        visible_when=_map_admin_form_visible_when(field.get("visible_when")),
        validation=field.get("validation") if isinstance(field.get("validation"), dict) else {},
        process_mapping=field.get("process_mapping") if isinstance(field.get("process_mapping"), dict) else {},
    )


def _map_admin_form_item(raw_form: dict | None) -> AdminFormsFormItem:
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
        on_behalf_policy=form.get("on_behalf_policy") if isinstance(form.get("on_behalf_policy"), dict) else {},
        fields=[
            _map_admin_form_field(field)
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


def _build_admin_forms_summary(
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
        title=str(resolved_pack.get("title") or "Каталог обращений"),
        description=str(resolved_pack.get("description") or "").strip() or None,
        forms_count=len(forms),
        fields_count=len(fields),
        required_fields_count=required_fields_count,
        last_published_at=last_published_at,
        last_published_by=last_published_by,
    )


def _build_admin_forms_payload_from_pack(
    pack: dict | None,
    *,
    last_published_at: str | None = None,
    last_published_by: str | None = None,
) -> AdminFormsPayload:
    resolved_pack = pack or validate_form_pack_schema(build_default_ticket_form_pack())
    return AdminFormsPayload(
        summary=_build_admin_forms_summary(
            resolved_pack,
            last_published_at=last_published_at,
            last_published_by=last_published_by,
        ),
        capabilities=AdminFormsBuilderCapabilities(
            current_endpoint=_FORMS_CURRENT_ENDPOINT,
            save_endpoint=_FORMS_SAVE_ENDPOINT,
            preview_endpoint=_FORMS_PREVIEW_ENDPOINT,
            process_preview_endpoint=_FORMS_PROCESS_PREVIEW_ENDPOINT,
            field_type_options=_form_field_type_options(),
            field_role_options=_form_field_role_options(),
        ),
        forms=[
            _map_admin_form_item(form)
            for form in (resolved_pack.get("forms") or [])
            if isinstance(form, dict)
        ],
    )


def _fallback_admin_forms_payload() -> AdminFormsPayload:
    builtin = validate_form_pack_schema(build_default_ticket_form_pack())
    return _build_admin_forms_payload_from_pack(
        builtin,
        last_published_by="builtin_default",
    )


def _serialize_admin_form_visible_when(
    payload: object | None,
) -> dict | None:
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


def _serialize_admin_form_field_request(payload: AdminFormsSaveFieldRequest) -> dict[str, object]:
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
    visible_when = _serialize_admin_form_visible_when(payload.visible_when)
    if visible_when:
        field_payload["visible_when"] = visible_when
    if payload.validation:
        field_payload["validation"] = dict(payload.validation)
    if payload.process_mapping:
        field_payload["process_mapping"] = dict(payload.process_mapping)
    return field_payload


def _serialize_admin_form_request(payload) -> dict[str, object]:
    form_payload: dict[str, object] = {
        "key": str(payload.key or "").strip(),
        "request_kind": str(payload.request_kind or payload.key or "").strip(),
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "fields": [_serialize_admin_form_field_request(field) for field in payload.fields],
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
        "on_behalf_policy",
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


def _serialize_admin_forms_save_request(payload: AdminFormsSaveRequest) -> dict[str, object]:
    return {
        "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
        "title": str(payload.title or "").strip() or "Каталог обращений",
        "description": str(payload.description or "").strip(),
        "forms": [_serialize_admin_form_request(form) for form in payload.forms],
    }


def _map_admin_module_preferred_rollout_summary(
    summary: dict | None,
) -> AdminModulePreferredRolloutSummary | None:
    if not isinstance(summary, dict):
        return None
    return AdminModulePreferredRolloutSummary(
        mode=str(summary.get("mode") or "manual"),
        should_sync=bool(summary.get("should_sync", False)),
        desired_updates=int(summary.get("desired_updates") or 0),
        sync_enqueued=int(summary.get("sync_enqueued") or 0),
        refresh_enqueued=int(summary.get("refresh_enqueued") or 0),
    )


async def _patch_admin_modules_rollout_settings(
    *,
    preferred_version_rollout_mode: str | None,
    sync_after_preferred_change: bool | None,
) -> AdminModulesRolloutSettings:
    if preferred_version_rollout_mode is not None:
        preferred_version_rollout_mode = str(preferred_version_rollout_mode or "").strip().lower() or None
    if preferred_version_rollout_mode is not None and preferred_version_rollout_mode not in _MODULE_ROLLOUT_MODE_LABELS:
        raise ValueError("INVALID_ROLLOUT_MODE")

    async with get_session() as session:
        rollout_repo = ModuleRolloutRepo(session)
        settings = await rollout_repo.set_settings(
            preferred_version_rollout_mode=preferred_version_rollout_mode,
            sync_after_preferred_change=sync_after_preferred_change,
        )
        await session.commit()

    rollout_mode = str(settings.get("preferred_version_rollout_mode") or "manual").strip().lower() or "manual"
    return AdminModulesRolloutSettings(
        preferred_version_rollout_mode=rollout_mode,
        preferred_version_rollout_mode_label=_module_rollout_mode_label(rollout_mode),
        sync_after_preferred_change=bool(settings.get("sync_after_preferred_change", True)),
    )


async def _set_admin_module_preferred_version(
    *,
    request: web.Request,
    auth_context: AuthContext,
    module_name: str,
    version: str | None,
) -> AdminModulePreferredVersionActionPayload:
    normalized_module_name = str(module_name or "").strip()
    normalized_version = str(version or "").strip() or None
    updated_by = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"

    async with get_session() as session:
        rollout_repo = ModuleRolloutRepo(session)
        modules_repo = ModulesRepo(session)
        if normalized_version is None:
            await rollout_repo.clear_assignment(normalized_module_name)
            await session.commit()
            return AdminModulePreferredVersionActionPayload(
                module_name=normalized_module_name,
                preferred_version=None,
                updated_at=None,
                updated_by=updated_by,
                message=f"Preferred-версия для {normalized_module_name} снята.",
                rollout_summary=None,
            )

        module = await modules_repo.get_module(normalized_module_name, normalized_version)
        if module is None:
            raise LookupError("MODULE_NOT_FOUND")
        preferred_blocker = _preferred_gate_for_module(module)
        if preferred_blocker:
            raise ValueError(preferred_blocker.get("error_code") or "MODULE_PREFERRED_GATE_FAILED")

        assignment = await rollout_repo.set_assignment(
            module_name=normalized_module_name,
            version=normalized_version,
            updated_by=updated_by,
        )
        rollout_settings = await _get_module_rollout_settings(session)
        rollout_summary = await _apply_module_preferred_rollout(
            session=session,
            state=request.app.get("state"),
            module_name=normalized_module_name,
            version=normalized_version,
            updated_by=updated_by,
            settings=rollout_settings,
        )
        await session.commit()

    rollout_summary = await _finalize_module_preferred_rollout(
        state=request.app.get("state"),
        updated_by=updated_by,
        rollout_summary=rollout_summary,
    )
    typed_rollout_summary = _map_admin_module_preferred_rollout_summary(rollout_summary)
    message = f"Preferred-версия для {normalized_module_name} обновлена на {normalized_version}."
    if typed_rollout_summary and typed_rollout_summary.desired_updates > 0:
        message += f" Desired state обновлён для {typed_rollout_summary.desired_updates} устройств."
    return AdminModulePreferredVersionActionPayload(
        module_name=normalized_module_name,
        preferred_version=assignment["version"],
        updated_at=assignment.get("updated_at"),
        updated_by=assignment.get("updated_by"),
        message=message,
        rollout_summary=typed_rollout_summary,
    )


def _parse_observer_lookback_hours(value: str | None) -> int:
    try:
        parsed = int(str(value or "").strip() or "24")
    except (TypeError, ValueError):
        return 24
    return max(1, min(parsed, 24 * 7))


def _compact_query_value(value: str | None) -> str | None:
    compacted = str(value or "").strip()
    return compacted or None


def _normalize_observer_status_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"running", "failed", "succeeded", "timed_out"}:
        return normalized
    return "all"


def _normalize_observer_root_kind_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {
        "ticket",
        "tool_call",
        "requester_web",
        "agent_update",
        "module_install",
        "module_reconcile",
        "module_remove",
        "playbook_run",
        "web_auth",
        "observer_runtime",
        "consent",
    }
    if normalized in allowed:
        return normalized
    return "all"


def _parse_observer_trace_limit(value: str | None) -> int:
    try:
        parsed = int(str(value or "").strip() or "25")
    except (TypeError, ValueError):
        return 25
    return max(5, min(parsed, 100))


def _parse_optional_positive_int(value: str | None) -> int | None:
    compacted = _compact_query_value(value)
    if compacted is None:
        return None
    try:
        parsed = int(compacted)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _observer_kind_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Неизвестный поток"
    return _OBSERVER_ROOT_KIND_LABELS.get(normalized, normalized.replace("_", " "))


def _observer_status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Статус неизвестен"
    return _OBSERVER_STATUS_LABELS.get(normalized, normalized.replace("_", " "))


def _observer_severity_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "critical":
        return "Критично"
    if normalized == "warning":
        return "Предупреждение"
    if normalized == "error":
        return "Ошибка"
    return "Инфо"


def _observer_runtime_summary_from_app(request: web.Request) -> AdminObserverRuntimeSummary:
    runtime = request.app._state.get("observer_refresh_runtime")
    if runtime is None:
        return AdminObserverRuntimeSummary(
            enabled=False,
            running=False,
            health_status="down",
            health_status_label=_OBSERVER_RUNTIME_STATUS_LABELS["down"],
            pending_trace_count=None,
            last_projected_at=None,
            issues=[],
        )

    snapshot = runtime.status_snapshot()
    health = snapshot.get("health") if isinstance(snapshot.get("health"), dict) else {}
    stats = snapshot.get("stats") if isinstance(snapshot.get("stats"), dict) else {}
    health_status = str(health.get("status") or "unknown").strip().lower() or "unknown"
    return AdminObserverRuntimeSummary(
        enabled=bool(snapshot.get("enabled")),
        running=bool(snapshot.get("running")),
        health_status=health_status,
        health_status_label=_OBSERVER_RUNTIME_STATUS_LABELS.get(
            health_status,
            _OBSERVER_RUNTIME_STATUS_LABELS["unknown"],
        ),
        pending_trace_count=health.get("pending_trace_count"),
        last_projected_at=stats.get("last_projected_at"),
        issues=[str(item) for item in health.get("issues") or []],
    )


def _first_compact_value(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        compacted = value.strip() if isinstance(value, str) else str(value).strip()
        if compacted:
            return compacted
    return None


def _first_compact_from_list(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        compacted = _first_compact_value(item)
        if compacted:
            return compacted
    return None


def _observer_display_title(item: dict) -> str:
    ticket_code = _first_compact_value(item.get("ticket_code"))
    root_kind = _first_compact_value(item.get("root_kind"))
    if ticket_code and root_kind == "ticket":
        return f"Тикет {ticket_code}"
    if ticket_code:
        return f"Связано с тикетом {ticket_code}"
    operation_label = _first_compact_value(item.get("operation_label"))
    if operation_label:
        return operation_label
    tool_name = _first_compact_value(item.get("primary_tool_name"))
    if tool_name:
        return f"Инструмент {tool_name}"
    return _observer_kind_label(root_kind)


def _observer_display_subtitle(item: dict) -> str:
    parts = [
        _first_compact_value(item.get("ticket_title")),
        _first_compact_value(item.get("ticket_status_label")),
        _first_compact_value(item.get("device_label")),
        _first_compact_value(item.get("primary_tool_name")),
        _first_compact_value(item.get("latest_error_label")),
    ]
    compacted = []
    for part in parts:
        if part and part not in compacted:
            compacted.append(part)
    if compacted:
        return " · ".join(compacted)
    trace_id = _first_compact_value(item.get("trace_id"))
    return f"Trace {trace_id}" if trace_id else ""


_OBSERVER_LAUNCH_SOURCE_LABELS = {
    "manual": "Ручной запуск",
    "form_autorun": "Автозапуск формы",
    "diagnostic_policy": "Diagnostic policy",
    "playbook": "Playbook",
    "retry": "Retry",
    "system": "System",
}

_OBSERVER_LAUNCH_PATH_LABELS = {
    "manual": "ручной запуск инструмента",
    "form_autorun": "автозапуск формы",
    "diagnostic_policy": "diagnostic policy",
    "playbook": "playbook",
    "retry": "retry",
    "system": "system",
}

_OBSERVER_ERROR_DIAGNOSES = {
    "AGENT_NOT_CONNECTED": "Агент на устройстве не подключен. Команда не была отправлена.",
    "POLICY_DENIED": "Запуск запрещён политикой.",
}

_OBSERVER_STAGE_LABELS = {
    "queued": "Поставлена в очередь",
    "sent": "Отправлена агенту",
    "accepted": "Принята агентом",
    "running": "Выполняется",
    "succeeded": "Завершена успешно",
    "failed": "Завершена ошибкой",
    "timed_out": "Таймаут",
    "canceled": "Отменена",
    "denied": "Запрещена",
}


def _iter_tool_entries(value: object, *, depth: int = 0):
    if depth > 4:
        return
    if isinstance(value, dict):
        if _first_compact_value(value.get("tool"), value.get("tool_name"), value.get("name")):
            yield value
        for key in ("tools", "toolset", "available_tools", "items", "data", "payload"):
            if key in value:
                yield from _iter_tool_entries(value.get(key), depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_tool_entries(item, depth=depth + 1)


async def _observer_tool_catalog_entry(
    session,
    *,
    device: Device | None,
    tool_name: str | None,
) -> dict | None:
    if not device or not tool_name or not device.current_toolset_snapshot_id:
        return None
    snapshot = await session.get(DeviceToolsetSnapshot, device.current_toolset_snapshot_id)
    if snapshot is None:
        return None
    for raw_tool in _iter_tool_entries(snapshot.toolset_json):
        if not isinstance(raw_tool, dict):
            continue
        current_tool = _first_compact_value(raw_tool.get("tool"), raw_tool.get("tool_name"), raw_tool.get("name"))
        if current_tool != tool_name:
            continue
        try:
            return normalize_tool_catalog_entry(raw_tool, source="device_toolset")
        except Exception as exc:
            logger.debug(f"[observer_explain] tool catalog normalize failed: tool={tool_name}, error={exc}")
            return raw_tool
    return None


def _observer_preset_from_tool_entry(tool_entry: dict | None, preset_id: str | None) -> dict | None:
    if not tool_entry or not preset_id:
        return None
    for preset in tool_entry.get("presets") or []:
        if not isinstance(preset, dict):
            continue
        current_id = _first_compact_value(preset.get("preset_id"), preset.get("id"), preset.get("key"))
        if current_id == preset_id:
            return preset
    return None


def _observer_extract_params(start_payload: dict) -> dict:
    params = start_payload.get("params")
    if isinstance(params, dict):
        return params
    nested = start_payload.get("tool_params")
    if isinstance(nested, dict):
        return nested
    return {}


def _observer_launch_source(operation: Operation, start_payload: dict) -> str:
    trigger_type = _first_compact_value(
        start_payload.get("trigger_type"),
        start_payload.get("launch_source"),
        start_payload.get("source"),
    )
    normalized_trigger = str(trigger_type or "").strip().lower()
    if operation.retry_of_operation_id:
        return "retry"
    if operation.playbook_run_id or normalized_trigger in {"playbook", "playbook_run", "support_playbook"}:
        return "playbook"
    if normalized_trigger in {"diagnostic_policy", "policy", "auto_diagnostic"}:
        return "diagnostic_policy"
    if normalized_trigger in {"form_autorun", "request_form", "request_template", "form"} or start_payload.get("form_id"):
        return "form_autorun"
    if str(operation.actor_role or "").strip().lower() in {"admin", "support", "specialist"}:
        return "manual"
    return "system"


def _observer_error_diagnosis(operation: Operation, error_code: str | None) -> str | None:
    normalized = str(error_code or "").strip().upper()
    if normalized == "TIMEOUT":
        timeout = operation.timeout_override_sec or None
        if timeout:
            return f"Агент не ответил за {timeout} секунд."
        return "Агент не ответил вовремя."
    return _OBSERVER_ERROR_DIAGNOSES.get(normalized)


def _observer_agent_online(device: Device | None, operation: Operation, error_code: str | None) -> bool | None:
    if str(error_code or "").strip().upper() == "AGENT_NOT_CONNECTED":
        return False
    if device is None:
        return None
    last_seen = getattr(device, "last_handshake_at", None) or getattr(device, "last_seen_at", None)
    if not last_seen:
        return None
    now = datetime.now(timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now - last_seen).total_seconds() <= 180


def _observer_next_actions(*, error_code: str | None, device: Device | None) -> list[str]:
    normalized = str(error_code or "").strip().upper()
    if normalized == "AGENT_NOT_CONNECTED":
        actions = ["Проверить подключение агента"]
        last_handshake = _iso(getattr(device, "last_handshake_at", None)) if device else None
        if last_handshake:
            actions.append(f"Последний handshake: {last_handshake}")
        actions.append("Открыть устройство в inventory")
        return actions
    if normalized == "TIMEOUT":
        return ["Проверить нагрузку агента и повторить запуск", "Открыть trace agent actions"]
    if normalized == "POLICY_DENIED":
        return ["Проверить политику запуска инструмента", "Проверить роль и доступ пользователя"]
    return ["Открыть технические детали trace", "Проверить operation.tool_call и terminal span"]


def _observer_operation_id_from_detail(trace_payload: dict, raw_detail: dict) -> str | None:
    operation_id = _first_compact_value(trace_payload.get("operation_id"))
    if operation_id:
        return operation_id
    for occurrence in raw_detail.get("error_occurrences") or []:
        if isinstance(occurrence, dict):
            operation_id = _first_compact_value(occurrence.get("operation_id"))
            if operation_id:
                return operation_id
    for span in raw_detail.get("spans") or []:
        if not isinstance(span, dict):
            continue
        attrs = span.get("attrs_json") if isinstance(span.get("attrs_json"), dict) else {}
        operation_id = _first_compact_value(span.get("source_ref") if span.get("source_type") == "operation" else None, attrs.get("operation_id"))
        if operation_id:
            return operation_id.split(":", 1)[0]
    return None


async def _build_admin_observer_trace_explanation(
    session,
    *,
    trace_payload: dict,
    raw_detail: dict,
) -> AdminObserverTraceExplanation | None:
    operation_id = _observer_operation_id_from_detail(trace_payload, raw_detail)
    operation = await session.get(Operation, operation_id) if operation_id else None
    if operation is None:
        return None

    ticket = await session.get(Ticket, operation.ticket_id) if operation.ticket_id else None
    device = await session.get(Device, operation.device_id) if operation.device_id else None
    event_rows = (
        (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.operation_id == operation.operation_id)
                .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            )
        )
        .scalars()
        .all()
    )
    start_event = next((row for row in event_rows if row.event_type == "tool_call_started"), None)
    start_payload = start_event.payload if start_event is not None and isinstance(start_event.payload, dict) else {}
    params = _observer_extract_params(start_payload)

    tool_name = _first_compact_value(
        start_payload.get("tool_name"),
        start_payload.get("tool"),
        operation.tool_name,
        trace_payload.get("primary_tool_name"),
    )
    module_name = _first_compact_value(trace_payload.get("primary_module_name"), tool_name.split(".", 1)[0] if tool_name and "." in tool_name else None)
    tool_entry = await _observer_tool_catalog_entry(session, device=device, tool_name=tool_name)
    preset_id = _first_compact_value(start_payload.get("preset_id"), params.get("preset_id"), params.get("preset"))
    preset = _observer_preset_from_tool_entry(tool_entry, preset_id)

    launch_source = _observer_launch_source(operation, start_payload)
    actor_role = _first_compact_value(start_payload.get("actor_role"), operation.actor_role)
    actor_id = _first_compact_value(start_payload.get("actor_id"), start_payload.get("triggered_by"))
    actor_display_name = _first_compact_value(start_payload.get("actor_display_name"), start_payload.get("display_name"), actor_id, actor_role)
    actor_label = f"Запустил: {actor_display_name}" if actor_display_name else None

    error_code = _first_compact_value(operation.error_code)
    error_diagnosis = _observer_error_diagnosis(operation, error_code)
    failure_stage = _first_compact_value(operation.status)
    agent_online = _observer_agent_online(device, operation, error_code)
    agent_status_label = "агент online" if agent_online is True else "агент offline" if agent_online is False else None
    tool_label = _first_compact_value(
        tool_entry.get("label") if isinstance(tool_entry, dict) else None,
        tool_entry.get("title") if isinstance(tool_entry, dict) else None,
        tool_name,
    )
    preset_label = _first_compact_value(
        preset.get("label") if isinstance(preset, dict) else None,
        preset.get("name") if isinstance(preset, dict) else None,
        preset_id,
    )
    preset_description = _first_compact_value(preset.get("description") if isinstance(preset, dict) else None)
    ticket_label = f"Тикет {ticket.ticket_code}" if ticket is not None and ticket.ticket_code else None
    launch_path = [
        item
        for item in [
            ticket_label,
            _OBSERVER_LAUNCH_PATH_LABELS.get(launch_source, launch_source),
            tool_label,
            agent_status_label,
            failure_stage,
        ]
        if item
    ]
    human_timeline = [
        item
        for item in [
            f"{_iso(operation.queued_at)} {actor_display_name} запустил диагностику" if operation.queued_at and actor_display_name else None,
            f"{_iso(operation.queued_at)} сервер поставил операцию в очередь" if operation.queued_at else None,
            f"{_iso(operation.finished_at)} {error_diagnosis}" if operation.finished_at and error_diagnosis else None,
        ]
        if item
    ]
    return AdminObserverTraceExplanation(
        launch_source=launch_source,
        launch_source_label=_OBSERVER_LAUNCH_SOURCE_LABELS.get(launch_source, launch_source),
        actor_role=actor_role,
        actor_id=actor_id,
        actor_display_name=actor_display_name,
        actor_label=actor_label,
        tool_name=tool_name,
        tool_label=tool_label,
        tool_description=_first_compact_value(tool_entry.get("description") if isinstance(tool_entry, dict) else None),
        module_name=module_name,
        module_label=module_name,
        preset_id=preset_id,
        preset_label=preset_label,
        preset_description=preset_description,
        error_code=error_code,
        error_diagnosis=error_diagnosis,
        error_details=_first_compact_value(operation.error_message),
        failure_stage=failure_stage,
        failure_stage_label=_observer_status_label(failure_stage),
        agent_online=agent_online,
        agent_status_label=agent_status_label,
        agent_last_seen_at=_iso(getattr(device, "last_seen_at", None)) if device else None,
        agent_last_handshake_at=_iso(getattr(device, "last_handshake_at", None)) if device else None,
        launch_path=launch_path,
        next_actions=_observer_next_actions(error_code=error_code, device=device),
        human_timeline=human_timeline,
        debug_refs={
            "trace_id": trace_payload.get("trace_id"),
            "operation_id": operation.operation_id,
            "ticket_id": operation.ticket_id,
            "device_id": operation.device_id,
            "tool_call_started_event_id": getattr(start_event, "id", None),
        },
    )


async def _enrich_admin_observer_trace_items(session, items: list[dict]) -> list[dict]:
    if not items:
        return []

    enriched = [dict(item) for item in items if isinstance(item, dict)]
    ticket_ids: set[str] = set()
    device_ids: set[str] = set()
    operation_ids: set[str] = set()
    queue_ids: set[int] = set()

    for item in enriched:
        attrs = item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {}
        ticket_id = _first_compact_value(item.get("ticket_id"), attrs.get("ticket_id"))
        device_id = _first_compact_value(item.get("device_id"), attrs.get("device_id"))
        operation_id = _first_compact_value(item.get("operation_id"), attrs.get("operation_id"))
        if ticket_id:
            ticket_ids.add(ticket_id)
        if device_id:
            device_ids.add(device_id)
        if operation_id:
            operation_ids.add(operation_id)

    tickets: dict[str, Ticket] = {}
    if ticket_ids:
        rows = (await session.execute(select(Ticket).where(Ticket.ticket_id.in_(ticket_ids)))).scalars().all()
        tickets = {row.ticket_id: row for row in rows}
        queue_ids = {int(row.queue_id) for row in rows if row.queue_id is not None}
        device_ids.update(row.device_id for row in rows if row.device_id)

    devices: dict[str, Device] = {}
    if device_ids:
        rows = (await session.execute(select(Device).where(Device.device_id.in_(device_ids)))).scalars().all()
        devices = {row.device_id: row for row in rows}

    operations: dict[str, Operation] = {}
    if operation_ids:
        rows = (await session.execute(select(Operation).where(Operation.operation_id.in_(operation_ids)))).scalars().all()
        operations = {row.operation_id: row for row in rows}

    queues: dict[int, TicketQueue] = {}
    if queue_ids:
        rows = (await session.execute(select(TicketQueue).where(TicketQueue.id.in_(queue_ids)))).scalars().all()
        queues = {int(row.id): row for row in rows}

    for item in enriched:
        attrs = item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {}
        ticket_id = _first_compact_value(item.get("ticket_id"), attrs.get("ticket_id"))
        operation_id = _first_compact_value(item.get("operation_id"), attrs.get("operation_id"))
        ticket = tickets.get(ticket_id or "")
        operation = operations.get(operation_id or "")
        device_id = _first_compact_value(item.get("device_id"), attrs.get("device_id"), getattr(ticket, "device_id", None))
        device = devices.get(device_id or "")
        queue = queues.get(int(ticket.queue_id)) if ticket is not None and ticket.queue_id is not None else None

        tool_name = _first_compact_value(
            _first_compact_from_list(attrs.get("tool_names")),
            attrs.get("tool_name"),
            getattr(operation, "tool_name", None),
        )
        module_name = _first_compact_value(
            _first_compact_from_list(attrs.get("module_names")),
            attrs.get("module_name"),
        )
        operation_kind = _first_compact_value(getattr(operation, "kind", None), item.get("root_kind"))
        operation_label = _first_compact_value(
            attrs.get("operation_label"),
            f"{operation_kind}: {tool_name}" if operation_kind and tool_name else None,
            tool_name,
            operation_kind,
        )
        latest_error = _first_compact_value(
            attrs.get("latest_error_label"),
            attrs.get("error_signature"),
            _first_compact_from_list(attrs.get("error_signatures")),
        )

        item["ticket_id"] = ticket_id
        item["ticket_code"] = _first_compact_value(getattr(ticket, "ticket_code", None), attrs.get("ticket_code"))
        item["ticket_title"] = _first_compact_value(getattr(ticket, "title", None), attrs.get("ticket_title"))
        item["ticket_status"] = _first_compact_value(getattr(ticket, "status", None), attrs.get("ticket_status"))
        item["ticket_status_label"] = _observer_status_label(item.get("ticket_status"))
        item["ticket_priority"] = _first_compact_value(getattr(ticket, "priority", None), attrs.get("ticket_priority"))
        item["queue_name"] = _first_compact_value(getattr(queue, "name", None), attrs.get("queue_name"))
        item["requester_display_name"] = _first_compact_value(
            getattr(ticket, "requester_id", None),
            attrs.get("requester_display_name"),
        )
        item["device_id"] = device_id
        item["device_hostname"] = _first_compact_value(getattr(device, "hostname", None), attrs.get("device_hostname"))
        item["device_label"] = _first_compact_value(item.get("device_hostname"), device_id)
        item["operation_label"] = operation_label
        item["latest_error_label"] = latest_error
        item["latest_error_stage"] = _first_compact_value(attrs.get("failure_stage"), attrs.get("component"))
        item["primary_tool_name"] = tool_name
        item["primary_module_name"] = module_name
        item["display_title"] = _first_compact_value(item.get("display_title"), _observer_display_title(item))
        item["display_subtitle"] = _first_compact_value(item.get("display_subtitle"), _observer_display_subtitle(item))

    return enriched


def _empty_admin_observer_quick_payload(
    *,
    lookback_hours: int,
    request: web.Request,
) -> AdminObserverQuickPayload:
    return AdminObserverQuickPayload(
        summary=AdminObserverQuickSummary(
            lookback_hours=lookback_hours,
            recent_trace_count=0,
            hot_trace_count=0,
            signature_count=0,
            degradation_group_count=0,
            dangerous_flow_count=0,
        ),
        runtime=_observer_runtime_summary_from_app(request),
        hot_traces=[],
        top_signatures=[],
        top_degradations=[],
        dangerous_flows=[],
        links=AdminObserverQuickLinks(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


def _map_admin_observer_quick_trace(item: dict) -> AdminObserverQuickTrace:
    return AdminObserverQuickTrace(
        trace_id=str(item.get("trace_id") or ""),
        root_kind=item.get("root_kind"),
        root_kind_label=_observer_kind_label(item.get("root_kind")),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        ticket_id=item.get("ticket_id"),
        ticket_code=item.get("ticket_code"),
        ticket_title=item.get("ticket_title"),
        ticket_status=item.get("ticket_status"),
        ticket_status_label=item.get("ticket_status_label"),
        ticket_priority=item.get("ticket_priority"),
        queue_name=item.get("queue_name"),
        requester_display_name=item.get("requester_display_name"),
        device_id=item.get("device_id"),
        device_hostname=item.get("device_hostname"),
        device_label=item.get("device_label"),
        operation_label=item.get("operation_label"),
        latest_error_label=item.get("latest_error_label"),
        latest_error_stage=item.get("latest_error_stage"),
        primary_tool_name=item.get("primary_tool_name"),
        primary_module_name=item.get("primary_module_name"),
        display_title=item.get("display_title"),
        display_subtitle=item.get("display_subtitle"),
        duration_ms=item.get("duration_ms"),
        error_count=int(item.get("error_count") or 0),
        span_count=int(item.get("span_count") or 0),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
    )


def _map_admin_observer_trace_item(item: dict) -> AdminObserverTraceItem:
    return AdminObserverTraceItem(
        trace_id=str(item.get("trace_id") or ""),
        root_span_id=item.get("root_span_id"),
        root_kind=item.get("root_kind"),
        root_kind_label=_observer_kind_label(item.get("root_kind")),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        ticket_id=item.get("ticket_id"),
        ticket_code=item.get("ticket_code"),
        ticket_title=item.get("ticket_title"),
        ticket_status=item.get("ticket_status"),
        ticket_status_label=item.get("ticket_status_label"),
        ticket_priority=item.get("ticket_priority"),
        queue_name=item.get("queue_name"),
        requester_display_name=item.get("requester_display_name"),
        device_id=item.get("device_id"),
        device_hostname=item.get("device_hostname"),
        device_label=item.get("device_label"),
        operation_id=item.get("operation_id"),
        operation_label=item.get("operation_label"),
        latest_error_label=item.get("latest_error_label"),
        latest_error_stage=item.get("latest_error_stage"),
        primary_tool_name=item.get("primary_tool_name"),
        primary_module_name=item.get("primary_module_name"),
        display_title=item.get("display_title"),
        display_subtitle=item.get("display_subtitle"),
        job_id=item.get("job_id"),
        duration_ms=item.get("duration_ms"),
        error_count=int(item.get("error_count") or 0),
        span_count=int(item.get("span_count") or 0),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
    )


def _map_admin_observer_trace_span(item: dict) -> AdminObserverTraceSpanItem:
    attrs = item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {}
    stage = _first_compact_value(attrs.get("stage"), item.get("event_type"))
    return AdminObserverTraceSpanItem(
        span_id=str(item.get("span_id") or ""),
        trace_id=str(item.get("trace_id") or ""),
        parent_span_id=item.get("parent_span_id"),
        source_type=item.get("source_type"),
        source_ref=item.get("source_ref"),
        name=str(item.get("name") or ""),
        kind=item.get("kind"),
        component=item.get("component"),
        event_type=item.get("event_type"),
        module_name=item.get("module_name"),
        tool_name=item.get("tool_name"),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        stage_label=_OBSERVER_STAGE_LABELS.get(stage or "") if stage else None,
        stage_state=_first_compact_value(attrs.get("stage_state")),
        stage_note=_first_compact_value(attrs.get("stage_note")),
        is_failure_stage=bool(attrs.get("is_failure_stage")),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
        duration_ms=item.get("duration_ms"),
        attrs_json=attrs,
    )


def _map_admin_observer_trace_span_link(item: dict) -> AdminObserverTraceSpanLinkItem:
    return AdminObserverTraceSpanLinkItem(
        id=int(item.get("id") or 0),
        span_id=str(item.get("span_id") or ""),
        linked_trace_id=item.get("linked_trace_id"),
        linked_span_id=item.get("linked_span_id"),
        reason=item.get("reason"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
        created_at=item.get("created_at"),
    )


def _map_admin_observer_error_occurrence(item: dict) -> AdminObserverTraceErrorOccurrenceItem:
    return AdminObserverTraceErrorOccurrenceItem(
        occurrence_id=str(item.get("occurrence_id") or ""),
        trace_id=str(item.get("trace_id") or ""),
        span_id=item.get("span_id"),
        error_signature=str(item.get("error_signature") or ""),
        device_id=item.get("device_id"),
        ticket_id=item.get("ticket_id"),
        operation_id=item.get("operation_id"),
        component=item.get("component"),
        module_name=item.get("module_name"),
        tool_name=item.get("tool_name"),
        error_kind=item.get("error_kind"),
        exception_type=item.get("exception_type"),
        failure_stage=item.get("failure_stage"),
        severity=item.get("severity"),
        severity_label=_observer_severity_label(item.get("severity")),
        message_norm=item.get("message_norm"),
        stack_hash=item.get("stack_hash"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
        created_at=item.get("created_at"),
    )


def _map_admin_observer_signature(item: dict) -> AdminObserverSignatureItem:
    return AdminObserverSignatureItem(
        error_signature=str(item.get("error_signature") or ""),
        title=str(item.get("title") or "Без названия"),
        tool_name=item.get("tool_name"),
        component=item.get("component"),
        occurrences_count=int(item.get("occurrences_count") or 0),
        affected_devices_count=int(item.get("affected_devices_count") or 0),
        last_seen_at=item.get("last_seen_at"),
    )


def _map_admin_observer_degradation(item: dict) -> AdminObserverDegradationItem:
    return AdminObserverDegradationItem(
        operation_kind=item.get("operation_kind"),
        operation_kind_label=_observer_kind_label(item.get("operation_kind")),
        tool_name=item.get("tool_name"),
        operations_count=int(item.get("operations_count") or 0),
        timeout_count=int(item.get("timeout_count") or 0),
        retried_operations_count=int(item.get("retried_operations_count") or 0),
        slow_operations_count=int(item.get("slow_operations_count") or 0),
        max_duration_ms=int(item.get("max_duration_ms") or 0),
        latest_operation_at=item.get("latest_operation_at"),
    )


def _map_admin_observer_dangerous_flow(item: dict) -> AdminObserverDangerousFlowItem:
    root_kind = str(item.get("root_kind") or "").strip().lower() or "unknown"
    return AdminObserverDangerousFlowItem(
        root_kind=root_kind,
        root_kind_label=_observer_kind_label(root_kind),
        operations_count=int(item.get("operations_count") or 0),
        error_count=int(item.get("error_count") or 0),
        timeout_count=int(item.get("timeout_count") or 0),
        retried_count=int(item.get("retried_count") or 0),
        active_count=int(item.get("active_count") or 0),
        latest_operation_at=item.get("latest_operation_at"),
    )


def _resolve_target(device) -> str | None:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    raw = str(metadata.get("os_type") or getattr(device, "os", "") or "").strip().lower()
    if not raw:
        return None
    return _OS_TYPE_TO_TARGET.get(raw) or _OS_TYPE_TO_TARGET.get(raw.replace("_", " "))


def _matches_status_filter(*, online: bool, status_filter: str) -> bool:
    if status_filter == "online":
        return online
    if status_filter == "offline":
        return not online
    return True


def _matches_query(item: AdminDeviceItem, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [
            item.device_id,
            item.hostname or "",
            item.os or "",
            item.agent_version or "",
            item.target or "",
            item.connection_status_label,
            item.identity_summary.machine_id_source or "",
            item.identity_summary.source_label,
            item.duplicate_warning.title if item.duplicate_warning else "",
        ]
    ).lower()
    return query.lower() in haystack


def _identity_source_label(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if not normalized:
        return "Источник не указан"
    return _IDENTITY_SOURCE_LABELS.get(normalized, normalized.replace("_", " "))


def _device_identity_summary(device) -> AdminDeviceIdentitySummary:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    source = str(metadata.get("machine_id_source") or "").strip() or None
    return AdminDeviceIdentitySummary(
        machine_id=str(getattr(device, "device_id", "") or ""),
        install_id=str(metadata.get("install_id") or "").strip() or None,
        machine_id_source=source,
        identity_scheme=str(metadata.get("identity_scheme") or "").strip() or None,
        source_label=_identity_source_label(source),
        is_stable=str(source or "").strip().lower() in _STABLE_IDENTITY_SOURCES,
    )


def _device_hostname(device) -> str | None:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    hostname = getattr(device, "hostname", None) or metadata.get("hostname")
    return str(hostname).strip() if hostname else None


def _build_duplicate_index(devices: list) -> dict[str, dict[str, int]]:
    index: dict[str, dict[str, int]] = {}
    for device in devices:
        hostname = _device_hostname(device)
        if not hostname:
            continue
        metadata = getattr(device, "device_metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
        source = str(metadata.get("machine_id_source") or "").strip().lower()
        row = index.setdefault(hostname.lower(), {"total": 0, "env_uuid": 0, "stable": 0, "cleanup": 0})
        row["total"] += 1
        if source == "env_uuid":
            row["env_uuid"] += 1
        if source in _STABLE_IDENTITY_SOURCES:
            row["stable"] += 1
    return index


def _build_duplicate_warning(device, *, duplicate_index: dict[str, dict[str, int]], online: bool) -> AdminDeviceDuplicateWarning | None:
    hostname = _device_hostname(device)
    if not hostname:
        return None
    group = duplicate_index.get(hostname.lower())
    if not group or group.get("total", 0) <= 1:
        return None
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    source = str(metadata.get("machine_id_source") or "").strip().lower()
    if source == "env_uuid":
        return AdminDeviceDuplicateWarning(
            kind="env_uuid_duplicate",
            severity="warning",
            title="Тестовый дубль hostname",
            description=(
                f"Hostname {hostname} встречается {group['total']} раз. Эта запись создана через env_uuid; "
                "её можно безопасно архивировать, если агент оффлайн."
            ),
            duplicate_count=group["total"],
            cleanup_available=False,
        )
    if group.get("env_uuid", 0) > 0:
        return AdminDeviceDuplicateWarning(
            kind="hostname_has_env_uuid_duplicates",
            severity="info",
            title="Есть старые тестовые дубли",
            description=(
                f"Для hostname {hostname} найдено env_uuid-дублей: {group['env_uuid']}. "
                "Текущую стабильную запись оставляем, старые оффлайн-записи можно архивировать."
            ),
            duplicate_count=group["total"],
            cleanup_available=False,
        )
    return None


def _build_device_item(device, *, online: bool, duplicate_index: dict[str, dict[str, int]] | None = None) -> AdminDeviceItem:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    hostname = _device_hostname(device)
    os_name = getattr(device, "os", None) or metadata.get("os_type")
    agent_version = getattr(device, "agent_version", None) or metadata.get("agent_version") or metadata.get("version")
    last_seen_at = getattr(device, "last_seen_at", None)
    deleted_at = getattr(device, "deleted_at", None)
    is_deleted = deleted_at is not None
    duplicate_index = duplicate_index or {}
    return AdminDeviceItem(
        device_id=str(getattr(device, "device_id", "") or ""),
        hostname=str(hostname) if hostname else None,
        os=str(os_name) if os_name else None,
        agent_version=str(agent_version) if agent_version else None,
        target=_resolve_target(device),
        online=False if is_deleted else online,
        last_seen_at=last_seen_at.isoformat() if last_seen_at else None,
        is_deleted=is_deleted,
        deleted_at=deleted_at.isoformat() if deleted_at else None,
        deleted_by=getattr(device, "deleted_by", None),
        delete_reason=getattr(device, "delete_reason", None),
        connection_status_label="Архив" if is_deleted else ("Онлайн" if online else "Оффлайн"),
        identity_summary=_device_identity_summary(device),
        duplicate_warning=None
        if is_deleted
        else _build_duplicate_warning(device, duplicate_index=duplicate_index, online=online),
    )


async def _build_admin_observer_quick_payload(
    *,
    request: web.Request,
    lookback_hours: int,
    device_id: str | None,
) -> AdminObserverQuickPayload:
    runtime = _observer_runtime_summary_from_app(request)

    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_payload = await service.get_quick_diagnosis(
                TraceOverlayFilters(lookback_hours=lookback_hours, device_id=device_id),
                hot_limit=5,
                signature_limit=4,
                degradation_limit=4,
                flow_limit=4,
            )
            raw_payload["hot_traces"] = await _enrich_admin_observer_trace_items(
                session,
                [item for item in raw_payload.get("hot_traces") or [] if isinstance(item, dict)],
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "[web_admin_observer_quick] returning empty payload for "
            f"lookback_hours={lookback_hours}, device_id={device_id}: {exc}"
        )
        return _empty_admin_observer_quick_payload(lookback_hours=lookback_hours, request=request)

    summary = raw_payload.get("summary") if isinstance(raw_payload.get("summary"), dict) else {}
    return AdminObserverQuickPayload(
        summary=AdminObserverQuickSummary(
            lookback_hours=lookback_hours,
            recent_trace_count=int(summary.get("recent_trace_count") or 0),
            hot_trace_count=int(summary.get("hot_trace_count") or 0),
            signature_count=int(summary.get("signature_count") or 0),
            degradation_group_count=int(summary.get("degradation_group_count") or 0),
            dangerous_flow_count=int(summary.get("dangerous_flow_count") or 0),
        ),
        runtime=runtime,
        hot_traces=[
            _map_admin_observer_quick_trace(item)
            for item in raw_payload.get("hot_traces") or []
            if isinstance(item, dict)
        ],
        top_signatures=[
            _map_admin_observer_signature(item)
            for item in raw_payload.get("top_signatures") or []
            if isinstance(item, dict)
        ],
        top_degradations=[
            _map_admin_observer_degradation(item)
            for item in raw_payload.get("top_degradations") or []
            if isinstance(item, dict)
        ],
        dangerous_flows=[
            _map_admin_observer_dangerous_flow(item)
            for item in raw_payload.get("dangerous_flows") or []
            if isinstance(item, dict)
        ],
        links=AdminObserverQuickLinks(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


def _build_observer_trace_filters(
    *,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    query: str | None = None,
    trace_id: str | None = None,
    ticket_id: str | None = None,
    operation_id: str | None = None,
    tool_name: str | None = None,
    module_name: str | None = None,
    error_signature: str | None = None,
    min_duration_ms: int | None = None,
    playbook_run_id: int | None = None,
    step_run_id: int | None = None,
    route: str | None = None,
    source: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    event_type: str | None = None,
) -> TraceOverlayFilters:
    return TraceOverlayFilters(
        query=query,
        trace_id=trace_id,
        ticket_id=ticket_id,
        operation_id=operation_id,
        device_id=device_id,
        tool_name=tool_name,
        module_name=module_name,
        error_signature=error_signature,
        lookback_hours=lookback_hours,
        status=None if status_filter == "all" else status_filter,
        root_kind=None if root_kind_filter == "all" else root_kind_filter,
        min_duration_ms=min_duration_ms,
        playbook_run_id=playbook_run_id,
        step_run_id=step_run_id,
        route=route,
        source=source,
        person_id=person_id,
        error_code=error_code,
        event_type=event_type,
    )


def _empty_admin_observer_traces_payload(
    *,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    limit: int,
    query: str | None = None,
    trace_id: str | None = None,
    ticket_id: str | None = None,
    operation_id: str | None = None,
    tool_name: str | None = None,
    module_name: str | None = None,
    error_signature: str | None = None,
    min_duration_ms: int | None = None,
    playbook_run_id: int | None = None,
    step_run_id: int | None = None,
    route: str | None = None,
    source: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    event_type: str | None = None,
) -> AdminObserverTracesPayload:
    return AdminObserverTracesPayload(
        query=AdminObserverTracesQuery(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
            query=query,
            trace_id=trace_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            tool_name=tool_name,
            module_name=module_name,
            error_signature=error_signature,
            min_duration_ms=min_duration_ms,
            playbook_run_id=playbook_run_id,
            step_run_id=step_run_id,
            route=route,
            source=source,
            person_id=person_id,
            error_code=error_code,
            event_type=event_type,
        ),
        summary=AdminObserverTracesSummary(
            visible_count=0,
            active_count=0,
            error_count=0,
            selected_trace_id=None,
        ),
        filters=AdminObserverTracesFilters(
            status_options=_OBSERVER_TRACE_STATUS_OPTIONS,
            root_kind_options=_OBSERVER_TRACE_ROOT_KIND_OPTIONS,
        ),
        traces=[],
        links=AdminObserverTracesLinks(
            detail_endpoint_template=_OBSERVER_TRACE_DETAIL_TEMPLATE,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


async def _build_admin_observer_traces_payload(
    *,
    request: web.Request,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    limit: int,
    query: str | None = None,
    trace_id: str | None = None,
    ticket_id: str | None = None,
    operation_id: str | None = None,
    tool_name: str | None = None,
    module_name: str | None = None,
    error_signature: str | None = None,
    min_duration_ms: int | None = None,
    playbook_run_id: int | None = None,
    step_run_id: int | None = None,
    route: str | None = None,
    source: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    event_type: str | None = None,
) -> AdminObserverTracesPayload:
    filters = _build_observer_trace_filters(
        device_id=device_id,
        lookback_hours=lookback_hours,
        status_filter=status_filter,
        root_kind_filter=root_kind_filter,
        query=query,
        trace_id=trace_id,
        ticket_id=ticket_id,
        operation_id=operation_id,
        tool_name=tool_name,
        module_name=module_name,
        error_signature=error_signature,
        min_duration_ms=min_duration_ms,
        playbook_run_id=playbook_run_id,
        step_run_id=step_run_id,
        route=route,
        source=source,
        person_id=person_id,
        error_code=error_code,
        event_type=event_type,
    )
    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_traces = await service.search_traces(filters, limit=limit)
            raw_traces = await _enrich_admin_observer_trace_items(
                session,
                [item for item in raw_traces if isinstance(item, dict)],
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "[web_admin_observer_traces] returning empty payload for "
            f"device_id={device_id}, lookback_hours={lookback_hours}, "
            f"status_filter={status_filter}, root_kind_filter={root_kind_filter}: {exc}"
        )
        return _empty_admin_observer_traces_payload(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
            query=query,
            trace_id=trace_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            tool_name=tool_name,
            module_name=module_name,
            error_signature=error_signature,
            min_duration_ms=min_duration_ms,
            playbook_run_id=playbook_run_id,
            step_run_id=step_run_id,
            route=route,
            source=source,
            person_id=person_id,
            error_code=error_code,
            event_type=event_type,
        )

    traces = [
        _map_admin_observer_trace_item(item)
        for item in raw_traces
        if isinstance(item, dict) and item.get("trace_id")
    ]
    active_count = sum(1 for item in traces if str(item.status or "").strip().lower() in _OBSERVER_ACTIVE_STATUSES)
    error_count = sum(
        1
        for item in traces
        if item.error_count > 0 or str(item.status or "").strip().lower() in _OBSERVER_ERROR_STATUSES
    )
    return AdminObserverTracesPayload(
        query=AdminObserverTracesQuery(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
            query=query,
            trace_id=trace_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            tool_name=tool_name,
            module_name=module_name,
            error_signature=error_signature,
            min_duration_ms=min_duration_ms,
            playbook_run_id=playbook_run_id,
            step_run_id=step_run_id,
            route=route,
            source=source,
            person_id=person_id,
            error_code=error_code,
            event_type=event_type,
        ),
        summary=AdminObserverTracesSummary(
            visible_count=len(traces),
            active_count=active_count,
            error_count=error_count,
            selected_trace_id=traces[0].trace_id if traces else None,
        ),
        filters=AdminObserverTracesFilters(
            status_options=_OBSERVER_TRACE_STATUS_OPTIONS,
            root_kind_options=_OBSERVER_TRACE_ROOT_KIND_OPTIONS,
        ),
        traces=traces,
        links=AdminObserverTracesLinks(
            detail_endpoint_template=_OBSERVER_TRACE_DETAIL_TEMPLATE,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


async def _build_admin_observer_trace_detail_payload(
    *,
    request: web.Request,
    trace_id: str,
) -> AdminObserverTraceDetailPayload:
    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_detail = await service.get_trace_detail(trace_id)
            if raw_detail is None:
                await session.rollback()
                raise LookupError("TRACE_NOT_FOUND")
            trace_payload = raw_detail.get("trace") if isinstance(raw_detail.get("trace"), dict) else {}
            enriched_traces = await _enrich_admin_observer_trace_items(session, [trace_payload])
            raw_detail["trace"] = enriched_traces[0] if enriched_traces else trace_payload
            raw_detail["explanation"] = await _build_admin_observer_trace_explanation(
                session,
                trace_payload=raw_detail["trace"],
                raw_detail=raw_detail,
            )
            await session.commit()
    except LookupError:
        raise
    except Exception as exc:
        logger.error(f"[web_admin_observer_trace_detail] Failed to load trace_id={trace_id}: {exc}")
        logger.exception(exc)
        raise

    trace_payload = raw_detail.get("trace") if isinstance(raw_detail.get("trace"), dict) else {}
    spans = [
        _map_admin_observer_trace_span(item)
        for item in raw_detail.get("spans") or []
        if isinstance(item, dict) and item.get("span_id")
    ]
    span_links = [
        _map_admin_observer_trace_span_link(item)
        for item in raw_detail.get("span_links") or []
        if isinstance(item, dict) and item.get("id") is not None
    ]
    error_occurrences = [
        _map_admin_observer_error_occurrence(item)
        for item in raw_detail.get("error_occurrences") or []
        if isinstance(item, dict) and item.get("occurrence_id")
    ]
    linked_trace_count = len({item.linked_trace_id for item in span_links if item.linked_trace_id})
    return AdminObserverTraceDetailPayload(
        trace=_map_admin_observer_trace_item(trace_payload),
        summary=AdminObserverTraceDetailSummary(
            span_count=len(spans),
            error_count=len(error_occurrences),
            linked_trace_count=linked_trace_count,
        ),
        explanation=raw_detail.get("explanation") if isinstance(raw_detail.get("explanation"), AdminObserverTraceExplanation) else None,
        spans=spans,
        span_links=span_links,
        error_occurrences=error_occurrences,
    )


def _build_missing_admin_observer_trace_detail_payload(trace_id: str) -> AdminObserverTraceDetailPayload:
    return AdminObserverTraceDetailPayload(
        trace=AdminObserverTraceItem(
            trace_id=trace_id,
            root_span_id=None,
            root_kind=None,
            root_kind_label="Нет данных",
            status="missing",
            status_label="Не найдена",
            attrs_json={
                "detail_status": "missing",
                "reason": "trace detail is not available for this projected trace",
            },
        ),
        summary=AdminObserverTraceDetailSummary(
            span_count=0,
            error_count=0,
            linked_trace_count=0,
        ),
        explanation=None,
        spans=[],
        span_links=[],
        error_occurrences=[],
    )


async def _build_admin_modules_payload(*, query: str) -> AdminModulesPayload:
    normalized_query = str(query or "").strip()
    query_lower = normalized_query.lower()

    async with get_session() as session:
        modules = await ModulesRepo(session).list_modules(limit=300)
        preferred_assignments = await _get_module_preferred_assignments(session)
        rollout_settings = await _get_module_rollout_settings(session)

    grouped: dict[str, list[object]] = {}
    for module in modules:
        grouped.setdefault(str(getattr(module, "module_name", "") or ""), []).append(module)

    families: list[AdminModuleFamilyItem] = []
    missing_files_count = 0
    invalid_count = 0
    preferred_count = 0
    for module_name in sorted(name for name in grouped if name):
        versions = sorted(
            grouped[module_name],
            key=lambda item: (
                version_key(str(getattr(item, "version", "") or "")).key,
                getattr(item, "created_at", None).isoformat() if getattr(item, "created_at", None) else "",
            ),
            reverse=True,
        )
        preferred_version = preferred_assignments.get(module_name, {}).get("version")
        version_items = [
            _map_admin_module_version_item(module, preferred_version=preferred_version)
            for module in versions
        ]
        primary_module = _pick_primary_module_record(versions, preferred_version)
        if primary_module is None:
            continue
        primary_manifest = get_module_manifest(primary_module)
        primary_validation = get_module_validation(primary_module)
        primary_validation_status = (
            str(primary_validation.get("validation_status") or "unknown").strip().lower() or "unknown"
        )
        tool_ids = _module_tool_ids(primary_manifest)
        family = AdminModuleFamilyItem(
            module_name=module_name,
            preferred_version=preferred_version,
            preferred_assigned=bool(preferred_version and any(item.is_preferred for item in version_items)),
            latest_version=version_items[0].version if version_items else None,
            owner_scope=primary_manifest.get("owner_scope"),
            module_api_version=primary_manifest.get("module_api_version"),
            validation_status=primary_validation_status,
            validation_status_label=_module_validation_label(primary_validation_status),
            version_count=len(version_items),
            tools_count=max((item.tools_count for item in version_items), default=0),
            platforms=[str(item) for item in (primary_manifest.get("platforms") or ["any"])],
            tool_ids=tool_ids,
            warnings_count=max((item.warnings_count for item in version_items), default=0),
            has_missing_files=any(not item.file_exists for item in version_items),
            versions=version_items,
        )
        haystack = " ".join(
            [
                family.module_name,
                family.preferred_version or "",
                family.latest_version or "",
                family.owner_scope or "",
                family.module_api_version or "",
                *family.platforms,
                *family.tool_ids,
                *(item.version for item in version_items),
            ]
        ).lower()
        if query_lower and query_lower not in haystack:
            continue
        if family.preferred_assigned:
            preferred_count += 1
        if family.validation_status in {"failed", "warning"}:
            invalid_count += 1
        if family.has_missing_files:
            missing_files_count += 1
        families.append(family)

    rollout_mode = str(rollout_settings.get("preferred_version_rollout_mode") or "manual").strip().lower() or "manual"
    return AdminModulesPayload(
        query=normalized_query,
        summary=AdminModulesSummary(
            visible_count=len(families),
            preferred_count=preferred_count,
            invalid_count=invalid_count,
            missing_files_count=missing_files_count,
        ),
        rollout_settings=AdminModulesRolloutSettings(
            preferred_version_rollout_mode=rollout_mode,
            preferred_version_rollout_mode_label=_module_rollout_mode_label(rollout_mode),
            sync_after_preferred_change=bool(rollout_settings.get("sync_after_preferred_change", True)),
        ),
        modules=families,
    )


async def _build_admin_forms_payload() -> AdminFormsPayload:
    builtin = validate_form_pack_schema(build_default_ticket_form_pack())

    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        pack = await resolve_ticket_form_pack(repo, pack_key=DEFAULT_TICKET_FORM_PACK_KEY)
        current_version = str(pack.get("version") or "")
        pack_record = await repo.get_pack(DEFAULT_TICKET_FORM_PACK_KEY, current_version) if current_version else None

    return _build_admin_forms_payload_from_pack(
        pack,
        last_published_at=pack_record.created_at.isoformat() if pack_record and pack_record.created_at else None,
        last_published_by=(
            pack_record.created_by
            if pack_record is not None
            else ("builtin_default" if current_version == str(builtin.get("version") or "") else None)
        ),
    )


async def _save_admin_forms_pack(
    *,
    auth_context: AuthContext,
    payload: AdminFormsSaveRequest,
) -> AdminFormsSaveResult:
    return await _save_admin_forms_pack_service(auth_context=auth_context, payload=payload)


async def _save_admin_forms_draft(
    *,
    auth_context: AuthContext,
    payload: AdminFormsDraftSaveRequest,
) -> AdminFormsDraftSaveResult:
    return await _save_admin_forms_draft_service(auth_context=auth_context, payload=payload)


async def _validate_admin_forms_draft(
    *,
    payload: AdminFormsValidateRequest,
) -> AdminFormsValidateResult:
    return await _validate_admin_forms_draft_service(payload=payload)


async def _publish_admin_forms_draft(
    *,
    auth_context: AuthContext,
    payload: AdminFormsPublishRequest,
) -> AdminFormsPublishResult:
    return await _publish_admin_forms_draft_service(auth_context=auth_context, payload=payload)


async def _set_admin_forms_preferred(
    *,
    auth_context: AuthContext,
    payload: AdminFormsPreferredUpdateRequest,
) -> AdminFormsPreferredUpdateResult:
    return await _set_admin_forms_preferred_service(auth_context=auth_context, payload=payload)


def _policy_ref_code(template_code: str, kind: str) -> str:
    return normalize_template_code(f"{template_code}_{kind}_policy")


def _form_policy_ref(form: dict[str, object], kind: str) -> str | None:
    direct = str(form.get(f"{kind}_policy_ref") or "").strip()
    if direct:
        return direct
    code = str(form.get(f"{kind}_policy_code") or "").strip()
    if code:
        return code
    refs = form.get("policy_refs") if isinstance(form.get("policy_refs"), dict) else {}
    ref = refs.get(kind) if isinstance(refs, dict) else None
    if isinstance(ref, dict):
        value = str(ref.get("code") or "").strip()
        return value or None
    value = str(ref or "").strip()
    return value or None


def _policy_title(form: dict[str, object], kind: str) -> str:
    title = str(form.get("title") or form.get("key") or "").strip()
    labels = {
        "priority": "приоритет",
        "routing": "роутинг",
        "approval": "согласования",
        "diagnostic": "диагностика",
        "closure": "закрытие",
        "visibility": "видимость",
        "notification": "уведомления",
    }
    return f"{title}: {labels.get(kind, kind)}".strip(": ")


def _template_has_policy(template: AdminHelpdeskRequestTemplateItem, kind: str) -> bool:
    config = template.config if isinstance(template.config, dict) else {}
    if kind == "priority":
        return bool(template.priority_policy_code or config.get("priority_policy"))
    if kind == "routing":
        return bool(template.routing_policy_code or config.get("routing_policy"))
    if kind == "sla":
        return bool(template.sla_policy_code or template.sla_policy_id or config.get("sla_policy"))
    if kind == "closure":
        return bool(template.closure_policy_code or config.get("closure_policy"))
    return False


def _build_helpdesk_model_data_quality(
    request_templates: list[AdminHelpdeskRequestTemplateItem],
) -> list[AdminHelpdeskDataQualityItem]:
    issues: list[AdminHelpdeskDataQualityItem] = []
    required_fields = [
        ("workflow_profile_id", "workflow_profile_id", "Workflow profile is not linked"),
        ("priority_policy", "priority_policy", "Priority policy is not linked"),
        ("routing_policy", "routing_policy", "Routing policy is not linked"),
        ("sla_policy", "sla_policy", "SLA policy is not linked"),
        ("closure_policy", "closure_policy", "Closure policy is not linked"),
    ]
    for template in request_templates:
        if not template.is_active:
            continue
        for field, issue_code, message in required_fields:
            missing = False
            if field == "workflow_profile_id":
                missing = not bool(str(template.workflow_profile_id or "").strip())
            elif field == "priority_policy":
                missing = not _template_has_policy(template, "priority")
            elif field == "routing_policy":
                missing = not _template_has_policy(template, "routing")
            elif field == "sla_policy":
                missing = not _template_has_policy(template, "sla")
            elif field == "closure_policy":
                missing = not _template_has_policy(template, "closure")
            if missing:
                issues.append(
                    AdminHelpdeskDataQualityItem(
                        entity_type="request_template",
                        entity_code=template.template_code,
                        severity="warning",
                        issue_code=f"missing_{issue_code}",
                        field=field,
                        message=message,
                        remediation="Publish or link the policy before relying on this template in production.",
                    )
                )
    return issues


async def _build_helpdesk_model_payload() -> AdminHelpdeskModelPayload:
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        request_templates = [
            AdminHelpdeskRequestTemplateItem.model_validate(item)
            for item in await repo.list_request_templates(include_inactive=True)
        ]
        ticket_types = [
            AdminHelpdeskTicketTypeItem.model_validate(item)
            for item in await repo.list_ticket_types(include_inactive=True)
        ]
        form_schemas = [
            AdminHelpdeskFormSchemaItem.model_validate(item)
            for item in await repo.list_form_schemas(include_inactive=True)
        ]
        policies_raw = await repo.list_policies(include_inactive=True)
        policies = {
            kind: [AdminHelpdeskPolicyItem.model_validate(item) for item in items]
            for kind, items in policies_raw.items()
        }
        smart_views = [
            AdminHelpdeskSmartViewItem.model_validate(item)
            for item in await repo.list_smart_views(include_inactive=True)
        ]

    all_policies = [item for items in policies.values() for item in items]
    data_quality = _build_helpdesk_model_data_quality(request_templates)
    return AdminHelpdeskModelPayload(
        summary=AdminHelpdeskModelSummary(
            request_templates_count=len(request_templates),
            active_request_templates_count=sum(1 for item in request_templates if item.is_active),
            ticket_types_count=len(ticket_types),
            active_ticket_types_count=sum(1 for item in ticket_types if item.is_active),
            form_schemas_count=len(form_schemas),
            active_form_schemas_count=sum(1 for item in form_schemas if item.is_active),
            policies_count=len(all_policies),
            active_policies_count=sum(1 for item in all_policies if item.is_active),
            smart_views_count=len(smart_views),
            active_smart_views_count=sum(1 for item in smart_views if item.is_active),
            data_quality_issue_count=len(data_quality),
        ),
        capabilities=AdminHelpdeskModelCapabilities(
            registry_endpoint=_HELPDESK_MODEL_REGISTRY_ENDPOINT,
            publish_from_form_endpoint=_HELPDESK_MODEL_PUBLISH_FROM_FORM_ENDPOINT,
            republish_legacy_forms_endpoint=_HELPDESK_MODEL_REPUBLISH_LEGACY_FORMS_ENDPOINT,
            publish_policy_endpoint=_HELPDESK_MODEL_PUBLISH_POLICY_ENDPOINT,
            policy_diff_endpoint=_HELPDESK_MODEL_POLICY_DIFF_ENDPOINT,
            policy_deactivate_endpoint=_HELPDESK_MODEL_POLICY_DEACTIVATE_ENDPOINT,
            policy_rollback_endpoint=_HELPDESK_MODEL_POLICY_ROLLBACK_ENDPOINT,
            publish_ticket_type_endpoint=_HELPDESK_MODEL_PUBLISH_TICKET_TYPE_ENDPOINT,
            ticket_type_deactivate_endpoint=_HELPDESK_MODEL_TICKET_TYPE_DEACTIVATE_ENDPOINT,
            ticket_type_rollback_endpoint=_HELPDESK_MODEL_TICKET_TYPE_ROLLBACK_ENDPOINT,
            publish_form_schema_endpoint=_HELPDESK_MODEL_PUBLISH_FORM_SCHEMA_ENDPOINT,
            publish_smart_view_endpoint=_HELPDESK_MODEL_PUBLISH_SMART_VIEW_ENDPOINT,
            inheritance_order=["system", "ticket_type", "category", "request_template"],
            policy_kinds=sorted(POLICY_MODELS.keys()),
        ),
        request_templates=request_templates,
        ticket_types=ticket_types,
        form_schemas=form_schemas,
        policies=policies,
        smart_views=smart_views,
        data_quality=data_quality,
    )


async def _publish_helpdesk_template_from_form_dict(
    *,
    auth_context: AuthContext,
    form_payload: dict[str, object],
    publish_policies: bool,
    source: str = "forms_builder_visual_constructor",
    registry_republish: dict[str, object] | None = None,
) -> AdminHelpdeskPublishFromFormResult:
    preview_pack = validate_form_pack_schema(
        {
            "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
            "version": "registry-preview",
            "title": "Registry preview",
            "forms": [form_payload],
        }
    )
    form = preview_pack["forms"][0]
    template_code = normalize_template_code(form.get("key"))
    if not template_code:
        raise ValueError("form key is required")

    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    policies: dict[str, AdminHelpdeskPolicyItem] = {}
    policy_ref_by_kind: dict[str, str | None] = {}
    policy_fields = {
        "priority": "priority_policy",
        "routing": "routing_policy",
        "approval": "approval_policy",
        "sla": "sla_policy",
        "ola": "ola_policy",
        "diagnostic": "diagnostic_policy",
        "closure": "closure_policy",
        "visibility": "visibility_policy",
        "notification": "notification_policy",
        "reporting": "reporting_policy",
    }

    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        form_schema = await repo.publish_form_schema(
            schema_id=f"{template_code}_form",
            title=str(form.get("title") or template_code),
            description=str(form.get("description") or "").strip() or None,
            form_key=template_code,
            request_template_code=template_code,
            ticket_type=str(form.get("ticket_type") or "incident"),
            fields=form.get("fields") if isinstance(form.get("fields"), list) else [],
            field_roles=form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
            config={
                "source": source,
                "request_kind": form.get("request_kind") or template_code,
                **({"registry_republish": registry_republish} if registry_republish else {}),
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if publish_policies:
            for kind, field_name in policy_fields.items():
                explicit_ref = _form_policy_ref(form, kind)
                if explicit_ref:
                    policy_ref_by_kind[kind] = explicit_ref
                    continue
                config = form.get(field_name) if isinstance(form.get(field_name), dict) else {}
                if not config:
                    policy_ref_by_kind[kind] = None
                    continue
                policy_code = _policy_ref_code(template_code, kind)
                item = await repo.publish_policy(
                    kind=kind,
                    code=policy_code,
                    title=_policy_title(form, kind),
                    description=f"Опубликовано из визуального конструктора шаблона {template_code}",
                    config=config,
                    scope_level="request_template",
                    scope_ref=template_code,
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
                policies[kind] = AdminHelpdeskPolicyItem.model_validate(item)
                policy_ref_by_kind[kind] = policy_code
        else:
            for kind in policy_fields:
                policy_ref_by_kind[kind] = _form_policy_ref(form, kind)

        request_template = await repo.publish_request_template(
            template_code=template_code,
            public_title=str(form.get("title") or template_code),
            internal_name=f"{form.get('ticket_type') or 'process'} / {template_code}",
            description=str(form.get("description") or "").strip() or None,
            ticket_type=str(form.get("ticket_type") or "incident"),
            category_id=form.get("category_id") if form.get("category_id") is not None else None,
            service_id=form.get("service_id") if form.get("service_id") is not None else None,
            subcategory_id=form.get("subcategory_id") if form.get("subcategory_id") is not None else None,
            form_schema_id=f"{template_code}_form",
            workflow_profile_id=str(form.get("ticket_type") or "incident"),
            priority_policy_code=policy_ref_by_kind.get("priority"),
            routing_policy_code=policy_ref_by_kind.get("routing"),
            sla_policy_id=form.get("sla_policy_id") if form.get("sla_policy_id") is not None else None,
            sla_policy_code=policy_ref_by_kind.get("sla"),
            ola_policy_code=policy_ref_by_kind.get("ola"),
            approval_policy_code=policy_ref_by_kind.get("approval"),
            diagnostic_policy_code=policy_ref_by_kind.get("diagnostic"),
            closure_policy_code=policy_ref_by_kind.get("closure"),
            visibility_policy_code=policy_ref_by_kind.get("visibility"),
            notification_policy_code=policy_ref_by_kind.get("notification"),
            reporting_policy_code=policy_ref_by_kind.get("reporting"),
            config={
                "form": form,
                "form_schema": {
                    "schema_id": form_schema["schema_id"],
                    "version": form_schema["version"],
                    "field_count": len(form_schema.get("fields") or []),
                },
                **({"registry_republish": registry_republish} if registry_republish else {}),
                "field_roles": form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
                "suggested_playbook_id": form.get("suggested_playbook_id"),
            },
            overrides={
                "source": source,
                "publish_policies": bool(publish_policies),
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        await session.commit()

    typed_template = AdminHelpdeskRequestTemplateItem.model_validate(request_template)
    typed_form_schema = AdminHelpdeskFormSchemaItem.model_validate(form_schema)
    return AdminHelpdeskPublishFromFormResult(
        request_template=typed_template,
        form_schema=typed_form_schema,
        policies=policies,
        message=(
            f"Шаблон обращения {typed_template.template_code} опубликован в реестр как версия "
            f"{typed_template.version}. Политик опубликовано: {len(policies)}."
        ),
    )


async def _publish_helpdesk_template_from_form(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPublishFromFormRequest,
) -> AdminHelpdeskPublishFromFormResult:
    return await _publish_helpdesk_template_from_form_dict(
        auth_context=auth_context,
        form_payload=_serialize_admin_form_request(payload.form),
        publish_policies=payload.publish_policies,
    )


def _legacy_form_registry_fingerprint(
    *,
    form: dict[str, object],
    pack_key: str,
    pack_version: str | None,
    publish_policies: bool,
) -> str:
    payload = {
        "pack_key": pack_key,
        "pack_version": pack_version,
        "publish_policies": bool(publish_policies),
        "form": form,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _republish_legacy_request_forms(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskRepublishLegacyFormsRequest,
) -> AdminHelpdeskRepublishLegacyFormsResult:
    pack_key = str(payload.pack_key or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    if pack_key != DEFAULT_TICKET_FORM_PACK_KEY:
        raise ValueError("only request_forms pack is supported for legacy republish")
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"

    async with get_session() as session:
        form_repo = TicketFormPacksRepo(session)
        pack = await resolve_ticket_form_pack(form_repo, pack_key=pack_key)
        policy_repo = HelpdeskPolicyRepo(session)
        active_templates = {
            item["template_code"]: item
            for item in await policy_repo.list_request_templates(include_inactive=False)
        }

    forms = [item for item in pack.get("forms") or [] if isinstance(item, dict)]
    pack_version = str(pack.get("version") or "").strip() or None
    items: list[AdminHelpdeskRepublishLegacyFormsItem] = []
    published_count = 0
    skipped_count = 0
    failed_count = 0

    for form in forms:
        template_code = normalize_template_code(form.get("key"))
        if not template_code:
            failed_count += 1
            items.append(
                AdminHelpdeskRepublishLegacyFormsItem(
                    template_code="",
                    status="failed",
                    message="form key is required",
                )
            )
            continue
        fingerprint = _legacy_form_registry_fingerprint(
            form=form,
            pack_key=pack_key,
            pack_version=pack_version,
            publish_policies=payload.publish_policies,
        )
        active_template = active_templates.get(template_code) or {}
        active_config = active_template.get("config") if isinstance(active_template.get("config"), dict) else {}
        active_republish = (
            active_config.get("registry_republish")
            if isinstance(active_config.get("registry_republish"), dict)
            else {}
        )
        if not payload.force and active_republish.get("fingerprint") == fingerprint:
            skipped_count += 1
            items.append(
                AdminHelpdeskRepublishLegacyFormsItem(
                    template_code=template_code,
                    status="skipped_unchanged",
                    form_schema_id=active_template.get("form_schema_id"),
                    request_template_version=active_template.get("version"),
                    message="active registry version already matches legacy form",
                )
            )
            continue
        try:
            result = await _publish_helpdesk_template_from_form_dict(
                auth_context=auth_context,
                form_payload=form,
                publish_policies=payload.publish_policies,
                source="legacy_request_forms_republish",
                registry_republish={
                    "pack_key": pack_key,
                    "pack_version": pack_version,
                    "fingerprint": fingerprint,
                    "republished_by": actor_id,
                },
            )
        except Exception as exc:
            failed_count += 1
            items.append(
                AdminHelpdeskRepublishLegacyFormsItem(
                    template_code=template_code,
                    status="failed",
                    message=str(exc) or "failed to republish legacy form",
                )
            )
            continue
        published_count += 1
        items.append(
            AdminHelpdeskRepublishLegacyFormsItem(
                template_code=result.request_template.template_code,
                status="published",
                form_schema_id=result.form_schema.schema_id,
                request_template_version=result.request_template.version,
                published_policy_count=len(result.policies),
                message=result.message,
            )
        )

    return AdminHelpdeskRepublishLegacyFormsResult(
        summary=AdminHelpdeskRepublishLegacyFormsSummary(
            pack_key=pack_key,
            pack_version=pack_version,
            forms_seen_count=len(forms),
            published_templates_count=published_count,
            skipped_unchanged_count=skipped_count,
            failed_count=failed_count,
        ),
        items=items,
        message=(
            f"Legacy request forms republish complete: published={published_count}, "
            f"skipped={skipped_count}, failed={failed_count}."
        ),
    )


async def _publish_helpdesk_ticket_type(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPublishTicketTypeRequest,
) -> AdminHelpdeskPublishTicketTypeResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.publish_ticket_type(
            code=payload.code,
            title=payload.title,
            description=payload.description,
            default_workflow_profile_id=payload.default_workflow_profile_id,
            default_priority_policy_code=payload.default_priority_policy_code,
            default_routing_policy_code=payload.default_routing_policy_code,
            default_sla_policy_id=payload.default_sla_policy_id,
            default_sla_policy_code=payload.default_sla_policy_code,
            default_ola_policy_code=payload.default_ola_policy_code,
            default_approval_policy_code=payload.default_approval_policy_code,
            default_diagnostic_policy_code=payload.default_diagnostic_policy_code,
            default_closure_policy_code=payload.default_closure_policy_code,
            default_visibility_policy_code=payload.default_visibility_policy_code,
            default_notification_policy_code=payload.default_notification_policy_code,
            default_reporting_policy_code=payload.default_reporting_policy_code,
            feature_flags=payload.feature_flags,
            config=payload.config,
            actor_id=actor_id,
            actor_role=actor_role,
            requested_version=payload.requested_version,
        )
        await session.commit()

    ticket_type = AdminHelpdeskTicketTypeItem.model_validate(item)
    return AdminHelpdeskPublishTicketTypeResult(
        ticket_type=ticket_type,
        message=f"Ticket type {ticket_type.code} published as version {ticket_type.version}.",
    )


async def _publish_helpdesk_form_schema(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPublishFormSchemaRequest,
) -> AdminHelpdeskPublishFormSchemaResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.publish_form_schema(
            schema_id=payload.schema_id,
            title=payload.title,
            description=payload.description,
            form_key=payload.form_key,
            request_template_code=payload.request_template_code,
            ticket_type=payload.ticket_type,
            fields=payload.fields,
            field_roles=payload.field_roles,
            conditions=payload.conditions,
            config=payload.config,
            actor_id=actor_id,
            actor_role=actor_role,
            requested_version=payload.requested_version,
        )
        await session.commit()

    form_schema = AdminHelpdeskFormSchemaItem.model_validate(item)
    return AdminHelpdeskPublishFormSchemaResult(
        form_schema=form_schema,
        message=f"Form schema {form_schema.schema_id} published as version {form_schema.version}.",
    )


async def _deactivate_helpdesk_ticket_type(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskTicketTypeDeactivateRequest,
) -> AdminHelpdeskTicketTypeDeactivateResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.deactivate_ticket_type(
            code=payload.code,
            version=payload.version,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        await session.commit()

    ticket_type = AdminHelpdeskTicketTypeItem.model_validate(item)
    return AdminHelpdeskTicketTypeDeactivateResult(
        ticket_type=ticket_type,
        message=f"Ticket type {ticket_type.code} version {ticket_type.version} deactivated.",
    )


async def _rollback_helpdesk_ticket_type(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskTicketTypeRollbackRequest,
) -> AdminHelpdeskTicketTypeRollbackResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.rollback_ticket_type(
            code=payload.code,
            target_version=payload.target_version,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        await session.commit()

    ticket_type = AdminHelpdeskTicketTypeItem.model_validate(item)
    return AdminHelpdeskTicketTypeRollbackResult(
        ticket_type=ticket_type,
        message=(
            f"Ticket type {ticket_type.code} rolled back from {payload.target_version}; "
            f"new active version {ticket_type.version}."
        ),
    )


async def _publish_helpdesk_policy(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPublishPolicyRequest,
) -> AdminHelpdeskPublishPolicyResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.publish_policy(
            kind=payload.kind,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            config=payload.config,
            scope_level=payload.scope_level,
            scope_ref=payload.scope_ref,
            actor_id=actor_id,
            actor_role=actor_role,
            requested_version=payload.requested_version,
        )
        await session.commit()

    policy = AdminHelpdeskPolicyItem.model_validate(item)
    return AdminHelpdeskPublishPolicyResult(
        policy=policy,
        message=f"Политика {policy.code} опубликована в реестр как версия {policy.version}.",
    )


async def _diff_helpdesk_policy(
    *,
    payload: AdminHelpdeskPolicyDiffRequest,
) -> AdminHelpdeskPolicyDiffResult:
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        diff = await repo.diff_policy_versions(
            kind=payload.kind,
            code=payload.code,
            from_version=payload.from_version,
            to_version=payload.to_version,
        )
    return AdminHelpdeskPolicyDiffResult.model_validate(diff)


async def _deactivate_helpdesk_policy(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPolicyDeactivateRequest,
) -> AdminHelpdeskPolicyDeactivateResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.deactivate_policy(
            kind=payload.kind,
            code=payload.code,
            version=payload.version,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        await session.commit()
    policy = AdminHelpdeskPolicyItem.model_validate(item)
    return AdminHelpdeskPolicyDeactivateResult(
        policy=policy,
        message=f"Политика {policy.code} версии {policy.version} деактивирована.",
    )


async def _rollback_helpdesk_policy(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPolicyRollbackRequest,
) -> AdminHelpdeskPolicyRollbackResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.rollback_policy(
            kind=payload.kind,
            code=payload.code,
            target_version=payload.target_version,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        await session.commit()
    policy = AdminHelpdeskPolicyItem.model_validate(item)
    return AdminHelpdeskPolicyRollbackResult(
        policy=policy,
        message=f"Политика {policy.code} откатана к версии {payload.target_version}; новая активная версия {policy.version}.",
    )


async def _publish_helpdesk_smart_view(
    *,
    auth_context: AuthContext,
    payload: AdminHelpdeskPublishSmartViewRequest,
) -> AdminHelpdeskPublishSmartViewResult:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    filter_config, sort, columns = validate_smart_view_definition(
        filter_config=payload.filter,
        sort=payload.sort,
        columns=payload.columns,
    )
    async with get_session() as session:
        repo = HelpdeskPolicyRepo(session)
        item = await repo.publish_smart_view(
            code=payload.code,
            title=payload.title,
            description=payload.description,
            filter_config=filter_config,
            sort=sort,
            columns=columns,
            scope_level=payload.scope_level,
            scope_ref=payload.scope_ref,
            actor_id=actor_id,
            actor_role=actor_role,
            requested_version=payload.requested_version,
        )
        await session.commit()

    smart_view = AdminHelpdeskSmartViewItem.model_validate(item)
    return AdminHelpdeskPublishSmartViewResult(
        smart_view=smart_view,
        message=f"Smart view {smart_view.code} опубликован в реестр как версия {smart_view.version}.",
    )


def _next_playbook_version(existing_versions: list[str], requested: str | None) -> str:
    candidate = str(requested or "1.0.0").strip() or "1.0.0"
    existing = {str(item or "") for item in existing_versions}
    while candidate in existing:
        parts = candidate.split(".")
        if parts and parts[-1].isdigit():
            parts[-1] = str(int(parts[-1]) + 1)
            candidate = ".".join(parts)
        else:
            candidate = f"{candidate}.1"
    return candidate


async def _build_admin_playbooks_payload(state: object | None = None) -> AdminPlaybookPayload:
    playbooks: list[AdminPlaybookItem] = []
    block_catalog: list[dict] = [dict(item) for item in DIAGNOSTIC_MODULE_CATALOG]
    seen_catalog_tools = {str(item.get("tool") or "") for item in block_catalog if item.get("tool")}
    try:
        for capability in await CapabilityRegistry(
            state=state,
            endpoint_cutover_only=True,
        ).list_capabilities(device_id=None):
            if capability.execution_target in {"agent_builtin", "agent_managed_module"}:
                continue
            entry = normalize_capability_catalog_entry(capability, source=capability.source or "diagnostic_capability")
            capability_id = str(entry.get("capability_id") or entry.get("tool") or "")
            if not capability_id or capability_id in seen_catalog_tools:
                continue
            seen_catalog_tools.add(capability_id)
            block_catalog.append(entry)
    except Exception as exc:
        logger.warning(f"[web_admin_playbooks] failed to load diagnostic capability catalog: {exc}")
    try:
        async with get_session() as session:
            latest_rows = await session.execute(
                select(Playbook, PlaybookVersion, func.count(PlaybookStep.id))
                .join(PlaybookVersion, PlaybookVersion.playbook_id == Playbook.id, isouter=True)
                .join(PlaybookStep, PlaybookStep.playbook_version_id == PlaybookVersion.id, isouter=True)
                .where(Playbook.archived.is_(False))
                .group_by(Playbook.id, PlaybookVersion.id)
                .order_by(Playbook.key.asc(), PlaybookVersion.created_at.desc().nullslast(), PlaybookVersion.id.desc())
            )
            seen: set[int] = set()
            for playbook, version, steps_count in latest_rows.all():
                if playbook.id in seen:
                    continue
                seen.add(playbook.id)
                playbooks.append(
                    AdminPlaybookItem(
                        key=str(playbook.key),
                        name=str(playbook.name),
                        domain=playbook.domain,
                        version=str(version.version) if version is not None else None,
                        status=str(version.status) if version is not None else "draft",
                        blocks_count=int(steps_count or 0),
                        updated_at=_iso(getattr(version, "published_at", None) or getattr(version, "created_at", None)),
                    )
                )
    except Exception as exc:
        logger.warning(f"[web_admin_playbooks] DB unavailable, returning catalog only: {exc}")

    return AdminPlaybookPayload(
        capabilities=AdminPlaybookBuilderCapabilities(
            catalog_endpoint=_PLAYBOOKS_CATALOG_ENDPOINT,
            save_endpoint=_PLAYBOOKS_SAVE_ENDPOINT,
            block_types=[
                AdminFilterOption(value="diagnostic", label="Диагностика"),
                AdminFilterOption(value="decision", label="Условие"),
                AdminFilterOption(value="report", label="Пакет фактов"),
            ],
            module_kind_options=[
                AdminFilterOption(value="diagnostic", label="Диагностика"),
                AdminFilterOption(value="remediation", label="Исправление через подтверждение"),
            ],
        ),
        block_catalog=[
            AdminPlaybookBlockCatalogItem.model_validate(item)
            for item in block_catalog
        ],
        scenario_templates=[
            AdminScenarioTemplateItem.model_validate(item)
            for item in SCENARIO_TEMPLATES
        ],
        playbooks=playbooks,
    )


async def _save_admin_playbook(
    *,
    auth_context: AuthContext,
    payload: AdminPlaybookDraftRequest,
) -> AdminPlaybookSaveResult:
    raw_payload = payload.model_dump(mode="json")
    raw_payload["owner"] = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    normalized = normalize_playbook_draft(raw_payload)
    playbook_payload = normalized["playbook"]
    steps_payload = normalized["steps"]

    async with get_session() as session:
        result = await session.execute(select(Playbook).where(Playbook.key == playbook_payload["key"]))
        playbook = result.scalar_one_or_none()
        if playbook is None:
            playbook = Playbook(**playbook_payload)
            session.add(playbook)
            await session.flush()
        else:
            playbook.name = playbook_payload["name"]
            playbook.domain = playbook_payload["domain"]
            playbook.owner = playbook_payload["owner"]
            playbook.archived = False

        version_rows = await session.execute(
            select(PlaybookVersion.version).where(PlaybookVersion.playbook_id == playbook.id)
        )
        next_version = _next_playbook_version(list(version_rows.scalars().all()), normalized.get("version"))
        version = PlaybookVersion(
            playbook_id=playbook.id,
            version=next_version,
            manifest_json=normalized["manifest"],
            status="published",
            published_at=datetime.now(timezone.utc),
        )
        session.add(version)
        await session.flush()
        for step in steps_payload:
            session.add(
                PlaybookStep(
                    playbook_version_id=version.id,
                    step_key=step["step_key"],
                    order_no=step["order_no"],
                    type=step["type"],
                    tool=step["tool"],
                    params_template_json=step["params_template_json"],
                    if_expr=step["if_expr"],
                    timeout_sec=step["timeout_sec"],
                    retry_policy_json=step["retry_policy_json"],
                    continue_on_error=step["continue_on_error"],
                    parallel_group=step["parallel_group"],
                )
            )
        await session.commit()

    return AdminPlaybookSaveResult(
        key=playbook_payload["key"],
        version=next_version,
        status="published",
        blocks_count=len(steps_payload),
        message=f"Плейбук опубликован как версия {next_version}. Его можно запускать из форм при создании тикета.",
    )


async def _preview_admin_forms_route(
    *,
    payload: AdminFormsRoutePreviewRequest,
) -> AdminFormsRoutePreviewResult:
    raw_form = _serialize_admin_form_request(payload.form)
    preview_pack = validate_form_pack_schema(
        {
            "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
            "version": "preview",
            "title": "Preview",
            "description": "Preview",
            "forms": [raw_form],
        }
    )
    validated_submission = validate_form_submission(
        preview_pack,
        form_key=str(payload.form.key or "").strip(),
        raw_values=payload.form_payload,
    )
    custom_fields = build_form_custom_fields(validated_submission)
    context = build_form_routing_context(
        ticket_type=str(validated_submission.get("request_kind") or payload.form.request_kind or payload.form.key or ""),
        custom_fields=custom_fields,
    )

    async with get_session() as session:
        config_repo = TicketAdminConfigRepo(session)
        rules = await config_repo.list_routing_rules(include_disabled=False)
        queues = await config_repo.list_queues(include_inactive=True)
        queue_name_map = {queue.id: queue.name for queue in queues}
        matched_rule = find_matching_routing_rule(rules, context)

        target_queue_id = matched_rule.target_queue_id if matched_rule is not None else None
        target_queue_name = queue_name_map.get(target_queue_id) if target_queue_id is not None else None
        fallback_applied = False
        if matched_rule is None:
            fallback_queue = await config_repo.get_queue_by_code(FALLBACK_QUEUE_CODE)
            if fallback_queue is not None:
                target_queue_id = fallback_queue.id
                target_queue_name = fallback_queue.name
                fallback_applied = True

    return AdminFormsRoutePreviewResult(
        ticket_type=str(validated_submission.get("request_kind") or ""),
        request_kind=str(validated_submission.get("request_kind") or ""),
        target_queue_id=target_queue_id,
        target_queue_name=target_queue_name,
        fallback_applied=fallback_applied,
        matched_rule=(
            AdminFormsRoutePreviewMatchedRule(
                id=matched_rule.id,
                priority_order=matched_rule.priority_order,
                target_queue_id=matched_rule.target_queue_id,
                target_queue_name=queue_name_map.get(matched_rule.target_queue_id),
                condition_json=matched_rule.condition_json,
            )
            if matched_rule is not None
            else None
        ),
        summary_rows=[
            AdminFormsRoutePreviewSummaryRow(
                key=str(row.get("key") or ""),
                label=str(row.get("label") or row.get("key") or ""),
                value=str(row.get("value") or ""),
            )
            for row in validated_submission.get("summary_rows") or []
            if isinstance(row, dict)
        ],
    )


async def _preview_admin_forms_process(
    *,
    payload: AdminFormsProcessPreviewRequest,
) -> AdminFormsProcessPreviewResult:
    raw_form = _serialize_admin_form_request(payload.form)
    async with get_session() as session:
        config_repo = TicketAdminConfigRepo(session)
        rules = await config_repo.list_routing_rules(include_disabled=False)
        queues = await config_repo.list_queues(include_inactive=True)

    result = await build_form_process_preview(
        raw_form=raw_form,
        form_payload=payload.form_payload,
        queues=queues,
        routing_rules=rules,
    )
    return AdminFormsProcessPreviewResult.model_validate(result)


@require_auth("admin")
async def handle_web_admin_bootstrap(_request):
    payload = AdminBootstrapPayload(
        workspace="admin",
        features=[
            "devices_inventory",
            "agent_rollout",
            "modules_workbench",
            "forms_builder",
            "tech_panel",
        ],
        observer=AdminObserverCapabilities(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
        ),
    )
    return json_model_response(SuccessResponse[AdminBootstrapPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_quick(request: web.Request):
    lookback_hours = _parse_observer_lookback_hours(request.query.get("lookback_hours"))
    device_id = _compact_query_value(request.query.get("device_id"))
    payload = await _build_admin_observer_quick_payload(
        request=request,
        lookback_hours=lookback_hours,
        device_id=device_id,
    )
    return json_model_response(SuccessResponse[AdminObserverQuickPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_traces(request: web.Request):
    device_id = _compact_query_value(request.query.get("device_id"))
    lookback_hours = _parse_observer_lookback_hours(request.query.get("lookback_hours"))
    status_filter = _normalize_observer_status_filter(request.query.get("status"))
    root_kind_filter = _normalize_observer_root_kind_filter(request.query.get("root_kind"))
    limit = _parse_observer_trace_limit(request.query.get("limit"))
    query = _compact_query_value(request.query.get("q") or request.query.get("query"))
    trace_id = _compact_query_value(request.query.get("trace_id"))
    ticket_id = _compact_query_value(request.query.get("ticket_id"))
    operation_id = _compact_query_value(request.query.get("operation_id"))
    tool_name = _compact_query_value(request.query.get("tool_name"))
    module_name = _compact_query_value(request.query.get("module_name"))
    error_signature = _compact_query_value(request.query.get("error_signature"))
    min_duration_ms = _parse_optional_positive_int(request.query.get("min_duration_ms"))
    playbook_run_id = _parse_optional_positive_int(request.query.get("playbook_run_id"))
    step_run_id = _parse_optional_positive_int(request.query.get("step_run_id"))
    route = _compact_query_value(request.query.get("route"))
    source = _compact_query_value(request.query.get("source"))
    person_id = _compact_query_value(request.query.get("person_id"))
    error_code = _compact_query_value(request.query.get("error_code"))
    event_type = _compact_query_value(request.query.get("event_type"))
    payload = await _build_admin_observer_traces_payload(
        request=request,
        device_id=device_id,
        lookback_hours=lookback_hours,
        status_filter=status_filter,
        root_kind_filter=root_kind_filter,
        limit=limit,
        query=query,
        trace_id=trace_id,
        ticket_id=ticket_id,
        operation_id=operation_id,
        tool_name=tool_name,
        module_name=module_name,
        error_signature=error_signature,
        min_duration_ms=min_duration_ms,
        playbook_run_id=playbook_run_id,
        step_run_id=step_run_id,
        route=route,
        source=source,
        person_id=person_id,
        error_code=error_code,
        event_type=event_type,
    )
    return json_model_response(SuccessResponse[AdminObserverTracesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_trace_detail(request: web.Request):
    trace_id = request.match_info["trace_id"]
    try:
        payload = await _build_admin_observer_trace_detail_payload(request=request, trace_id=trace_id)
    except LookupError:
        payload = _build_missing_admin_observer_trace_detail_payload(trace_id)
    except Exception:
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить детали трассы",
                "error_code": "ADMIN_OBSERVER_TRACE_DETAIL_FAILED",
                "trace_id": trace_id,
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminObserverTraceDetailPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_devices(request: web.Request):
    query = str(request.query.get("query", "") or "").strip()
    status_filter = _normalize_status_filter(request.query.get("status"))
    include_archived = _truthy_query_flag(request.query.get("include_archived"))
    state = request.app.get("state")

    try:
        async with get_session() as session:
            devices = await DevicesRepo(session).list_all(include_deleted=include_archived)

        typed_devices: list[AdminDeviceItem] = []
        online_count = 0
        active_devices = [device for device in devices if getattr(device, "deleted_at", None) is None]
        archived_count = len(devices) - len(active_devices)
        duplicate_index = _build_duplicate_index(active_devices)
        for device in devices:
            device_id = str(getattr(device, "device_id", "") or "")
            is_deleted = getattr(device, "deleted_at", None) is not None
            is_online = False
            if is_online:
                online_count += 1
            if not _matches_status_filter(online=is_online, status_filter=status_filter):
                continue
            item = _build_device_item(device, online=is_online, duplicate_index=duplicate_index)
            if _matches_query(item, query):
                typed_devices.append(item)

        payload = AdminDevicesPayload(
            query=query,
            status_filter=status_filter,
            summary=AdminDevicesSummary(
                visible_count=len(typed_devices),
                online_count=online_count,
                duplicate_hosts=sum(1 for item in duplicate_index.values() if item.get("total", 0) > 1),
                cleanup_candidates=sum(item.get("cleanup", 0) for item in duplicate_index.values()),
                archived_count=archived_count,
            ),
            filters=AdminDevicesFilters(status_options=STATUS_OPTIONS, include_archived=include_archived),
            devices=typed_devices,
        )
    except Exception as exc:
        logger.warning(
            f"[web_admin_devices] DB unavailable, returning empty devices payload: "
            f"status_filter={status_filter}, error={exc}"
        )
        payload = _empty_devices_payload(
            query=query,
            status_filter=status_filter,
            include_archived=include_archived,
        )

    return json_model_response(SuccessResponse[AdminDevicesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_restore(request: web.Request):
    device_id = request.match_info["device_id"]
    auth_context = request.get("auth_context")
    actor_id = getattr(auth_context, "actor_id", None) or "admin"
    try:
        payload = await request.json() if request.can_read_body else {}
    except Exception:
        payload = {}
    restore_reason = str(payload.get("reason") or "").strip() or None

    try:
        async with get_session() as session:
            repo = DevicesRepo(session)
            device = await repo.get_by_device_id(device_id, include_deleted=True)
            if device is None:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Устройство не найдено",
                        "error_code": "DEVICE_NOT_FOUND",
                    },
                    status=404,
                )
            restored = await repo.restore_device(
                device_id,
                restored_by=actor_id,
                restore_reason=restore_reason,
            )
            if restored:
                await session.commit()
    except Exception as exc:
        logger.warning(f"[web_admin_device_restore] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось восстановить устройство из архива",
                "error_code": "ADMIN_DEVICE_RESTORE_FAILED",
            },
            status=500,
        )

    payload = AdminDeviceRestorePayload(
        device_id=device_id,
        is_deleted=False,
        restored_by=actor_id,
        restore_reason=restore_reason,
        tokens_restored=False,
        sessions_restored=False,
    )
    return json_model_response(SuccessResponse[AdminDeviceRestorePayload](data=payload))


def _cleanup_candidate_from_device(device, *, online: bool) -> AdminDeviceCleanupCandidate:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    last_seen_at = getattr(device, "last_seen_at", None)
    return AdminDeviceCleanupCandidate(
        device_id=str(getattr(device, "device_id", "") or ""),
        hostname=_device_hostname(device),
        agent_version=str(getattr(device, "agent_version", None) or metadata.get("agent_version") or metadata.get("version") or "").strip() or None,
        last_seen_at=last_seen_at.isoformat() if last_seen_at else None,
        machine_id_source=str(metadata.get("machine_id_source") or "").strip() or None,
        online=online,
    )


@require_auth("admin")
async def handle_web_admin_devices_cleanup_env_duplicates(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    hostname = str(data.get("hostname") or "").strip()
    apply_cleanup = bool(data.get("apply"))
    keep_device_id = str(data.get("keep_device_id") or "").strip()
    if not hostname:
        return web.json_response(
            {
                "status": "error",
                "error": "hostname is required",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    if apply_cleanup:
        return web.json_response(
            {
                "status": "error",
                "error": "Проверка live-состояния устройства доступна только через Endpoint Platform",
                "error_code": "ENDPOINT_CONTROL_PLANE_REQUIRED",
            },
            status=409,
        )
    auth_context = request.get("auth_context")
    actor_id = getattr(auth_context, "actor_id", None) or "admin"
    archived_count = 0
    candidates: list[AdminDeviceCleanupCandidate] = []
    kept_device_ids: list[str] = []

    try:
        async with get_session() as session:
            repo = DevicesRepo(session)
            devices = await repo.list_all()
            for device in devices:
                device_hostname = _device_hostname(device)
                if not device_hostname or device_hostname.lower() != hostname.lower():
                    continue
                device_id = str(getattr(device, "device_id", "") or "")
                metadata = getattr(device, "device_metadata", None)
                if not isinstance(metadata, dict):
                    metadata = {}
                source = str(metadata.get("machine_id_source") or "").strip().lower()
                online = False
                if device_id == keep_device_id or source in _STABLE_IDENTITY_SOURCES:
                    kept_device_ids.append(device_id)
                    continue
                if source != "env_uuid":
                    kept_device_ids.append(device_id)
                    continue
                candidates.append(_cleanup_candidate_from_device(device, online=online))
                if apply_cleanup:
                    deleted = await repo.archive_device(
                        device_id,
                        deleted_by=actor_id,
                        delete_reason=f"safe env_uuid duplicate cleanup for hostname {hostname}",
                    )
                    if deleted:
                        archived_count += 1
            if apply_cleanup:
                await session.commit()
    except Exception as exc:
        logger.warning(f"[web_admin_devices_cleanup_env_duplicates] failed: hostname={hostname} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось выполнить безопасную чистку дублей",
                "error_code": "ADMIN_DEVICE_CLEANUP_FAILED",
            },
            status=500,
        )

    payload = AdminDeviceCleanupPayload(
        hostname=hostname,
        applied=apply_cleanup,
        archived_count=archived_count,
        candidates=candidates,
        kept_device_ids=kept_device_ids,
    )
    return json_model_response(SuccessResponse[AdminDeviceCleanupPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_modules(request: web.Request):
    query = str(request.query.get("query", "") or "").strip()

    try:
        payload = await _build_admin_modules_payload(query=query)
    except Exception as exc:
        logger.warning(
            f"[web_admin_modules] DB unavailable, returning empty modules payload: "
            f"query={query!r}, error={exc}"
        )
        payload = _empty_admin_modules_payload(query=query)

    return json_model_response(SuccessResponse[AdminModulesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_forms_current(_request: web.Request):
    try:
        payload = await _build_admin_forms_payload()
    except Exception as exc:
        logger.warning(f"[web_admin_forms_current] Falling back to builtin form pack: {exc}")
        payload = _fallback_admin_forms_payload()

    return json_model_response(SuccessResponse[AdminFormsPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_forms_save(request: web.Request):
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminFormsSaveRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _save_admin_forms_pack(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_save] Failed to publish typed forms catalog: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать каталог форм",
                "error_code": "ADMIN_FORMS_SAVE_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminFormsSaveResult](data=result))


@require_auth("admin")
async def handle_web_admin_forms_save_draft(request: web.Request):
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminFormsDraftSaveRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру черновика каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _save_admin_forms_draft(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру черновика каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_save_draft] Failed to save forms draft: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сохранить черновик каталога форм",
                "error_code": "ADMIN_FORMS_DRAFT_SAVE_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsDraftSaveResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsDraftSaveResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_forms_validate(request: web.Request):
    try:
        raw_payload = await request.json()
        payload = AdminFormsValidateRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру каталога форм для проверки",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _validate_admin_forms_draft(payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_validate] Failed to validate forms draft: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось проверить каталог форм",
                "error_code": "ADMIN_FORMS_VALIDATE_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsValidateResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsValidateResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_forms_publish(request: web.Request):
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminFormsPublishRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру публикации каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_admin_forms_draft(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру публикации каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_publish] Failed to publish forms draft: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать каталог форм",
                "error_code": "ADMIN_FORMS_PUBLISH_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsPublishResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsPublishResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_forms_preferred(request: web.Request):
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminFormsPreferredUpdateRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте версию активного каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _set_admin_forms_preferred(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте версию активного каталога форм",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_preferred] Failed to switch preferred forms version: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось переключить активную версию каталога форм",
                "error_code": "ADMIN_FORMS_PREFERRED_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsPreferredUpdateResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsPreferredUpdateResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_forms_route_preview(request: web.Request):
    try:
        raw_payload = await request.json()
        payload = AdminFormsRoutePreviewRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру формы и пример значений",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _preview_admin_forms_route(payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Не удалось построить preview маршрута",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_route_preview] Failed to build route preview: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось построить preview маршрута",
                "error_code": "ADMIN_FORMS_ROUTE_PREVIEW_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsRoutePreviewResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsRoutePreviewResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_forms_process_preview(request: web.Request):
    try:
        raw_payload = await request.json()
        payload = AdminFormsProcessPreviewRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру формы и пример значений для process preview",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _preview_admin_forms_process(payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Не удалось построить process preview",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_forms_process_preview] Failed to build process preview: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось построить process preview",
                "error_code": "ADMIN_FORMS_PROCESS_PREVIEW_FAILED",
            },
            status=500,
        )

    typed_result = AdminFormsProcessPreviewResult.model_validate(result)
    return json_model_response(SuccessResponse[AdminFormsProcessPreviewResult](data=typed_result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_policies(_request: web.Request):
    try:
        payload = await _build_helpdesk_model_payload()
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_policies] Failed to load registry: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить реестр шаблонов и политик",
                "error_code": "HELPDESK_MODEL_REGISTRY_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminHelpdeskModelPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_publish_from_form(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPublishFromFormRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру шаблона обращения",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_helpdesk_template_from_form(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру шаблона обращения",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_publish_from_form] Failed to publish template: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать шаблон обращения в реестр",
                "error_code": "HELPDESK_TEMPLATE_PUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPublishFromFormResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_republish_legacy_forms(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskRepublishLegacyFormsRequest.model_validate(raw_payload or {})
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Check legacy forms republish payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _republish_legacy_request_forms(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Check legacy forms republish payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_republish_legacy_forms] Failed to republish legacy forms: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Failed to republish legacy request forms into helpdesk registry",
                "error_code": "HELPDESK_LEGACY_FORMS_REPUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskRepublishLegacyFormsResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_publish_ticket_type(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPublishTicketTypeRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Check ticket type payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_helpdesk_ticket_type(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Check ticket type payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_publish_ticket_type] Failed to publish ticket type: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Could not publish ticket type",
                "error_code": "HELPDESK_TICKET_TYPE_PUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPublishTicketTypeResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_publish_form_schema(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPublishFormSchemaRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Check form schema payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_helpdesk_form_schema(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Check form schema payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_publish_form_schema] Failed to publish form schema: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Could not publish form schema",
                "error_code": "HELPDESK_FORM_SCHEMA_PUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPublishFormSchemaResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_publish_policy(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPublishPolicyRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру политики",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_helpdesk_policy(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру политики",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_publish_policy] Failed to publish policy: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать политику в реестр",
                "error_code": "HELPDESK_POLICY_PUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPublishPolicyResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_policy_diff(request: web.Request):
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPolicyDiffRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте параметры сравнения политик",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _diff_helpdesk_policy(payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Версия политики не найдена",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_policy_diff] Failed to diff policy: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сравнить версии политики",
                "error_code": "HELPDESK_POLICY_DIFF_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPolicyDiffResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_policy_deactivate(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPolicyDeactivateRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте параметры деактивации политики",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _deactivate_helpdesk_policy(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Версия политики не найдена",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_policy_deactivate] Failed to deactivate policy: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось деактивировать версию политики",
                "error_code": "HELPDESK_POLICY_DEACTIVATE_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPolicyDeactivateResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_policy_rollback(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPolicyRollbackRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте параметры отката политики",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _rollback_helpdesk_policy(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Версия политики не найдена",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_policy_rollback] Failed to rollback policy: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось откатить политику",
                "error_code": "HELPDESK_POLICY_ROLLBACK_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPolicyRollbackResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_ticket_type_deactivate(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskTicketTypeDeactivateRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Check ticket type deactivation payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _deactivate_helpdesk_ticket_type(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Check ticket type deactivation payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_ticket_type_deactivate] Failed to deactivate ticket type: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Could not deactivate ticket type",
                "error_code": "HELPDESK_TICKET_TYPE_DEACTIVATE_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskTicketTypeDeactivateResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_ticket_type_rollback(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskTicketTypeRollbackRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Check ticket type rollback payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _rollback_helpdesk_ticket_type(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Check ticket type rollback payload",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_ticket_type_rollback] Failed to roll back ticket type: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Could not roll back ticket type",
                "error_code": "HELPDESK_TICKET_TYPE_ROLLBACK_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskTicketTypeRollbackResult](data=result))


@require_auth("admin")
async def handle_web_admin_helpdesk_model_publish_smart_view(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminHelpdeskPublishSmartViewRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру smart view",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _publish_helpdesk_smart_view(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру smart view",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_helpdesk_model_publish_smart_view] Failed to publish smart view: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать smart view в реестр",
                "error_code": "HELPDESK_SMART_VIEW_PUBLISH_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminHelpdeskPublishSmartViewResult](data=result))


@require_auth("admin")
async def handle_web_admin_playbooks_catalog(request: web.Request):
    try:
        payload = await _build_admin_playbooks_payload(request.app.get("state"))
    except TypeError as exc:
        if "positional" not in str(exc) and "argument" not in str(exc):
            raise
        payload = await _build_admin_playbooks_payload()
    return json_model_response(SuccessResponse[AdminPlaybookPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_playbooks_save(request: web.Request):
    auth_context: AuthContext = request["auth_context"]
    try:
        raw_payload = await request.json()
        payload = AdminPlaybookDraftRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру плейбука",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _save_admin_playbook(auth_context=auth_context, payload=payload)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Проверьте структуру плейбука",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_playbooks_save] Failed to publish playbook: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось опубликовать плейбук",
                "error_code": "ADMIN_PLAYBOOK_SAVE_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminPlaybookSaveResult](data=result))


@require_auth("admin")
async def handle_web_admin_patch_modules_rollout_settings(request: web.Request):
    try:
        raw_payload = await request.json()
        payload = AdminModulesRolloutSettingsUpdateRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте параметры rollout policy",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        settings = await _patch_admin_modules_rollout_settings(
            preferred_version_rollout_mode=payload.preferred_version_rollout_mode,
            sync_after_preferred_change=payload.sync_after_preferred_change,
        )
    except ValueError:
        return web.json_response(
            {
                "status": "error",
                "error": "Неизвестный режим preferred-version rollout",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_modules_rollout_settings] Failed to update settings: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сохранить rollout policy модулей",
                "error_code": "ADMIN_MODULES_ROLLOUT_SETTINGS_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminModulesRolloutSettings](data=settings))


@require_auth("admin")
async def handle_web_admin_set_module_preferred_version(request: web.Request):
    module_name = request.match_info["module_name"]
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminModulePreferredVersionRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Укажите версию модуля или null для снятия preferred",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _set_admin_module_preferred_version(
            request=request,
            auth_context=auth_context,
            module_name=module_name,
            version=payload.version,
        )
    except LookupError:
        return web.json_response(
            {
                "status": "error",
                "error": "Версия модуля не найдена",
                "error_code": "MODULE_NOT_FOUND",
                "module_name": module_name,
                "version": payload.version,
            },
            status=404,
        )
    except ValueError as exc:
        if str(exc) == "MODULE_WINDOWS_LIVE_TEST_REQUIRED":
            return web.json_response(
                {
                    "status": "error",
                    "error": "Windows-targeted module versions require a passed Windows lab-agent live test before preferred rollout.",
                    "error_code": "MODULE_WINDOWS_LIVE_TEST_REQUIRED",
                    "module_name": module_name,
                    "version": payload.version,
                },
                status=409,
            )
        return web.json_response(
            {
                "status": "error",
                "error": str(exc) or "Preferred version validation failed",
                "error_code": "VALIDATION_ERROR",
                "module_name": module_name,
            },
            status=400,
        )
    except Exception as exc:
        logger.error(f"[web_admin_module_preferred] Failed to update preferred version for {module_name}: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось обновить preferred-версию модуля",
                "error_code": "ADMIN_MODULE_PREFERRED_FAILED",
                "module_name": module_name,
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminModulePreferredVersionActionPayload](data=result))
