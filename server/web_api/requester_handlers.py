from __future__ import annotations

import uuid
from typing import Any

from aiohttp import web

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import require_auth
from knowledge.attempts import attach_knowledge_attempts, sanitize_knowledge_attempts
from knowledge.feedback_service import KnowledgeFeedbackService
from quality.feedback_service import TicketFeedbackService
from quality.reopen_service import TicketReopenService
from requester.identity_service import RequesterIdentityResolver
from tickets.handlers import (
    _event_visible_to_requester,
    _push_ticket_event,
    _resolution_confirmation_pending,
    _serialize_event_for_requester,
    _serialize_message_for_requester,
    _store_resolution_confirmation_state,
)
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects
from tickets.diagnostic_policy import normalize_diagnostic_consent_payload
from tickets.form_catalog import DEFAULT_TICKET_FORM_PACK_KEY, build_form_custom_fields
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies
from tickets.priority_policy import compute_priority_from_policy
from tickets.request_template_submission import resolve_create_form_submission
from tickets.service_catalog_preview import ServiceCatalogPreviewError, build_requester_service_catalog_preview
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver
from tickets.statuses import enrich_chat_payload_with_requester_name
from tickets.workflow_service import TicketWorkflowService


def _success(data: dict[str, Any]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _error(message: str, *, status: int = 400, error_code: str = "VALIDATION_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": error_code}, status=status)


def _validation_error(details: dict[str, Any]) -> web.Response:
    return web.json_response(
        {"status": "error", "error": "validation_error", "error_code": "VALIDATION_ERROR", "details": details},
        status=400,
    )


def _clean(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


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
    if not text:
        return _error("text is required", status=400)

    message_id = _clean(data.get("message_id"), max_length=120) or str(uuid.uuid4())
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

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
    return _success({"message_id": message_id, "event_id": result[0] if result else None})


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
    if not device_id:
        return _error("device_id is required", status=400)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        try:
            person, binding = await resolver.require_owned_device(actor_id=auth_context.actor_id, device_id=device_id)
        except PermissionError as exc:
            return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")

        preview_payload = dict(data)
        requester_context = preview_payload.get("requester_context") if isinstance(preview_payload.get("requester_context"), dict) else {}
        requester_context = dict(requester_context)
        requester_context.setdefault(
            "requester_profile",
            {
                "full_name": getattr(person, "full_name", None) or getattr(person, "display_name", None) or auth_context.actor_id,
                "email": getattr(person, "email", None) or auth_context.actor_id,
                "phone": getattr(person, "phone", None),
            },
        )
        requester_context.setdefault(
            "requester_account",
            {
                "account_mode": "confirmed_binding",
                "person_id": person.person_id if person else None,
                "binding_id": binding.binding_id,
                "validation": "web_requester_identity_resolved",
            },
        )
        preview_payload["requester_context"] = requester_context
        try:
            preview = await build_requester_service_catalog_preview(session, preview_payload)
        except ServiceCatalogPreviewError as exc:
            return _validation_error(exc.details)
        except ValueError as exc:
            return _validation_error({"preview": str(exc)})

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

    device_id = _clean(data.get("device_id"), max_length=80)
    if not device_id:
        return _error("device_id is required", status=400)
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
        try:
            person, binding = await resolver.require_owned_device(actor_id=auth_context.actor_id, device_id=device_id)
        except PermissionError as exc:
            return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")

        requester_profile = {
            "full_name": getattr(person, "full_name", None) or getattr(person, "display_name", None) or auth_context.actor_id,
            "email": getattr(person, "email", None) or auth_context.actor_id,
            "phone": getattr(person, "phone", None),
        }
        requester_account = {
            "account_mode": "confirmed_binding",
            "person_id": person.person_id if person else None,
            "binding_id": binding.binding_id,
            "display_name": getattr(person, "display_name", None),
            "full_name": getattr(person, "full_name", None),
            "email": getattr(person, "email", None),
            "validation": "web_requester_identity_resolved",
        }
        extra_custom_fields: dict[str, Any] = {"request_context": "authenticated_requester_workspace"}
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
