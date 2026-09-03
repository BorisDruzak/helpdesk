from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from loguru import logger
from sqlalchemy import or_, update

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.db.models import RegistryPerson, Ticket
from app.repos import ArtifactsRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import ensure_server_request_id, require_auth
from consent.service import ConsentAccessError, UserConsentService, serialize_user_consent
from domain_ports import (
    ActorRef,
    DomainPortContainer,
    OnBehalfAllowed,
    OnBehalfCandidateProjection,
    OnBehalfCandidatesProjection,
    OnBehalfDenied,
    OnBehalfPolicyProjection,
    RegistryReadActor,
    RequesterRef,
)
from observer.web_event_writer import write_web_cabinet_observer_event
from quality.feedback_service import TicketFeedbackService
from quality.reopen_service import TicketReopenService
from requester.identity_service import RequesterIdentityResolver, RequesterProfileValidationError
from registry.primary_agent_resolver import PrimaryAgentResolver
from registry.profile_schema_service import RequesterProfileSchemaService
from tickets.handlers import (
    _event_visible_to_requester,
    _normalize_attachment_refs,
    _push_ticket_event,
    _resolution_confirmation_pending,
    _resolve_attachment_descriptors,
    _serialize_event_for_requester,
    _serialize_message_for_requester,
    _store_resolution_confirmation_state,
)
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects
from tickets.diagnostic_target import resolve_ticket_diagnostic_target
from tickets.diagnostic_policy import normalize_diagnostic_consent_payload
from tickets.form_catalog import DEFAULT_TICKET_FORM_PACK_KEY, build_form_custom_fields, resolve_ticket_form_pack
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies
from tickets.priority_policy import compute_priority_from_policy
from tickets.public_access import verify_public_access_code
from tickets.requester_policy import requester_ticket_actions
from tickets.request_template_submission import resolve_create_form_submission
from tickets.service_catalog_preview import ServiceCatalogPreviewError, build_requester_service_catalog_preview
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver
from tickets.statuses import enrich_chat_payload_with_requester_name
from tickets.chat_idempotency import (
    ChatMessageIdError,
    chat_message_retry_payload_matches,
    normalize_chat_message_id,
)
from tickets.ticket_context import TicketContextBuilder, project_requester_ticket_context
from tickets.workflow_service import TicketWorkflowService

_AVAILABILITY_POLICY_FIELDS = (
    "available_without_completed_profile",
    "available_without_agent_binding",
    "requires_manual_triage",
    "contact_required",
    "allowed_for_anonymous",
)
_DEFAULT_AVAILABILITY_POLICY = {field: False for field in _AVAILABILITY_POLICY_FIELDS}
_CONTACT_FIELD_KEYS = (
    "contact",
    "contact_phone",
    "callback_phone",
    "phone",
    "email",
    "preferred_contact",
    "preferred_contact_method",
)


def _success(data: dict[str, Any]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _error(message: str, *, status: int = 400, error_code: str = "VALIDATION_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": error_code}, status=status)


def _validation_error(details: dict[str, Any]) -> web.Response:
    return web.json_response(
        {"status": "error", "error": "validation_error", "error_code": "VALIDATION_ERROR", "details": details},
        status=400,
    )


async def _build_requester_ticket_context_preview(
    session,
    *,
    state: Any | None,
    person: RegistryPerson | None,
    actor_id: str,
    requester_context: dict[str, Any],
    on_behalf_context: dict[str, str] | None = None,
    form: dict[str, Any] | None = None,
    policy_refs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if person is None or not str(getattr(person, "person_id", "") or "").strip():
        return None
    raw_context = on_behalf_context if isinstance(on_behalf_context, dict) else {}
    context = await TicketContextBuilder(session, state=state).build(
        creator_person_id=str(person.person_id),
        creator_actor_id=actor_id,
        affected_person_id=str(raw_context.get("affected_person_id") or "").strip() or None,
        on_behalf_reason=str(raw_context.get("on_behalf_reason") or raw_context.get("reason") or "").strip() or None,
        requester_context=requester_context,
        form=form or {},
        policy_refs=policy_refs or {},
    )
    return project_requester_ticket_context(context, actor_context={"actor_id": actor_id, "actor_role": "user"})


def _profile_incomplete_error(completion: dict[str, Any]) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "Заполните профиль, чтобы продолжить работу в кабинете пользователя.",
            "error_code": "REQUESTER_PROFILE_INCOMPLETE",
            "details": completion,
        },
        status=403,
    )


