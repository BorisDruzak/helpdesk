from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from sqlalchemy import func, or_, select

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.db.models import RegistryDepartment, RegistryLocation, RegistryPerson
from app.repos import ArtifactsRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import require_auth
from consent.service import ConsentAccessError, UserConsentService, serialize_user_consent
from knowledge.attempts import attach_knowledge_attempts, sanitize_knowledge_attempts
from knowledge.feedback_service import KnowledgeFeedbackService
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
from tickets.diagnostic_policy import normalize_diagnostic_consent_payload
from tickets.form_catalog import DEFAULT_TICKET_FORM_PACK_KEY, build_form_custom_fields, resolve_ticket_form_pack
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies
from tickets.priority_policy import compute_priority_from_policy
from tickets.public_access import verify_public_access_code
from tickets.request_template_submission import resolve_create_form_submission
from tickets.service_catalog_preview import ServiceCatalogPreviewError, build_requester_service_catalog_preview
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver
from tickets.statuses import enrich_chat_payload_with_requester_name
from tickets.workflow_service import TicketWorkflowService

_ON_BEHALF_EXCLUDED_PERSON_STATUSES = frozenset({"archived", "deleted", "disabled", "inactive", "merged"})
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


def _metadata_value(person: RegistryPerson, *keys: str) -> str:
    metadata = person.metadata_json if isinstance(person.metadata_json, dict) else {}
    for key in keys:
        value = _clean(metadata.get(key), max_length=120)
        if value:
            return value
    return ""


def _person_selectable_for_on_behalf(person: RegistryPerson | None) -> bool:
    if person is None:
        return False
    status = str(getattr(person, "status", "") or "active").strip().lower()
    return status not in _ON_BEHALF_EXCLUDED_PERSON_STATUSES


def _on_behalf_scope_allows(
    *,
    creator: RegistryPerson,
    affected: RegistryPerson,
    scope: str,
) -> bool:
    if affected.person_id == creator.person_id:
        return True
    if scope == "any_employee":
        return True
    if scope in {"same_department", "same_department_or_privileged"}:
        return bool(creator.department_id and creator.department_id == affected.department_id)
    if scope == "direct_reports":
        manager_id = _metadata_value(affected, "manager_person_id", "manager_id", "reports_to_person_id")
        return bool(manager_id and manager_id == creator.person_id)
    if scope in {"self_only", "privileged_only", "exact_search_only"}:
        return False
    return False


def _person_matches_exact_lookup(person: RegistryPerson, lookup: str) -> bool:
    normalized = lookup.strip().lower()
    if not normalized:
        return False
    candidates = [
        getattr(person, "display_name", None),
        getattr(person, "full_name", None),
        getattr(person, "email", None),
    ]
    return any(str(candidate or "").strip().lower() == normalized for candidate in candidates)