def _web_observer_actor_context(
    request: web.Request,
    auth_context: Any,
    *,
    idempotency_key: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    correlation_id = (
        _clean(request.headers.get("X-Request-ID"), max_length=120)
        or _clean(request.headers.get("X-Correlation-ID"), max_length=120)
        or None
    )
    return {
        "actor_id": getattr(auth_context, "actor_id", None),
        "actor_role": getattr(auth_context, "actor_role", None),
        "method": request.method,
        "server_request_id": ensure_server_request_id(request),
        "request_id": _clean(request.headers.get("X-Request-ID"), max_length=120),
        "correlation_id": correlation_id,
        "idempotency_key": _clean(idempotency_key, max_length=120),
        "operation_id": _clean(operation_id, max_length=120),
    }


async def _write_requester_web_observer_event(
    session,
    *,
    request: web.Request,
    auth_context: Any,
    source: str,
    event_type: str,
    severity: str,
    result: str,
    ticket_id: str | None = None,
    device_id: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    idempotency_key: str | None = None,
    operation_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        async with session.begin_nested():
            await write_web_cabinet_observer_event(
                session,
                source=source,
                event_type=event_type,
                severity=severity,
                route=request.path,
                actor_context=_web_observer_actor_context(
                    request,
                    auth_context,
                    idempotency_key=idempotency_key,
                    operation_id=operation_id,
                ),
                ticket_id=ticket_id,
                device_id=device_id,
                person_id=person_id,
                result=result,
                error_code=error_code,
                payload=payload,
            )
    except Exception as exc:
        logger.warning(f"[requester_observer] failed to write {source}.{event_type}: {exc}")


def _profile_completion_blocks(completion: dict[str, Any], key: str) -> bool:
    blocks = completion.get("blocks") if isinstance(completion.get("blocks"), dict) else {}
    return bool(blocks.get(key, not completion.get("complete", False)))


def _profile_completion_blocks_for_form(completion: dict[str, Any], key: str, availability_policy: dict[str, Any]) -> bool:
    if _profile_completion_blocks(completion, key) and availability_policy.get("available_without_completed_profile"):
        return False
    return _profile_completion_blocks(completion, key)


def _clean(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


def _availability_policy_from_form(form: dict[str, Any]) -> dict[str, bool]:
    raw_policy = form.get("availability_policy") if isinstance(form.get("availability_policy"), dict) else {}
    return {
        field: bool(form.get(field, raw_policy.get(field, _DEFAULT_AVAILABILITY_POLICY[field])))
        for field in _AVAILABILITY_POLICY_FIELDS
    }


async def _resolve_form_availability_policy(
    session,
    *,
    pack_key: str,
    pack_version: str | None,
    form_key: str,
    request_template_key: str,
) -> dict[str, bool]:
    lookup_keys = {key for key in (form_key, request_template_key) if key}
    if not lookup_keys:
        return dict(_DEFAULT_AVAILABILITY_POLICY)

    pack = await resolve_ticket_form_pack(
        TicketFormPacksRepo(session),
        pack_key=pack_key or DEFAULT_TICKET_FORM_PACK_KEY,
        version=pack_version or None,
        include_setup_assistance=True,
    )
    forms = pack.get("forms") if isinstance(pack.get("forms"), list) else []
    for item in forms:
        if not isinstance(item, dict):
            continue
        keys = {
            str(item.get("key") or "").strip(),
            str(item.get("request_template_key") or "").strip(),
        }
        if lookup_keys.intersection({key for key in keys if key}):
            return _availability_policy_from_form(item)
    return dict(_DEFAULT_AVAILABILITY_POLICY)


async def _resolve_requester_self_device_context(
    resolver: RequesterIdentityResolver,
    *,
    actor_id: str,
    supplied_device_id: str,
    state: Any | None,
) -> tuple[RegistryPerson | None, Any | None, str | None, str, str, dict[str, Any]]:
    if supplied_device_id:
        person, binding = await resolver.require_owned_device(actor_id=actor_id, device_id=supplied_device_id)
        return person, binding, supplied_device_id, "confirmed_binding", "authenticated_requester_workspace", {
            "status": "available",
            "reason_code": "selected_device",
            "source": "requester_selected_device",
            "candidate_count": 1,
        }

    person = await resolver.resolve_person_for_web_user(actor_id)
    _primary_device, primary_resolution, primary_binding = await resolver.resolve_primary_device(
        getattr(person, "person_id", None),
        state=state,
    )
    if primary_binding is not None:
        return (
            person,
            primary_binding,
            primary_binding.device_id,
            "confirmed_binding",
            "authenticated_requester_workspace",
            primary_resolution,
        )
    return person, None, None, "browser_no_device", "no_device", primary_resolution


def _has_contact_for_emergency(person: RegistryPerson | None, form_payload: dict[str, Any], data: dict[str, Any]) -> bool:
    for value in (getattr(person, "phone", None), getattr(person, "email", None), data.get("user_display_name")):
        if _clean(value, max_length=240):
            return True
    for source in (form_payload, data):
        for key in _CONTACT_FIELD_KEYS:
            if _clean(source.get(key), max_length=240):
                return True
    return False


def _manual_triage_custom_fields(
    *,
    availability_policy: dict[str, Any],
    no_valid_target: bool,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "request_form_availability": dict(availability_policy),
    }
    if availability_policy.get("requires_manual_triage"):
        fields.update(
            {
                "requires_manual_triage": True,
                "manual_triage_reason": "request_form_availability_policy",
            }
        )
    if no_valid_target:
        diagnostics = {
            "autorun_suppressed": True,
            "last_autorun_skip_reason": "manual_triage_required"
            if availability_policy.get("requires_manual_triage")
            else "target_device_missing",
            "diagnostic_target": {
                "target_device_id": None,
                "source": "no_primary_agent",
                "agent_status": "missing",
                "reason_code": "primary_device_missing",
            },
        }
        fields.update(
            {
                "diagnostic_target_source": "no_primary_agent",
                "target_agent_status": "missing",
                "diagnostic_target_reason_code": "primary_device_missing",
                "diagnostics": diagnostics,
            }
        )
    return fields


def _diagnostic_target_observer_payload(ticket: Any, custom_fields: dict[str, Any]) -> dict[str, Any] | None:
    target = resolve_ticket_diagnostic_target(ticket, custom_fields)
    status = _clean(target.agent_status, max_length=80).lower() or None
    source = _clean(target.source, max_length=120) or "unknown"
    reason_code = _clean(target.reason_code, max_length=120) or None

    if reason_code == "ambiguous_primary_device" or source == "ambiguous_primary_agent" or status == "ambiguous":
        event_type = "diagnostic_target_ambiguous"
        error_code = "DIAGNOSTIC_TARGET_AMBIGUOUS"
        status = status or "ambiguous"
    elif status == "offline":
        event_type = "diagnostic_target_offline"
        error_code = "DIAGNOSTIC_TARGET_OFFLINE"
    elif not target.dispatch_device_id or status == "missing":
        event_type = "diagnostic_target_missing"
        error_code = "DIAGNOSTIC_TARGET_MISSING"
        status = status or "missing"
    else:
        return None

    diagnostics = custom_fields.get("diagnostics") if isinstance(custom_fields.get("diagnostics"), dict) else {}
    return {
        "event_type": event_type,
        "error_code": error_code,
        "device_id": target.dispatch_device_id,
        "payload": {
            "diagnostic_target_source": source,
            "agent_status": status,
            "reason_code": reason_code,
            "created_on_behalf": bool(target.created_on_behalf),
            "has_dispatch_device": bool(target.dispatch_device_id),
            "manual_triage": bool(custom_fields.get("requires_manual_triage")),
            "diagnostics_autorun_suppressed": bool(diagnostics.get("autorun_suppressed")),
        },
    }


class _OnBehalfRequestError(ValueError):
    def __init__(self, message: str, *, status: int = 400, error_code: str = "ON_BEHALF_VALIDATION_ERROR"):
        super().__init__(message)
        self.status = status
        self.error_code = error_code


def _raw_on_behalf_context(data: dict[str, Any]) -> dict[str, str]:
    raw_context = data.get("ticket_context") if isinstance(data.get("ticket_context"), dict) else {}
    affected_person_id = _clean(raw_context.get("affected_person_id"), max_length=120)
    reason = _clean(raw_context.get("on_behalf_reason") or raw_context.get("reason"), max_length=1000)
    lookup = _clean(raw_context.get("affected_person_lookup"), max_length=240)
    payload: dict[str, str] = {}
    if affected_person_id:
        payload["affected_person_id"] = affected_person_id
    if reason:
        payload["on_behalf_reason"] = reason
    if lookup:
        payload["affected_person_lookup"] = lookup
    return payload


async def _resolve_on_behalf_policy(
    session,
    *,
    pack_key: str,
    pack_version: str | None,
    form_key: str,
    request_template_key: str,
) -> dict[str, Any]:
    lookup_keys = {key for key in (form_key, request_template_key) if key}
    if not lookup_keys:
        return {"allowed": False}

    pack = await resolve_ticket_form_pack(
        TicketFormPacksRepo(session),
        pack_key=pack_key or DEFAULT_TICKET_FORM_PACK_KEY,
        version=pack_version or None,
        include_setup_assistance=True,
    )
    forms = pack.get("forms") if isinstance(pack.get("forms"), list) else []
    for item in forms:
        if not isinstance(item, dict):
            continue
        keys = {
            str(item.get("key") or "").strip(),
            str(item.get("request_template_key") or "").strip(),
        }
        if not lookup_keys.intersection({key for key in keys if key}):
            continue
        policy = item.get("on_behalf_policy") if isinstance(item.get("on_behalf_policy"), dict) else {}
        return policy if policy.get("allowed") else {"allowed": False}
    return {"allowed": False}


def _on_behalf_policy_projection(policy: dict[str, Any]) -> OnBehalfPolicyProjection | None:
    """Freeze only server-resolved form policy fields for the Registry boundary."""

    try:
        return OnBehalfPolicyProjection(
            allowed=bool(policy.get("allowed")),
            scope=_clean(policy.get("allowed_scope"), max_length=80)
            or "same_department_or_privileged",
            reason_required=bool(policy.get("reason_required")),
        )
    except ValueError:
        return None


def _on_behalf_actor_from_verified_auth(
    auth_context: Any,
    *,
    creator: RequesterRef,
) -> RegistryReadActor | None:
    """Build requester actor correlation only from middleware and resolved identity."""

    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    actor_role = str(getattr(auth_context, "actor_role", "") or "").strip().lower()
    if actor_role not in {"user", "requester"} or not actor_id:
        return None
    try:
        return RegistryReadActor(
            actor=ActorRef(external_id=actor_id),
            role="user",
            requester=creator,
        )
    except ValueError:
        return None


def _requester_ref_from_resolved_person(person: RegistryPerson | None) -> RequesterRef | None:
    """Translate only the server-resolved Registry identity into an opaque ref."""

    person_id = str(getattr(person, "person_id", "") or "")
    if not person_id:
        return None
    try:
        return RequesterRef(external_id=person_id)
    except ValueError:
        return None


async def _authorize_on_behalf_context(
    session,
    *,
    auth_context: Any,
    creator: RequesterRef | None,
    policy: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, str] | None:
    raw_context = _raw_on_behalf_context(data)
    affected_person_id = raw_context.get("affected_person_id")
    if not affected_person_id:
        return None
    if creator is None:
        raise _OnBehalfRequestError(
            "Requester identity is required for on-behalf tickets",
            status=403,
            error_code="REQUESTER_IDENTITY_REQUIRED",
        )
    if affected_person_id == creator.external_id:
        return None
    policy_projection = _on_behalf_policy_projection(policy)
    if policy_projection is None:
        raise _OnBehalfRequestError(
            "On-behalf ticket creation is not allowed for this form",
            status=403,
            error_code="ON_BEHALF_NOT_ALLOWED",
        )
    reason = raw_context.get("on_behalf_reason", "")
    if policy_projection.allowed and policy_projection.reason_required and not reason:
        raise _OnBehalfRequestError(
            "On-behalf reason is required",
            status=400,
            error_code="ON_BEHALF_REASON_REQUIRED",
        )

    actor = _on_behalf_actor_from_verified_auth(auth_context, creator=creator)
    if actor is None:
        raise _OnBehalfRequestError(
            "Requester identity is required for on-behalf tickets",
            status=403,
            error_code="REQUESTER_IDENTITY_REQUIRED",
        )
    try:
        affected = RequesterRef(external_id=affected_person_id)
    except ValueError:
        affected = None
    outcome = (
        await DomainPortContainer.from_config(registry_session=session).registry.authorize_on_behalf(
            actor=actor,
            creator=creator,
            affected=affected,
            policy=policy_projection,
            lookup=raw_context.get("affected_person_lookup") or None,
        )
        if affected is not None
        else None
    )
    if isinstance(outcome, OnBehalfDenied) and outcome.code == "registry_on_behalf_not_allowed":
        raise _OnBehalfRequestError(
            "On-behalf ticket creation is not allowed for this form",
            status=403,
            error_code="ON_BEHALF_NOT_ALLOWED",
        )
    if not isinstance(outcome, OnBehalfAllowed) or outcome.affected.external_id != affected_person_id:
        raise _OnBehalfRequestError(
            "Affected person is outside the allowed scope",
            status=403,
            error_code="ON_BEHALF_SCOPE_DENIED",
        )
    context = {"affected_person_id": outcome.affected.external_id}
    if reason:
        context["on_behalf_reason"] = reason
    if raw_context.get("affected_person_lookup"):
        context["affected_person_lookup"] = raw_context["affected_person_lookup"]
    return context


async def _serialize_on_behalf_person(
    session,
    person: OnBehalfCandidateProjection,
    *,
    state: Any | None = None,
) -> dict[str, Any]:
    # PrimaryAgentResolver is intentionally separate deferred Registry debt; it
    # decorates the existing response but does not participate in candidate
    # visibility or authorization.
    resolved = await PrimaryAgentResolver(session, state=state).resolve_for_person(
        person.person.external_id
    )
    primary_status = "available" if resolved.get("resolved") else "missing"
    if not resolved.get("resolved") and resolved.get("reason_code") == "ambiguous_primary_device":
        primary_status = "ambiguous"
    return {
        "person_id": person.person.external_id,
        "display_name": person.display_name,
        "full_name": person.full_name,
        "email": person.email,
        "department": {
            "id": person.department.external_id if person.department is not None else None,
            "name": person.department_label,
        },
        "location": {
            "id": person.location.external_id if person.location is not None else None,
            "display_name": person.location_label,
        },
        "primary_agent": {
            "status": primary_status,
            "online": resolved.get("online") if resolved.get("resolved") else None,
        },
    }


def _has_catalog_selection(data: dict[str, Any]) -> bool:
    return any(
        _clean(data.get(key), max_length=240)
        for key in ("service_code", "offering_code", "offering_full_code", "full_offering_code", "request_template_key", "form_key")
    )


def _web_form_runtime_preview_payload(
    data: dict[str, Any],
    *,
    preview: dict[str, Any],
    form_key: str,
    request_template_key: str,
    account_mode: str,
) -> dict[str, Any]:
    approval = preview.get("approval") if isinstance(preview.get("approval"), dict) else {}
    diagnostics = preview.get("diagnostics") if isinstance(preview.get("diagnostics"), dict) else {}
    blockers = preview.get("blockers") if isinstance(preview.get("blockers"), list) else []
    warnings = preview.get("warnings") if isinstance(preview.get("warnings"), list) else []
    return {
        "stage": "preview",
        "has_catalog_selection": _has_catalog_selection(data),
        "form_pack_key": _clean(data.get("form_pack_key"), max_length=120) or None,
        "form_pack_version": _clean(data.get("form_pack_version"), max_length=120) or None,
        "form_key": form_key,
        "request_template_key": request_template_key,
        "account_mode": account_mode,
        "form_payload_present": isinstance(data.get("form_payload"), dict) and bool(data.get("form_payload")),
        "preview_ok": bool(preview.get("ok")),
        "service_selected": bool((preview.get("service") if isinstance(preview.get("service"), dict) else {}).get("code")),
        "offering_selected": bool((preview.get("offering") if isinstance(preview.get("offering"), dict) else {}).get("code")),
        "approval_required": bool(approval.get("required")),
        "diagnostics_required": bool(diagnostics.get("required")),
        "diagnostic_consent_required": bool(diagnostics.get("consent_required")),
        "sla_expected": bool(preview.get("expected_first_response") or preview.get("expected_resolution")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _web_form_runtime_create_payload(
    data: dict[str, Any],
    *,
    ticket: Any,
    ticket_custom_fields: dict[str, Any],
    form_key: str,
    request_template_key: str,
    account_mode: str,
) -> dict[str, Any]:
    priority = ticket_custom_fields.get("priority_decision")
    priority = priority if isinstance(priority, dict) else {}
    routing = ticket_custom_fields.get("routing_decision")
    routing = routing if isinstance(routing, dict) else {}
    request_template = ticket_custom_fields.get("request_template")
    request_template = request_template if isinstance(request_template, dict) else {}
    computed = request_template.get("computed") if isinstance(request_template.get("computed"), dict) else {}
    policy_refs = request_template.get("policy_refs") if isinstance(request_template.get("policy_refs"), dict) else {}
    requester_context = (
        ticket_custom_fields.get("requester_context_snapshot")
        if isinstance(ticket_custom_fields.get("requester_context_snapshot"), dict)
        else {}
    )
    profile_schema = (
        requester_context.get("profile_schema")
        if isinstance(requester_context.get("profile_schema"), dict)
        else {}
    )
    queue_id = routing.get("to_queue_id") if routing.get("to_queue_id") is not None else routing.get("queue_id")
    sla_configured = bool(
        getattr(ticket, "sla_policy_id", None)
        or request_template.get("sla_policy_id")
        or request_template.get("sla_policy_code")
        or request_template.get("sla_policy")
        or policy_refs.get("sla")
    )
    sla_due_present = bool(getattr(ticket, "first_response_due_at", None) or getattr(ticket, "resolution_due_at", None))
    return {
        "stage": "create",
        "has_catalog_selection": _has_catalog_selection(data),
        "form_pack_key": ticket_custom_fields.get("resolved_pack_key") or ticket_custom_fields.get("request_form_pack_key"),
        "form_pack_version": ticket_custom_fields.get("resolved_pack_version") or ticket_custom_fields.get("request_form_version"),
        "form_key": form_key,
        "request_template_key": request_template_key,
        "resolved_from": ticket_custom_fields.get("resolved_from"),
        "resolved_template_version": ticket_custom_fields.get("resolved_template_version"),
        "resolved_form_schema_id_present": bool(ticket_custom_fields.get("resolved_form_schema_id")),
        "resolved_form_schema_version": ticket_custom_fields.get("resolved_form_schema_version"),
        "profile_schema_version": profile_schema.get("version"),
        "account_mode": account_mode,
        "form_payload_present": isinstance(data.get("form_payload"), dict) and bool(data.get("form_payload")),
        "request_template_source": request_template.get("source"),
        "priority_class": priority.get("effective_priority") or priority.get("priority_class") or computed.get("priority"),
        "priority_source": priority.get("priority_source") or computed.get("priority_source"),
        "routing_source": routing.get("source") or computed.get("routing_source"),
        "queue_resolved": queue_id is not None or computed.get("queue_id") is not None,
        "matched_routing_rule": bool(routing.get("matched_rule") or computed.get("matched_routing_rule")),
        "sla_configured": sla_configured,
        "sla_started": sla_due_present,
        "sla_due_present": sla_due_present,
        "approval_required": bool(computed.get("approval_required")),
        "diagnostics_suggested": bool(computed.get("suggested_diagnostics")),
        "manual_triage": bool(ticket_custom_fields.get("manual_triage_required")),
    }


def _requester_chat_message_observer_payload(
    *,
    message_payload: dict[str, Any],
    attachments: list[dict[str, Any]],
    status_result: Any | None,
) -> dict[str, Any]:
    return {
        "message_present": bool(str(message_payload.get("text") or "").strip()),
        "attachment_count": len(attachments),
        "visibility": str(message_payload.get("visibility") or "public"),
        "status_transitioned": bool(status_result),
    }


def _requester_closure_observer_payload(
    *,
    from_status: str | None,
    ticket: Any | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "from_status": from_status,
        "to_status": getattr(ticket, "status", None),
        "reason_present": bool(_clean(data.get("reason"), max_length=200)),
        "confirmation_pending_cleared": bool(ticket is not None and not _resolution_confirmation_pending(ticket)),
    }


def _requester_feedback_observer_payload(
    *,
    data: dict[str, Any],
    result: dict[str, Any],
    request_metadata_present: bool,
) -> dict[str, Any]:
    reason_codes = data.get("reason_codes") if isinstance(data.get("reason_codes"), list) else []
    return {
        "rating_present": data.get("rating") is not None,
        "problem_resolved": data.get("problem_resolved") if isinstance(data.get("problem_resolved"), bool) else None,
        "resolution_confirmed": data.get("resolution_confirmed")
        if isinstance(data.get("resolution_confirmed"), bool)
        else None,
        "reason_code_count": len([item for item in reason_codes if str(item or "").strip()]),
        "comment_present": bool(_clean(data.get("comment"), max_length=200)),
        "metadata_present": request_metadata_present,
        "reopen_available": bool(result.get("reopen_available")),
    }


def _requester_reopen_observer_payload(
    *,
    from_status: str | None,
    data: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "from_status": from_status,
        "to_status": result.get("status"),
        "reason_code_present": bool(_clean(data.get("reason_code"), max_length=120)),
        "reason_comment_present": bool(_clean(data.get("reason_comment"), max_length=200)),
        "linked_feedback_present": bool(_clean(data.get("linked_feedback_id"), max_length=120)),
        "linked_knowledge_item_present": bool(_clean(data.get("linked_knowledge_item_id"), max_length=120)),
    }


def _priority_policy_fallback(data: dict[str, Any]) -> dict[str, Any]:
    fallback: dict[str, Any] = {
        "impact": data.get("impact"),
        "urgency": data.get("urgency"),
        "importance": data.get("importance"),
        "actor_role": "requester",
        "manual_actor_role": "requester",
    }
    manual_priority = data.get("manual_priority")
    if manual_priority is not None:
        fallback["manual_priority"] = manual_priority
        fallback["manual_reason"] = data.get("manual_reason") or data.get("manual_priority_reason")
    return fallback


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _status_filter(request: web.Request) -> list[str] | None:
    raw = _clean(request.query.get("status"), max_length=120)
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


@require_auth("user")
async def handle_web_requester_bootstrap(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        payload = await RequesterIdentityResolver(session, state=request.app.get("state")).build_bootstrap(
            actor_id=auth_context.actor_id,
            state=request.app.get("state"),
        )
    return _success(payload)


@require_auth("user")
async def handle_web_requester_devices(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        devices = await resolver.list_allowed_devices(person.person_id if person else None, state=request.app.get("state"))
    return _success({"devices": devices, "count": len(devices)})


@require_auth("user")
async def handle_web_requester_profile(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        payload = await RequesterIdentityResolver(session, state=request.app.get("state")).build_profile(
            actor_id=auth_context.actor_id,
            state=request.app.get("state"),
        )
    return _success(payload)


@require_auth("user")
async def handle_web_requester_on_behalf_people(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    query = _clean(request.query.get("q"), max_length=120)
    form_key = _clean(request.query.get("form_key"), max_length=120)
    request_template_key = _clean(request.query.get("request_template_key"), max_length=120)
    pack_key = _clean(request.query.get("form_pack_key"), max_length=120) or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = _clean(request.query.get("form_pack_version"), max_length=120) or None
    if len(query) < 2:
        return _success({"people": []})

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        creator = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        if creator is None:
            return _error(
                "Requester identity is required for on-behalf search",
                status=403,
                error_code="REQUESTER_IDENTITY_REQUIRED",
            )
        try:
            creator_ref = RequesterRef(external_id=str(creator.person_id))
        except ValueError:
            return _error(
                "Requester identity is required for on-behalf search",
                status=403,
                error_code="REQUESTER_IDENTITY_REQUIRED",
            )
        actor = _on_behalf_actor_from_verified_auth(auth_context, creator=creator_ref)
        if actor is None:
            return _error(
                "Requester identity is required for on-behalf search",
                status=403,
                error_code="REQUESTER_IDENTITY_REQUIRED",
            )
        policy = await _resolve_on_behalf_policy(
            session,
            pack_key=pack_key,
            pack_version=pack_version,
            form_key=form_key,
            request_template_key=request_template_key,
        )
        policy_projection = _on_behalf_policy_projection(policy)
        if policy_projection is None:
            return _success({"people": []})
        result = await DomainPortContainer.from_config(
            registry_session=session
        ).registry.on_behalf_candidates(
            actor=actor,
            creator=creator_ref,
            policy=policy_projection,
            query=query,
        )
        scoped_people = result.items if isinstance(result, OnBehalfCandidatesProjection) else ()
        people = [
            await _serialize_on_behalf_person(session, person, state=request.app.get("state"))
            for person in scoped_people
        ]
    return _success({"people": people})


@require_auth("user")
async def handle_web_requester_profile_update(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await _json_body(request)
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        try:
            payload = await resolver.update_own_profile(actor_id=auth_context.actor_id, payload=data)
            await session.commit()
        except RequesterProfileValidationError as exc:
            await session.rollback()
            return _validation_error(exc.details or {"profile": str(exc)})
        except PermissionError as exc:
            await session.rollback()
            return _error(str(exc), status=403, error_code="REQUESTER_PROFILE_FORBIDDEN")
    return _success(payload)


@require_auth("user")
async def handle_web_requester_device_detail(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = _clean(request.match_info.get("device_id"), max_length=80)
    if not device_id:
        return _error("device not found", status=404, error_code="NOT_FOUND")
    async with get_session() as session:
        try:
            payload = await RequesterIdentityResolver(session, state=request.app.get("state")).get_device_detail(
                actor_id=auth_context.actor_id,
                device_id=device_id,
                state=request.app.get("state"),
            )
        except PermissionError:
            return _error("device not found", status=404, error_code="NOT_FOUND")
    return _success(payload)


@require_auth("user")
async def handle_web_requester_tickets(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    limit = int(request.query.get("limit") or 100)
    async with get_session() as session:
        tickets = await RequesterIdentityResolver(session, state=request.app.get("state")).list_tickets(
            actor_id=auth_context.actor_id,
            limit=limit,
        )
        payload = [ticket_to_dict(ticket, visibility="requester") for ticket in tickets]
    return _success({"tickets": payload, "count": len(payload)})


@require_auth("user")
async def handle_web_requester_ticket_detail(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    async with get_session() as session:
        ticket = await RequesterIdentityResolver(session, state=request.app.get("state")).get_ticket(
            actor_id=auth_context.actor_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        repo = TicketEventsRepo(session)
        raw_events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=200)
        visible_events = [event for event in raw_events if _event_visible_to_requester(event)]
        messages = [event for event in visible_events if getattr(event, "event_type", None) == "chat_message"]
        payload = ticket_to_dict(ticket, visibility="requester")
    return _success(
        {
            "ticket": payload,
            "messages": [_serialize_message_for_requester(event, ticket=ticket) for event in messages],
            "events": [_serialize_event_for_requester(event, ticket=ticket) for event in visible_events],
        }
    )


@require_auth("user")
async def handle_web_requester_consents(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        items = await UserConsentService(session).list_for_requester(
            requester_external_ref=resolver.requester_external_ref(person),
            requester_person_id=person.person_id if person else None,
            statuses=_status_filter(request),
        )
        await session.commit()
    return _success({"consents": items, "count": len(items)})


@require_auth("user")
async def handle_web_requester_consent_detail(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    consent_id = _clean(request.match_info.get("consent_id"), max_length=80)
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        row = await UserConsentService(session).get_for_requester(
            consent_id=consent_id,
            requester_external_ref=resolver.requester_external_ref(person),
            requester_person_id=person.person_id if person else None,
        )
        await session.commit()
    if row is None:
        return _error("consent not found", status=404, error_code="NOT_FOUND")
    return _success({"consent": serialize_user_consent(row)})


async def _handle_web_requester_consent_decision(request: web.Request, decision: str) -> web.Response:
    auth_context = request["auth_context"]
    consent_id = _clean(request.match_info.get("consent_id"), max_length=80)
    data = await _json_body(request)
    reason = _clean(data.get("reason"), max_length=1000)
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        try:
            row = await UserConsentService(session, state=request.app.get("state")).decide_from_browser(
                consent_id=consent_id,
                decision=decision,
                requester_external_ref=resolver.requester_external_ref(person),
                requester_person_id=person.person_id if person else None,
                actor_id=auth_context.actor_id,
                reason=reason,
            )
            await session.commit()
        except ConsentAccessError as exc:
            await session.rollback()
            return _error(str(exc), status=exc.status, error_code=exc.error_code)
        except ValueError as exc:
            await session.rollback()
            return _error(str(exc), status=400, error_code="VALIDATION_ERROR")
    return _success({"consent": serialize_user_consent(row)})


@require_auth("user")
async def handle_web_requester_consent_approve(request: web.Request) -> web.Response:
    return await _handle_web_requester_consent_decision(request, "approved")


@require_auth("user")
async def handle_web_requester_consent_deny(request: web.Request) -> web.Response:
    return await _handle_web_requester_consent_decision(request, "denied")


@require_auth("user")
async def handle_web_requester_ticket_claim_public(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await _json_body(request)
    ticket_id = _clean(data.get("ticket_id"), max_length=80)
    code = _clean(data.get("code"), max_length=80)
    if not ticket_id:
        return _validation_error({"ticket_id": "ticket_id is required"})
    if not code:
        return _validation_error({"code": "code is required"})

    async with get_session() as session:
        repo = TicketEventsRepo(session)
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        ticket = await repo.get_ticket(ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        if not verify_public_access_code(ticket, code):
            return _error("invalid public access code", status=403, error_code="INVALID_PUBLIC_ACCESS_CODE")

        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        if person is None:
            return _error(
                "requester identity is required to claim a public ticket",
                status=403,
                error_code="REQUESTER_IDENTITY_REQUIRED",
            )
        existing_person_id = getattr(ticket, "requester_person_id", None)
        if existing_person_id and existing_person_id != person.person_id:
            return _error("ticket is already claimed", status=409, error_code="PUBLIC_TICKET_ALREADY_CLAIMED")

        previous_requester_id = getattr(ticket, "requester_id", None)
        custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
        custom_fields["requester_claim"] = {
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "claimed_by_actor_id": auth_context.actor_id,
            "previous_requester_id": previous_requester_id,
            "source": "requester_workspace",
        }
        public_access = custom_fields.get("public_access")
        if isinstance(public_access, dict):
            public_access = dict(public_access)
            public_access["unbound"] = False
            custom_fields["public_access"] = public_access

        claim_result = await session.execute(
            update(Ticket)
            .where(
                Ticket.ticket_id == ticket.ticket_id,
                or_(Ticket.requester_person_id.is_(None), Ticket.requester_person_id == person.person_id),
            )
            .values(
                requester_id=auth_context.actor_id,
                requester_person_id=person.person_id,
                custom_fields=custom_fields,
                updated_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        if claim_result.rowcount != 1:
            return _error("ticket is already claimed", status=409, error_code="PUBLIC_TICKET_ALREADY_CLAIMED")
        await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="requester_ticket_claimed",
            payload={
                "actor_id": auth_context.actor_id,
                "actor_role": "requester",
                "requester_person_id": person.person_id,
                "previous_requester_id": previous_requester_id,
                "source": "requester_workspace",
            },
            trace_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
        )
        await session.commit()
        await session.refresh(ticket)

    return _success(
        {
            "ticket_id": ticket_id,
            "claimed": True,
            "requester_person_id": getattr(ticket, "requester_person_id", None) if ticket else None,
            "ticket": ticket_to_dict(ticket, visibility="requester") if ticket else None,
        }
    )


@require_auth("user")
async def handle_web_requester_ticket_message(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    try:
        data = await request.json()
    except Exception:
        return _error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _error("JSON body must be an object", status=400)

    text = _clean(data.get("text"), max_length=5000)
    try:
        attachment_refs = _normalize_attachment_refs(data.get("attachment_refs"))
    except ValueError as exc:
        return _validation_error({"attachment_refs": str(exc)})
    if not text and not attachment_refs:
        return _validation_error({"text": "text or attachment_refs is required"})

    try:
        message_id = normalize_chat_message_id(data.get("message_id"))
    except ChatMessageIdError as exc:
        return _error(str(exc), status=400, error_code="INVALID_MESSAGE_ID")
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        actions = requester_ticket_actions(ticket)
        if not actions["can_send_message"]:
            return _error(
                "requester message is not available for this ticket status",
                status=409,
                error_code="REQUESTER_TICKET_ACTION_NOT_AVAILABLE",
            )

        attachments: list[dict[str, Any]] = []
        if attachment_refs:
            try:
                attachments = await _resolve_attachment_descriptors(
                    ArtifactsRepo(session),
                    ticket.ticket_id,
                    ticket.device_id,
                    attachment_refs,
                )
            except ValueError as exc:
                return _validation_error({"attachment_refs": [str(exc)]})

        payload: dict[str, Any] = {
            "message_id": message_id,
            "sender_role": "user",
            "sender_display_name": auth_context.actor_id,
            "from": "user",
            "text": text,
            "visibility": "public",
            "requester_person_id": getattr(ticket, "requester_person_id", None),
            "requester_binding_id": getattr(ticket, "requester_binding_id", None),
            "requester_account_session_id": getattr(ticket, "requester_account_session_id", None),
            "requester_account_mode": getattr(ticket, "requester_account_mode", None),
        }
        if metadata:
            payload["metadata"] = metadata
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
        if attachment_refs:
            payload["attachment_refs"] = attachment_refs
            payload["attachments"] = attachments

        repo = TicketEventsRepo(session)
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload=payload,
            trace_id=str(uuid.uuid4()),
            event_id=message_id,
        )

        inserted_message = result is not None
        event_id = int(result[0]) if result and result[0] is not None else None
        attachments_count = len(attachments)
        if not inserted_message:
            existing_message = await repo.get_chat_message_by_message_id(ticket.ticket_id, message_id)
            if existing_message is None:
                return _error("message retry could not be resolved", status=409, error_code="MESSAGE_RETRY_NOT_FOUND")
            event_id = int(existing_message.id)
            existing_payload = existing_message.payload if isinstance(existing_message.payload, dict) else {}
            if not chat_message_retry_payload_matches(existing_payload, payload):
                return _error(
                    "message retry payload does not match the original message",
                    status=409,
                    error_code="MESSAGE_RETRY_PAYLOAD_CONFLICT",
                )
            existing_attachments = existing_payload.get("attachments")
            existing_attachment_refs = existing_payload.get("attachment_refs")
            if isinstance(existing_attachments, list):
                attachments_count = len(existing_attachments)
            elif isinstance(existing_attachment_refs, list):
                attachments_count = len(existing_attachment_refs)

        status_result = None
        status_payload: dict[str, Any] | None = None
        if inserted_message and getattr(ticket, "status", None) == "waiting_on_user":
            workflow = TicketWorkflowService(session, repo)
            transition = await workflow.apply_triggered_transition(
                ticket_id=ticket.ticket_id,
                trigger="requester_replied",
                actor_id="system",
                actor_role="system",
                reason="requester_reply",
                source="requester_reply",
                trigger_actor_id=auth_context.actor_id,
                trigger_actor_role=auth_context.actor_role,
                fallback_status="assigned",
            )
            status_result = transition.get("event_result")
            status_payload = transition.get("event_payload") or {}

        if inserted_message:
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_chat",
                event_type="chat_message_sent",
                severity="info",
                result="succeeded",
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                person_id=getattr(ticket, "requester_person_id", None),
                idempotency_key=message_id,
                payload=_requester_chat_message_observer_payload(
                    message_payload=payload,
                    attachments=attachments,
                    status_result=status_result,
                ),
            )
        await session.commit()

    if inserted_message:
        await _push_ticket_event(request, ticket.ticket_id, result, "chat_message", payload)
    if inserted_message and status_result:
        await _push_ticket_event(request, ticket.ticket_id, status_result, "status_changed", status_payload or {})
    return _success({"message_id": message_id, "event_id": event_id, "attachments_count": attachments_count})


@require_auth("user")
async def handle_web_requester_ticket_close(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        repo = TicketEventsRepo(session)
        if getattr(ticket, "status", None) == "closed":
            return _success({"ticket": ticket_to_dict(ticket, visibility="requester")})
        if getattr(ticket, "status", None) != "resolved":
            return _error(
                "ticket can be closed only from resolved",
                status=400,
                error_code="INVALID_TICKET_STATUS",
            )
        actions = requester_ticket_actions(ticket)
        if not actions["can_confirm_solution"]:
            return _error(
                "requester confirmation is not available for this ticket",
                status=409,
                error_code="REQUESTER_TICKET_ACTION_NOT_AVAILABLE",
            )

        from_status = str(getattr(ticket, "status", "") or "")
        workflow = TicketWorkflowService(session, repo)
        try:
            transition = await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=ticket.status,
                to_status="closed",
                actor_id=auth_context.actor_id,
                actor_role="requester",
                reason=_clean(data.get("reason"), max_length=200) or "requester_confirmed_resolution",
                source="requester_workspace",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="WORKFLOW_POLICY_ERROR")

        ticket = await repo.get_ticket(ticket.ticket_id)
        if ticket is not None and _resolution_confirmation_pending(ticket):
            ticket = await _store_resolution_confirmation_state(
                repo,
                ticket,
                pending=False,
                responded_option_id="confirm",
            )
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="requester_closure",
            event_type="closure_confirmed",
            severity="info",
            result="succeeded",
            ticket_id=ticket.ticket_id if ticket is not None else ticket_id,
            device_id=getattr(ticket, "device_id", None),
            person_id=getattr(ticket, "requester_person_id", None),
            payload=_requester_closure_observer_payload(
                from_status=from_status,
                ticket=ticket,
                data=data,
            ),
        )
        await session.commit()

    await _push_ticket_event(
        request,
        ticket.ticket_id if ticket is not None else ticket_id,
        transition.get("event_result"),
        "status_changed",
        transition.get("event_payload") or {},
    )
    return _success({"ticket": ticket_to_dict(ticket, visibility="requester")})


@require_auth("user")
async def handle_web_requester_ticket_feedback(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        actions = requester_ticket_actions(ticket)
        if not actions["can_rate_solution"]:
            return _error(
                "requester feedback is not available for this ticket",
                status=409,
                error_code="REQUESTER_TICKET_ACTION_NOT_AVAILABLE",
            )

        metadata = dict(data.get("metadata")) if isinstance(data.get("metadata"), dict) else {}
        request_metadata_present = bool(metadata)
        metadata["web_actor_id"] = auth_context.actor_id
        data["metadata"] = metadata
        data["ticket_id"] = ticket.ticket_id
        data["source_surface"] = "requester_portal"
        data.pop("visibility", None)
        try:
            result = await TicketFeedbackService(session).submit_feedback(
                data,
                actor_id=str(getattr(ticket, "requester_id", None) or auth_context.actor_id),
                actor_role="requester",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="QUALITY_FEEDBACK_ERROR")
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="requester_closure",
            event_type="feedback_submitted",
            severity="info",
            result="succeeded",
            ticket_id=ticket.ticket_id,
            device_id=getattr(ticket, "device_id", None),
            person_id=getattr(ticket, "requester_person_id", None),
            payload=_requester_feedback_observer_payload(
                data=data,
                result=result,
                request_metadata_present=request_metadata_present,
            ),
        )
        await session.commit()

    return _success(
        {
            "ok": True,
            "feedback_id": result["feedback_id"],
            "message": result.get("message"),
            "reopen_available": bool(result.get("reopen_available")),
        }
    )


@require_auth("user")
async def handle_web_requester_ticket_reopen(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        actions = requester_ticket_actions(ticket)
        if not actions["can_reopen"]:
            return _error(
                "requester reopen is not available for this ticket",
                status=409,
                error_code="REQUESTER_TICKET_ACTION_NOT_AVAILABLE",
            )

        from_status = str(getattr(ticket, "status", "") or "")
        try:
            result = await TicketReopenService(session).reopen_ticket(
                ticket.ticket_id,
                reason_code=str(data.get("reason_code") or ""),
                reason_comment=data.get("reason_comment"),
                linked_feedback_id=data.get("linked_feedback_id"),
                linked_knowledge_item_id=data.get("linked_knowledge_item_id"),
                actor_id=str(getattr(ticket, "requester_id", None) or auth_context.actor_id),
                actor_role="requester",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="QUALITY_REOPEN_ERROR")
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="requester_closure",
            event_type="ticket_reopened",
            severity="info",
            result="succeeded",
            ticket_id=ticket.ticket_id,
            device_id=getattr(ticket, "device_id", None),
            person_id=getattr(ticket, "requester_person_id", None),
            payload=_requester_reopen_observer_payload(
                from_status=from_status,
                data=data,
                result=result,
            ),
        )
        await session.commit()

    return _success(
        {
            "ok": True,
            "ticket_id": result["ticket_id"],
            "ticket_status": result["status"],
            "reopen_id": result["reopen_id"],
            "linked_feedback_id": result.get("linked_feedback_id"),
        }
    )


@require_auth("user")
async def handle_web_requester_ticket_preview(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    try:
        data = await request.json()
    except Exception:
        return _error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _error("JSON body must be an object", status=400)

    supplied_device_id = _clean(data.get("device_id"), max_length=80)
    pack_key = _clean(data.get("form_pack_key"), max_length=120) or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = _clean(data.get("form_pack_version"), max_length=120) or None
    form_key = _clean(data.get("form_key") or data.get("request_template_key"), max_length=120)
    request_template_key = _clean(data.get("request_template_key"), max_length=120)
    form_payload = data.get("form_payload") if isinstance(data.get("form_payload"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        profile_schema = await RequesterProfileSchemaService(session).get_schema()
        try:
            person, binding, device_id, account_mode, _request_context, primary_device_resolution = await _resolve_requester_self_device_context(
                resolver,
                actor_id=auth_context.actor_id,
                supplied_device_id=supplied_device_id,
                state=request.app.get("state"),
            )
        except PermissionError as exc:
            return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")
        completion = resolver.build_profile_completion(person, profile_schema=profile_schema)
        availability_policy = await _resolve_form_availability_policy(
            session,
            pack_key=pack_key,
            pack_version=pack_version,
            form_key=form_key,
            request_template_key=request_template_key,
        )
        if _profile_completion_blocks_for_form(completion, "ticket_preview", availability_policy):
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_profile",
                event_type="profile_incomplete_blocked",
                severity="warning",
                result="blocked",
                person_id=getattr(person, "person_id", None),
                error_code="REQUESTER_PROFILE_INCOMPLETE",
                payload={"action": "ticket_preview", "completion": completion},
            )
            return _profile_incomplete_error(completion)
        if availability_policy.get("contact_required") and not _has_contact_for_emergency(person, form_payload, data):
            return _error(
                "Укажите телефон или другой контакт для связи.",
                status=400,
                error_code="REQUESTER_CONTACT_REQUIRED",
            )
        has_agent_binding = binding is not None
        if (
            form_key
            and not supplied_device_id
            and not has_agent_binding
            and not availability_policy.get("available_without_agent_binding")
            and not _raw_on_behalf_context(data).get("affected_person_id")
        ):
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_preview",
                event_type="ticket_preview_blocked",
                severity="warning",
                result="blocked",
                person_id=getattr(person, "person_id", None),
                error_code="REQUESTER_AGENT_REQUIRED",
                payload={
                    "action": "ticket_preview",
                    "form_key": form_key,
                    "request_template_key": request_template_key,
                    "has_agent_binding": has_agent_binding,
                    "available_without_agent_binding": bool(
                        availability_policy.get("available_without_agent_binding")
                    ),
                },
            )
            return _error(
                "Для этой формы нужно основное устройство. Выберите форму для экстренного обращения или привяжите устройство.",
                status=403,
                error_code="REQUESTER_AGENT_REQUIRED",
            )

        try:
            on_behalf_context = await _authorize_on_behalf_context(
                session,
                auth_context=auth_context,
                creator=_requester_ref_from_resolved_person(person),
                policy=await _resolve_on_behalf_policy(
                    session,
                    pack_key=pack_key,
                    pack_version=pack_version,
                    form_key=form_key,
                    request_template_key=request_template_key,
                ),
                data=data,
            )
        except _OnBehalfRequestError as exc:
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_preview",
                event_type="ticket_preview_blocked",
                severity="warning",
                result="blocked",
                device_id=device_id or None,
                person_id=getattr(person, "person_id", None),
                error_code=exc.error_code,
                payload={
                    "action": "ticket_preview",
                    "form_key": form_key,
                    "request_template_key": request_template_key,
                    "has_on_behalf_request": bool(_raw_on_behalf_context(data).get("affected_person_id")),
                },
            )
            return _error(str(exc), status=exc.status, error_code=exc.error_code)

        preview_payload = dict(data)
        if on_behalf_context:
            preview_payload["ticket_context"] = on_behalf_context
        requester_context = await resolver.build_requester_context(
            actor_id=auth_context.actor_id,
            person=person,
            binding=binding,
            account_mode=account_mode,
            profile_schema=profile_schema,
        )
        context_custom_fields = RequesterIdentityResolver.requester_context_custom_fields(requester_context)
        context_custom_fields["primary_device_resolution"] = primary_device_resolution
        if form_key:
            context_custom_fields.update(
                _manual_triage_custom_fields(
                    availability_policy=availability_policy,
                    no_valid_target=not has_agent_binding and not on_behalf_context,
                )
            )
        client_custom_fields = (
            preview_payload.get("custom_fields")
            if isinstance(preview_payload.get("custom_fields"), dict)
            else {}
        )
        preview_payload["custom_fields"] = {**client_custom_fields, **context_custom_fields}
        preview_payload["requester_context"] = requester_context
        if isinstance(requester_context.get("device"), dict):
            preview_payload["device_metadata"] = dict(requester_context["device"])
        ticket_context_preview = await _build_requester_ticket_context_preview(
            session,
            state=request.app.get("state"),
            person=person,
            actor_id=auth_context.actor_id,
            requester_context=requester_context,
            on_behalf_context=on_behalf_context,
            form={
                "key": form_key or request_template_key,
                "title": form_key or request_template_key,
            }
            if (form_key or request_template_key)
            else {},
            policy_refs={},
        )
        if not _has_catalog_selection(preview_payload):
            response_payload = {
                "ok": True,
                "service": {"code": None, "title": None},
                "offering": {"code": None, "full_code": None, "title": None},
                "request_type_label": "Request",
                "public_status_after_create": "Новое обращение",
                "approval": {"required": False, "text": "Согласование не требуется"},
                "diagnostics": {
                    "required": False,
                    "consent_required": False,
                    "text": "Диагностика не требуется до отправки",
                },
                "next_action": "После отправки обращение попадет в поддержку.",
                "warnings": [],
                "blockers": [],
                "would_create_ticket": False,
                "requester_context": RequesterIdentityResolver.requester_context_preview(requester_context),
            }
            if ticket_context_preview is not None:
                response_payload["ticket_context"] = ticket_context_preview
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_preview",
                event_type="ticket_preview_succeeded",
                severity="info",
                result="previewed",
                device_id=device_id or None,
                person_id=getattr(person, "person_id", None),
                payload={
                    "has_catalog_selection": False,
                    "form_key": form_key,
                    "request_template_key": request_template_key,
                    "account_mode": account_mode,
                },
            )
            return _success(response_payload)
        try:
            preview = await build_requester_service_catalog_preview(session, preview_payload)
        except ServiceCatalogPreviewError as exc:
            return _validation_error(exc.details)
        except ValueError as exc:
            return _validation_error({"preview": str(exc)})
        preview["requester_context"] = RequesterIdentityResolver.requester_context_preview(requester_context)
        if ticket_context_preview is not None:
            preview["ticket_context"] = ticket_context_preview
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="requester_ticket_preview",
            event_type="ticket_preview_succeeded",
            severity="info",
            result="previewed",
            device_id=device_id or None,
            person_id=getattr(person, "person_id", None),
            payload={
                "has_catalog_selection": True,
                "form_key": form_key,
                "request_template_key": request_template_key,
                "account_mode": account_mode,
            },
        )
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="web_form_runtime",
            event_type="form_runtime_preview_succeeded",
            severity="info",
            result="previewed",
            device_id=device_id or None,
            person_id=getattr(person, "person_id", None),
            payload=_web_form_runtime_preview_payload(
                preview_payload,
                preview=preview,
                form_key=form_key,
                request_template_key=request_template_key,
                account_mode=account_mode,
            ),
        )

    return _success(preview)


@require_auth("user")
async def handle_web_requester_ticket_create(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    try:
        data = await request.json()
    except Exception:
        return _error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _error("JSON body must be an object", status=400)

    supplied_device_id = _clean(data.get("device_id"), max_length=80)
    description = _clean(data.get("description"), max_length=5000)
    if not description:
        return _error("description is required", status=400)
    title = _clean(data.get("title"), max_length=300) or "Requester workspace request"
    request_template_key = _clean(data.get("request_template_key"), max_length=120)
    service_code = _clean(data.get("service_code"), max_length=120)
    offering_code = _clean(data.get("offering_code"), max_length=160)
    offering_full_code = _clean(data.get("offering_full_code") or data.get("full_offering_code"), max_length=240)
    form_key = _clean(data.get("form_key") or request_template_key, max_length=120)
    pack_key = _clean(data.get("form_pack_key"), max_length=120) or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = _clean(data.get("form_pack_version"), max_length=120) or None
    form_payload = data.get("form_payload") if isinstance(data.get("form_payload"), dict) else {}
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session, state=request.app.get("state"))
        profile_schema = await RequesterProfileSchemaService(session).get_schema()
        try:
            person, binding, device_id, account_mode, request_context, primary_device_resolution = await _resolve_requester_self_device_context(
                resolver,
                actor_id=auth_context.actor_id,
                supplied_device_id=supplied_device_id,
                state=request.app.get("state"),
            )
        except PermissionError as exc:
            return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")
        completion = resolver.build_profile_completion(person, profile_schema=profile_schema)
        availability_policy = await _resolve_form_availability_policy(
            session,
            pack_key=pack_key,
            pack_version=pack_version,
            form_key=form_key,
            request_template_key=request_template_key,
        )
        if _profile_completion_blocks_for_form(completion, "ticket_create", availability_policy):
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_profile",
                event_type="profile_incomplete_blocked",
                severity="warning",
                result="blocked",
                person_id=getattr(person, "person_id", None),
                error_code="REQUESTER_PROFILE_INCOMPLETE",
                payload={"action": "ticket_create", "completion": completion},
            )
            return _profile_incomplete_error(completion)
        if availability_policy.get("contact_required") and not _has_contact_for_emergency(person, form_payload, data):
            return _error(
                "Укажите телефон или другой контакт для связи.",
                status=400,
                error_code="REQUESTER_CONTACT_REQUIRED",
            )
        has_agent_binding = binding is not None
        if (
            form_key
            and not supplied_device_id
            and not has_agent_binding
            and not availability_policy.get("available_without_agent_binding")
            and not _raw_on_behalf_context(data).get("affected_person_id")
        ):
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_create",
                event_type="ticket_create_blocked",
                severity="warning",
                result="blocked",
                person_id=getattr(person, "person_id", None),
                error_code="REQUESTER_AGENT_REQUIRED",
                payload={
                    "action": "ticket_create",
                    "form_key": form_key,
                    "request_template_key": request_template_key,
                    "has_agent_binding": has_agent_binding,
                    "available_without_agent_binding": bool(
                        availability_policy.get("available_without_agent_binding")
                    ),
                },
            )
            return _error(
                "Для этой формы нужно основное устройство. Выберите форму для экстренного обращения или привяжите устройство.",
                status=403,
                error_code="REQUESTER_AGENT_REQUIRED",
            )

        requester_profile = {
            "full_name": getattr(person, "full_name", None) or getattr(person, "display_name", None) or auth_context.actor_id,
            "email": getattr(person, "email", None) or auth_context.actor_id,
            "phone": getattr(person, "phone", None),
        }
        requester_account = {
            "account_mode": account_mode,
            "person_id": person.person_id if person else None,
            "binding_id": binding.binding_id if binding is not None else None,
            "display_name": getattr(person, "display_name", None),
            "full_name": getattr(person, "full_name", None),
            "email": getattr(person, "email", None),
            "validation": "web_requester_identity_resolved",
        }
        requester_context_snapshot = await resolver.build_requester_context(
            actor_id=auth_context.actor_id,
            person=person,
            binding=binding,
            account_mode=account_mode,
            profile_schema=profile_schema,
        )
        snapshot_profile = (
            requester_context_snapshot.get("profile")
            if isinstance(requester_context_snapshot.get("profile"), dict)
            else {}
        )
        requester_profile["building"] = snapshot_profile.get("building")
        requester_profile["room"] = snapshot_profile.get("room")
        extra_custom_fields: dict[str, Any] = {
            "request_context": request_context,
            "primary_device_resolution": primary_device_resolution,
            **RequesterIdentityResolver.requester_context_custom_fields(requester_context_snapshot),
        }
        on_behalf_context: dict[str, str] | None = None
        if form_key:
            extra_custom_fields.update(
                _manual_triage_custom_fields(
                    availability_policy=availability_policy,
                    no_valid_target=not has_agent_binding and not _raw_on_behalf_context(data).get("affected_person_id"),
                )
            )
        if account_mode == "browser_no_device":
            extra_custom_fields["no_device"] = {
                "created_from": "requester_portal",
                "device_scope": "none",
                "primary_device_resolution": primary_device_resolution,
            }
        template_context: dict[str, Any] = {}
        catalog_process_fields: dict[str, Any] = {}
        ticket_type = _clean(data.get("ticket_type"), max_length=64) or "request"
        normalized_priority = build_default_priority_payload(data)
        catalog_selection = None
        catalog_template_key = request_template_key or form_key
        if service_code or offering_code or offering_full_code or catalog_template_key:
            try:
                catalog_selection = await ServiceCatalogRuntimeResolver(session).resolve_selection(
                    service_code=service_code or None,
                    offering_code=offering_code or None,
                    offering_full_code=offering_full_code or None,
                    request_template_key=catalog_template_key or None,
                    actor_role="requester",
                )
                if catalog_selection.request_template_key:
                    request_template_key = catalog_selection.request_template_key
                    form_key = form_key or request_template_key
            except ServiceCatalogResolutionError as exc:
                return _validation_error(exc.details)
        if form_key:
            try:
                validated_submission = await resolve_create_form_submission(
                    session,
                    pack_key=pack_key,
                    pack_version=pack_version,
                    form_key=form_key,
                    request_template_key=request_template_key,
                    raw_values=form_payload,
                    include_setup_assistance=True,
                )
                if catalog_selection is not None:
                    validated_submission = await ServiceCatalogRuntimeResolver(session).apply_to_validated_submission(
                        validated_submission,
                        catalog_selection,
                    )
                validated_submission = await apply_effective_registry_policies(session, validated_submission)
                extra_custom_fields.update(build_form_custom_fields(validated_submission))
                catalog_process_fields = (
                    validated_submission.get("catalog_fields")
                    if isinstance(validated_submission.get("catalog_fields"), dict)
                    else {}
                )
                diagnostic_consent = normalize_diagnostic_consent_payload(data.get("diagnostic_consent"))
                if diagnostic_consent:
                    extra_custom_fields["diagnostic_consent"] = diagnostic_consent
                ticket_type = str(validated_submission.get("ticket_type") or ticket_type).strip() or ticket_type
                template_context = (
                    validated_submission.get("template_context")
                    if isinstance(validated_submission.get("template_context"), dict)
                    else {}
                )
                if isinstance(template_context.get("service_catalog"), dict):
                    extra_custom_fields["service_catalog"] = template_context["service_catalog"]
                priority_policy = (
                    template_context.get("priority_policy")
                    if isinstance(template_context.get("priority_policy"), dict)
                    else {}
                )
                if priority_policy:
                    normalized_priority = compute_priority_from_policy(
                        priority_policy=priority_policy,
                        submitted_values=validated_submission.get("submitted_values") or {},
                        fallback=_priority_policy_fallback(data),
                    )
            except ValueError as exc:
                details = exc.args[0] if exc.args else "invalid form payload"
                return _validation_error({"form_payload": details})
        policy = template_context.get("on_behalf_policy") if isinstance(template_context.get("on_behalf_policy"), dict) else {}
        if not policy and _raw_on_behalf_context(data).get("affected_person_id"):
            policy = await _resolve_on_behalf_policy(
                session,
                pack_key=pack_key,
                pack_version=pack_version,
                form_key=form_key,
                request_template_key=request_template_key,
            )
        try:
            on_behalf_context = await _authorize_on_behalf_context(
                session,
                auth_context=auth_context,
                creator=_requester_ref_from_resolved_person(person),
                policy=policy,
                data=data,
            )
        except _OnBehalfRequestError as exc:
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_create",
                event_type="ticket_create_blocked",
                severity="warning",
                result="blocked",
                device_id=device_id or None,
                person_id=getattr(person, "person_id", None),
                error_code=exc.error_code,
                payload={
                    "action": "ticket_create",
                    "form_key": form_key,
                    "request_template_key": request_template_key,
                    "has_on_behalf_request": bool(_raw_on_behalf_context(data).get("affected_person_id")),
                },
            )
            return _error(str(exc), status=exc.status, error_code=exc.error_code)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=auth_context.actor_id,
            title=title,
            description=description,
            user_display_name=_clean(data.get("user_display_name"), max_length=300)
            or getattr(person, "display_name", None)
            or auth_context.actor_id,
            requester_profile=requester_profile,
            normalized_priority=normalized_priority,
            initial_message_text=description,
            initial_message_sender_role="user",
            initial_message_from="user",
            include_public_access=True,
            ticket_type=ticket_type,
            category_id=template_context.get("category_id"),
            service_id=template_context.get("service_id"),
            subcategory_id=template_context.get("subcategory_id"),
            sla_policy_id=template_context.get("sla_policy_id"),
            catalog_service_id=catalog_process_fields.get("catalog_service_id"),
            catalog_offering_id=catalog_process_fields.get("catalog_offering_id"),
            service_code=catalog_process_fields.get("service_code"),
            offering_code=catalog_process_fields.get("offering_code"),
            request_type=catalog_process_fields.get("request_type"),
            business_criticality=catalog_process_fields.get("business_criticality"),
            reporting_category=catalog_process_fields.get("reporting_category"),
            service_owner_actor_id=catalog_process_fields.get("service_owner_actor_id"),
            support_group_code=catalog_process_fields.get("support_group_code"),
            extra_custom_fields=extra_custom_fields,
            requester_account=requester_account,
            ticket_context=on_behalf_context,
            state=request.app.get("state"),
        )
        ticket_row = created["ticket"]
        ticket_custom_fields = ticket_row.custom_fields if isinstance(ticket_row.custom_fields, dict) else {}
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="requester_ticket_create",
            event_type="ticket_create_succeeded",
            severity="info",
            result="created",
            ticket_id=created["ticket_id"],
            device_id=getattr(ticket_row, "device_id", None) or device_id,
            person_id=getattr(person, "person_id", None),
            payload={
                "request_context": request_context,
                "account_mode": account_mode,
                "form_key": form_key,
                "request_template_key": request_template_key,
                "has_ticket_context": isinstance(ticket_custom_fields.get("ticket_context"), dict),
                "diagnostic_target_source": ticket_custom_fields.get("diagnostic_target_source"),
            },
        )
        target_observer = _diagnostic_target_observer_payload(ticket_row, ticket_custom_fields)
        if target_observer is not None:
            await _write_requester_web_observer_event(
                session,
                request=request,
                auth_context=auth_context,
                source="requester_ticket_create",
                event_type=target_observer["event_type"],
                severity="warning",
                result="skipped",
                ticket_id=created["ticket_id"],
                device_id=target_observer["device_id"],
                person_id=getattr(person, "person_id", None),
                error_code=target_observer["error_code"],
                payload=target_observer["payload"],
            )
        await _write_requester_web_observer_event(
            session,
            request=request,
            auth_context=auth_context,
            source="web_form_runtime",
            event_type="form_runtime_create_succeeded",
            severity="info",
            result="created",
            ticket_id=created["ticket_id"],
            device_id=getattr(ticket_row, "device_id", None) or device_id,
            person_id=getattr(person, "person_id", None),
            payload=_web_form_runtime_create_payload(
                data,
                ticket=ticket_row,
                ticket_custom_fields=ticket_custom_fields,
                form_key=form_key,
                request_template_key=request_template_key,
                account_mode=account_mode,
            ),
        )
        await session.commit()
        ticket = ticket_to_dict(created["ticket"], visibility="requester")

    return _success(
        {
            "ticket": ticket,
            "ticket_id": created["ticket_id"],
            "ticket_code": ticket.get("ticket_code"),
            "public_access_code": created.get("public_access_code"),
            "public_access_url": ticket.get("public_access_url"),
        }
    )