async def _authorize_on_behalf_context(
    session,
    *,
    creator: RegistryPerson | None,
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
    if affected_person_id == creator.person_id:
        return None
    if not policy.get("allowed"):
        raise _OnBehalfRequestError(
            "On-behalf ticket creation is not allowed for this form",
            status=403,
            error_code="ON_BEHALF_NOT_ALLOWED",
        )
    reason = raw_context.get("on_behalf_reason", "")
    if policy.get("reason_required") and not reason:
        raise _OnBehalfRequestError(
            "On-behalf reason is required",
            status=400,
            error_code="ON_BEHALF_REASON_REQUIRED",
        )

    affected = await session.get(RegistryPerson, affected_person_id)
    if not _person_selectable_for_on_behalf(affected):
        raise _OnBehalfRequestError(
            "Affected person is outside the allowed scope",
            status=403,
            error_code="ON_BEHALF_SCOPE_DENIED",
        )
    scope = _clean(policy.get("allowed_scope"), max_length=80) or "same_department_or_privileged"
    if scope == "exact_search_only":
        allowed = _person_matches_exact_lookup(affected, raw_context.get("affected_person_lookup", ""))
    else:
        allowed = _on_behalf_scope_allows(creator=creator, affected=affected, scope=scope)
    if not allowed:
        raise _OnBehalfRequestError(
            "Affected person is outside the allowed scope",
            status=403,
            error_code="ON_BEHALF_SCOPE_DENIED",
        )
    context = {"affected_person_id": affected.person_id}
    if reason:
        context["on_behalf_reason"] = reason
    if raw_context.get("affected_person_lookup"):
        context["affected_person_lookup"] = raw_context["affected_person_lookup"]
    return context


async def _serialize_on_behalf_person(session, person: RegistryPerson, *, state: Any | None = None) -> dict[str, Any]:
    department = await session.get(RegistryDepartment, person.department_id) if person.department_id else None
    location = await session.get(RegistryLocation, person.location_id) if person.location_id else None
    resolved = await PrimaryAgentResolver(session, state=state).resolve_for_person(person.person_id)
    primary_status = "available" if resolved.get("resolved") else "missing"
    if not resolved.get("resolved") and resolved.get("reason_code") == "ambiguous_primary_device":
        primary_status = "ambiguous"
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "full_name": person.full_name,
        "email": person.email,
        "department": {
            "id": person.department_id,
            "name": getattr(department, "name", None),
        },
        "location": {
            "id": person.location_id,
            "display_name": getattr(location, "display_name", None),
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
        payload = await RequesterIdentityResolver(session).build_bootstrap(actor_id=auth_context.actor_id)
    return _success(payload)


@require_auth("user")
async def handle_web_requester_devices(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        devices = await resolver.list_allowed_devices(person.person_id if person else None)
    return _success({"devices": devices, "count": len(devices)})


@require_auth("user")
async def handle_web_requester_profile(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        payload = await RequesterIdentityResolver(session).build_profile(actor_id=auth_context.actor_id)
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
        resolver = RequesterIdentityResolver(session)
        creator = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        if creator is None:
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
        if not policy.get("allowed"):
            return _success({"people": []})

        scope = _clean(policy.get("allowed_scope"), max_length=80) or "same_department_or_privileged"
        lowered_query = query.lower()
        stmt = select(RegistryPerson).where(
            ~RegistryPerson.status.in_(sorted(_ON_BEHALF_EXCLUDED_PERSON_STATUSES)),
            RegistryPerson.person_id != creator.person_id,
        )
        if scope == "exact_search_only":
            stmt = stmt.where(
                or_(
                    func.lower(RegistryPerson.display_name) == lowered_query,
                    func.lower(RegistryPerson.full_name) == lowered_query,
                    func.lower(RegistryPerson.email) == lowered_query,
                )
            )
        else:
            pattern = f"%{lowered_query}%"
            stmt = stmt.where(
                or_(
                    func.lower(RegistryPerson.display_name).like(pattern),
                    func.lower(RegistryPerson.full_name).like(pattern),
                    func.lower(RegistryPerson.email).like(pattern),
                )
            )
        stmt = stmt.order_by(RegistryPerson.display_name.asc()).limit(20)
        result = await session.execute(stmt)
        matched_people = result.scalars().all()
        scoped_people = (
            matched_people[:10]
            if scope == "exact_search_only"
            else [
                person
                for person in matched_people
                if _on_behalf_scope_allows(creator=creator, affected=person, scope=scope)
            ][:10]
        )
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
        resolver = RequesterIdentityResolver(session)
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
            payload = await RequesterIdentityResolver(session).get_device_detail(
                actor_id=auth_context.actor_id,
                device_id=device_id,
            )
        except PermissionError:
            return _error("device not found", status=404, error_code="NOT_FOUND")
    return _success(payload)


@require_auth("user")
async def handle_web_requester_tickets(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    limit = int(request.query.get("limit") or 100)
    async with get_session() as session:
        tickets = await RequesterIdentityResolver(session).list_tickets(actor_id=auth_context.actor_id, limit=limit)
        payload = [ticket_to_dict(ticket, visibility="requester") for ticket in tickets]
    return _success({"tickets": payload, "count": len(payload)})


@require_auth("user")
async def handle_web_requester_ticket_detail(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    async with get_session() as session:
        ticket = await RequesterIdentityResolver(session).get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
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
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        items = await UserConsentService(session).list_for_requester(
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
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        row = await UserConsentService(session).get_for_requester(
            consent_id=consent_id,
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
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        try:
            row = await UserConsentService(session, state=request.app.get("state")).decide_from_browser(
                consent_id=consent_id,
                decision=decision,
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
        resolver = RequesterIdentityResolver(session)
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

        await repo.update_ticket(
            ticket.ticket_id,
            requester_id=auth_context.actor_id,
            requester_person_id=person.person_id,
            custom_fields=custom_fields,
        )
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
        ticket = await repo.get_ticket(ticket.ticket_id)

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

    message_id = _clean(data.get("message_id"), max_length=120) or str(uuid.uuid4())
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

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

        status_result = None
        status_payload: dict[str, Any] | None = None
        if getattr(ticket, "status", None) == "waiting_on_user":
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

        await session.commit()

    await _push_ticket_event(request, ticket_id, result, "chat_message", payload)
    if status_result:
        await _push_ticket_event(request, ticket_id, status_result, "status_changed", status_payload or {})
    return _success({"message_id": message_id, "event_id": result[0] if result else None, "attachments_count": len(attachments)})


@require_auth("user")
async def handle_web_requester_ticket_close(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
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
        await session.commit()

    await _push_ticket_event(
        request,
        ticket_id,
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
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
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
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

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

    device_id = _clean(data.get("device_id"), max_length=80)
    pack_key = _clean(data.get("form_pack_key"), max_length=120) or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = _clean(data.get("form_pack_version"), max_length=120) or None
    form_key = _clean(data.get("form_key") or data.get("request_template_key"), max_length=120)
    request_template_key = _clean(data.get("request_template_key"), max_length=120)
    form_payload = data.get("form_payload") if isinstance(data.get("form_payload"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        profile_schema = await RequesterProfileSchemaService(session).get_schema()
        binding = None
        if device_id:
            try:
                person, binding = await resolver.require_owned_device(actor_id=auth_context.actor_id, device_id=device_id)
            except PermissionError as exc:
                return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")
        else:
            person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        completion = resolver.build_profile_completion(person, profile_schema=profile_schema)
        availability_policy = await _resolve_form_availability_policy(
            session,
            pack_key=pack_key,
            pack_version=pack_version,
            form_key=form_key,
            request_template_key=request_template_key,
        )
        if _profile_completion_blocks_for_form(completion, "ticket_preview", availability_policy):
            return _profile_incomplete_error(completion)
        if availability_policy.get("contact_required") and not _has_contact_for_emergency(person, form_payload, data):
            return _error(
                "Укажите телефон или другой контакт для связи.",
                status=400,
                error_code="REQUESTER_CONTACT_REQUIRED",
            )
        has_agent_binding = bool(binding)
        if not has_agent_binding and person is not None:
            has_agent_binding = bool(await resolver.list_allowed_devices(person.person_id))
        if (
            form_key
            and not device_id
            and not has_agent_binding
            and not availability_policy.get("available_without_agent_binding")
            and not _raw_on_behalf_context(data).get("affected_person_id")
        ):
            return _error(
                "Для этой формы нужно основное устройство. Выберите форму для экстренного обращения или привяжите устройство.",
                status=403,
                error_code="REQUESTER_AGENT_REQUIRED",
            )

        try:
            on_behalf_context = await _authorize_on_behalf_context(
                session,
                creator=person,
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
            return _error(str(exc), status=exc.status, error_code=exc.error_code)

        preview_payload = dict(data)
        if on_behalf_context:
            preview_payload["ticket_context"] = on_behalf_context
        account_mode = "confirmed_binding" if binding is not None else "browser_no_device"
        requester_context = await resolver.build_requester_context(
            actor_id=auth_context.actor_id,
            person=person,
            binding=binding,
            account_mode=account_mode,
        )
        context_custom_fields = RequesterIdentityResolver.requester_context_custom_fields(requester_context)
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
        if not _has_catalog_selection(preview_payload):
            return _success(
                {
                    "ok": True,
                    "service": {"code": None, "title": None},
                    "offering": {"code": None, "full_code": None, "title": None},
                    "request_type_label": "Request",
                    "public_status_after_create": "Новая заявка",
                    "approval": {"required": False, "text": "Согласование не требуется"},
                    "diagnostics": {
                        "required": False,
                        "consent_required": False,
                        "text": "Диагностика не требуется до отправки",
                    },
                    "next_action": "После отправки заявка попадет в поддержку.",
                    "warnings": [],
                    "blockers": [],
                    "would_create_ticket": False,
                    "requester_context": RequesterIdentityResolver.requester_context_preview(requester_context),
                }
            )
        try:
            preview = await build_requester_service_catalog_preview(session, preview_payload)
        except ServiceCatalogPreviewError as exc:
            return _validation_error(exc.details)
        except ValueError as exc:
            return _validation_error({"preview": str(exc)})
        preview["requester_context"] = RequesterIdentityResolver.requester_context_preview(requester_context)

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
    knowledge_attempts = sanitize_knowledge_attempts(data.get("knowledge_attempts"), surface="requester_portal")

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        profile_schema = await RequesterProfileSchemaService(session).get_schema()
        binding = None
        if supplied_device_id:
            try:
                person, binding = await resolver.require_owned_device(actor_id=auth_context.actor_id, device_id=supplied_device_id)
            except PermissionError as exc:
                return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")
            device_id = supplied_device_id
            account_mode = "confirmed_binding"
            request_context = "authenticated_requester_workspace"
        else:
            person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
            device_id = str(uuid.uuid4())
            account_mode = "browser_no_device"
            request_context = "no_device"
        completion = resolver.build_profile_completion(person, profile_schema=profile_schema)
        availability_policy = await _resolve_form_availability_policy(
            session,
            pack_key=pack_key,
            pack_version=pack_version,
            form_key=form_key,
            request_template_key=request_template_key,
        )
        if _profile_completion_blocks_for_form(completion, "ticket_create", availability_policy):
            return _profile_incomplete_error(completion)
        if availability_policy.get("contact_required") and not _has_contact_for_emergency(person, form_payload, data):
            return _error(
                "Укажите телефон или другой контакт для связи.",
                status=400,
                error_code="REQUESTER_CONTACT_REQUIRED",
            )
        has_agent_binding = bool(binding)
        if not has_agent_binding and person is not None:
            has_agent_binding = bool(await resolver.list_allowed_devices(person.person_id))
        if (
            form_key
            and not supplied_device_id
            and not has_agent_binding
            and not availability_policy.get("available_without_agent_binding")
            and not _raw_on_behalf_context(data).get("affected_person_id")
        ):
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
                "placeholder_device_id": device_id,
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
                creator=person,
                policy=policy,
                data=data,
            )
        except _OnBehalfRequestError as exc:
            return _error(str(exc), status=exc.status, error_code=exc.error_code)
        extra_custom_fields = attach_knowledge_attempts(extra_custom_fields, knowledge_attempts)
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
        if knowledge_attempts:
            ticket_row = created["ticket"]
            await KnowledgeFeedbackService(session).record_event(
                {
                    "event_type": "ticket_created_after_view",
                    "ticket_id": created["ticket_id"],
                    "service_code": service_code or getattr(ticket_row, "service_code", None),
                    "offering_code": offering_full_code or offering_code or getattr(ticket_row, "offering_code", None),
                    "surface": "requester_portal",
                    "metadata": {"knowledge_attempts": knowledge_attempts},
                },
                actor_role="requester",
                actor_id=auth_context.actor_id,
            )
        await session.commit()
        ticket = ticket_to_dict(created["ticket"], visibility="requester")

    return _success(
        {
            "ticket": ticket,
            "ticket_id": created["ticket_id"],
            "public_access_code": created.get("public_access_code"),
            "public_access_url": ticket.get("public_access_url"),
        }
    )
