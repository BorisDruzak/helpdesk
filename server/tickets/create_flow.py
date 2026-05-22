"""Shared ticket creation flow for HTTP, agent WS, and legacy chat entrypoints."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from loguru import logger

from app.repos import DevicesRepo, TicketEventsRepo
from tickets.assignment_service import (
    MAX_ACTIVE_TICKETS_PER_OPERATOR,
    TicketAssignmentError,
    TicketAssignmentService,
)
from tickets.ola_service import start_ola_for_ticket
from tickets.public_access import (
    build_public_access_message,
    generate_public_access_code,
    set_public_access_code,
)
from tickets.form_catalog import attach_request_template_computed_snapshot
from tickets.routing_service import TicketRoutingService
from tickets.sla_service import TicketSlaService
from tickets.statuses import merge_requester_custom_fields, normalize_ticket_priority_inputs
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.workflow_service import TicketWorkflowService
from playbooks.form_triggers import start_ticket_created_playbooks
from utils import new_ticket_id


def build_default_priority_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    urgency = data.get("urgency")
    importance = data.get("importance")
    urgency_reason = str(data.get("urgency_reason") or "").strip()
    importance_reason = str(data.get("importance_reason") or "").strip()
    if urgency is None or importance is None:
        urgency = False
        importance = False
    if not urgency_reason:
        urgency_reason = "Не указано при создании"
    if not importance_reason:
        importance_reason = "Не указано при создании"
    return normalize_ticket_priority_inputs(urgency, importance, urgency_reason, importance_reason)


def build_agent_raise_description(
    *,
    reason: str,
    severity: str,
    context: Optional[dict[str, Any]] = None,
) -> str:
    parts = [
        "Agent requested support.",
        f"Reason: {reason or 'agent_initiated'}.",
        f"Severity: {severity or 'warning'}.",
    ]
    if context:
        try:
            context_blob = json.dumps(context, ensure_ascii=False, sort_keys=True)
        except TypeError:
            context_blob = str(context)
        if context_blob:
            parts.append(f"Context: {context_blob}")
    return " ".join(part for part in parts if part).strip()


async def _auto_assign_if_possible(session: Any, ticket_repo: TicketEventsRepo, ticket: Any) -> Any:
    if getattr(ticket, "assignee_id", None):
        return ticket
    assignment_service = TicketAssignmentService(ticket_repo)
    workflow = TicketWorkflowService(session, ticket_repo)
    try:
        selection = await assignment_service.resolve_assignee(
            ticket,
            requested_assignee_id=None,
            auto_assign=True,
        )
        assignee_id = selection["assignee_id"]
        if assignee_id:
            await assignment_service.assign_ticket(
                ticket.ticket_id,
                ticket.device_id,
                assignee_id,
                actor_id="system",
                actor_role="system",
                reason="auto_assign_on_create",
                comment="",
                old_assignee=getattr(ticket, "assignee_id", None),
                auto_assigned=True,
                active_count=selection["active_count"],
                limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                db_session=session,
                close_ola=True,
            )
            await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=getattr(ticket, "status", "new") or "new",
                to_status="assigned",
                actor_id="system",
                actor_role="system",
                reason="auto_assign_on_create",
                source="system",
            )
            ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    except TicketAssignmentError:
        return ticket
    return ticket


def _approval_waiting_status(policy: dict[str, Any]) -> str:
    statuses = policy.get("statuses") if isinstance(policy.get("statuses"), dict) else {}
    return str(statuses.get("waiting_status") or "waiting_on_approval").strip() or "waiting_on_approval"


async def _enter_initial_approval_wait_if_required(session: Any, ticket_repo: TicketEventsRepo, ticket: Any) -> Any:
    if not ticket or getattr(ticket, "status", None) != "new":
        return ticket
    approval_policy = await resolve_effective_ticket_policy(session, ticket, "approval")
    if not approval_policy or not approval_policy.get("required"):
        return ticket
    waiting_status = _approval_waiting_status(approval_policy)
    workflow = TicketWorkflowService(session, ticket_repo)
    await workflow.apply_status_transition(
        ticket_id=ticket.ticket_id,
        from_status="new",
        to_status=waiting_status,
        actor_id="system",
        actor_role="system",
        reason="approval_required_on_create",
        source="system",
    )
    return await ticket_repo.get_ticket(ticket.ticket_id)


async def apply_create_side_effects(session: Any, ticket_repo: TicketEventsRepo, ticket: Any) -> Any:
    devices_repo = DevicesRepo(session)
    routing = TicketRoutingService(session, ticket_repo, devices_repo)
    sla = TicketSlaService(session, ticket_repo)

    async def add_routing_event(ticket_id: str, device_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type=event_type,
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )

    try:
        await routing.apply_routing(ticket.ticket_id, ticket.device_id, add_events_fn=add_routing_event)
    except Exception as exc:
        logger.warning(f"[create] routing failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    try:
        await sla.start_sla(ticket)
    except Exception as exc:
        logger.warning(f"[create] sla failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    try:
        await start_ola_for_ticket(session, ticket, trigger="ticket_created")
    except Exception as exc:
        logger.warning(f"[create] ola failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    ticket = await _enter_initial_approval_wait_if_required(session, ticket_repo, ticket)
    if ticket and getattr(ticket, "status", None) != "new":
        return ticket
    ticket = await _auto_assign_if_possible(session, ticket_repo, ticket)
    if (
        ticket
        and getattr(ticket, "queue_id", None)
        and not getattr(ticket, "assignee_id", None)
        and getattr(ticket, "status", None) == "new"
    ):
        workflow = TicketWorkflowService(session, ticket_repo)
        await workflow.apply_status_transition(
            ticket_id=ticket.ticket_id,
            from_status="new",
            to_status="queued",
            actor_id="system",
            actor_role="system",
            reason="routed_to_queue",
            source="system",
        )
        ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    return ticket


async def create_ticket_with_side_effects(
    session: Any,
    *,
    device_id: str,
    requester_id: str,
    title: str,
    description: str,
    user_display_name: str,
    requester_profile: Optional[dict[str, Any]] = None,
    normalized_priority: Optional[Dict[str, Any]] = None,
    initial_message_text: Optional[str] = None,
    initial_message_sender_role: str = "user",
    initial_message_from: Optional[str] = None,
    include_public_access: bool = True,
    ticket_type: str = "request",
    category_id: Optional[int] = None,
    service_id: Optional[int] = None,
    subcategory_id: Optional[int] = None,
    sla_policy_id: Optional[int] = None,
    catalog_service_id: Optional[str] = None,
    catalog_offering_id: Optional[str] = None,
    service_code: Optional[str] = None,
    offering_code: Optional[str] = None,
    request_type: Optional[str] = None,
    business_criticality: Optional[str] = None,
    reporting_category: Optional[str] = None,
    service_owner_actor_id: Optional[str] = None,
    support_group_code: Optional[str] = None,
    extra_custom_fields: Optional[dict[str, Any]] = None,
    state: Any | None = None,
) -> Dict[str, Any]:
    ticket_repo = TicketEventsRepo(session)
    ticket_id = new_ticket_id()
    requester_person_id = None
    requester_binding_id = None
    requester_registration_status = "unregistered"
    requester_registration_context: dict[str, Any] = {"status": "unregistered"}
    try:
        from registry.registration_service import RegistrationService

        registration_service = RegistrationService(session)
        registration_status = await registration_service.get_device_registration_status(device_id)
        active_binding = registration_status.get("active_binding") if isinstance(registration_status, dict) else None
        if isinstance(active_binding, dict) and active_binding.get("binding_id"):
            requester_person_id = active_binding.get("person_id")
            requester_binding_id = active_binding.get("binding_id")
            requester_registration_status = "admin_confirmed"
        else:
            requester_registration_status = str((registration_status or {}).get("status") or "unregistered")
        requester_registration_context = registration_status if isinstance(registration_status, dict) else requester_registration_context
    except Exception as exc:
        logger.warning(f"[create] registration requester context failed ticket_id={ticket_id} err={exc}")

    ticket = await ticket_repo.create_ticket(
        ticket_id=ticket_id,
        device_id=device_id,
        title=title,
        description=description,
        status="new",
        requester_id=requester_id,
        ticket_type=ticket_type,
        category_id=category_id,
        service_id=service_id,
        subcategory_id=subcategory_id,
        sla_policy_id=sla_policy_id,
        catalog_service_id=catalog_service_id,
        catalog_offering_id=catalog_offering_id,
        service_code=service_code,
        offering_code=offering_code,
        request_type=request_type,
        business_criticality=business_criticality,
        reporting_category=reporting_category,
        service_owner_actor_id=service_owner_actor_id,
        support_group_code=support_group_code,
        requester_person_id=requester_person_id,
        requester_binding_id=requester_binding_id,
        requester_registration_status=requester_registration_status,
    )

    normalized_priority = normalized_priority or build_default_priority_payload({})
    priority_class = normalized_priority.get("effective_priority") or normalized_priority.get("priority_class") or "P3"
    priority_decision = {
        "impact": normalized_priority.get("impact"),
        "urgency": normalized_priority.get("urgency"),
        "importance": normalized_priority.get("importance"),
        "computed_priority": normalized_priority.get("computed_priority") or priority_class,
        "manual_priority": normalized_priority.get("manual_priority"),
        "effective_priority": priority_class,
        "priority_class": priority_class,
        "legacy_priority": normalized_priority.get("legacy_priority"),
        "priority_source": normalized_priority.get("priority_source") or "system",
        "priority_reason": normalized_priority.get("priority_reason")
        or normalized_priority.get("urgency_reason")
        or "Не указано при создании",
        "manual_priority_reason": normalized_priority.get("manual_priority_reason"),
        "applied_modifiers": normalized_priority.get("applied_modifiers") or [],
        "manual_override_event": normalized_priority.get("manual_override_event"),
        "priority_explanation": normalized_priority.get("priority_explanation") or {},
    }
    custom_fields = merge_requester_custom_fields(
        getattr(ticket, "custom_fields", None),
        user_display_name=user_display_name,
        requester_profile=requester_profile or {},
        priority_class=priority_class,
    )
    custom_fields["priority_decision"] = priority_decision
    if extra_custom_fields:
        custom_fields.update(extra_custom_fields)
    custom_fields["requester_registration"] = requester_registration_context

    try:
        from registry.service import RegistryIngestionService

        registry_result = await RegistryIngestionService(session).ingest_requester_profile(
            device_id=device_id,
            requester_id=requester_id,
            display_name=user_display_name,
            profile=requester_profile or {},
        )
        custom_fields["registry_context"] = {
            "person_id": registry_result.person_id,
            "asset_id": registry_result.asset_id,
            "location_id": registry_result.location_id,
            "department_id": registry_result.department_id,
            "source": "agent_profile",
        }
    except Exception as exc:
        logger.warning(f"[create] registry profile ingest failed ticket_id={ticket_id} err={exc}")

    public_access_code: Optional[str] = None
    if include_public_access:
        public_access_code = generate_public_access_code()
        custom_fields = set_public_access_code(custom_fields, public_access_code)

    await ticket_repo.update_ticket(
        ticket_id,
        impact=normalized_priority.get("impact"),
        urgency=normalized_priority.get("urgency"),
        importance=normalized_priority.get("importance"),
        urgency_reason=normalized_priority["urgency_reason"],
        importance_reason=normalized_priority["importance_reason"],
        priority=normalized_priority["legacy_priority"],
        custom_fields=custom_fields,
    )
    if priority_decision.get("manual_override_event"):
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="priority_overridden",
            payload={
                "priority_decision": priority_decision,
                "override": priority_decision["manual_override_event"],
            },
            trace_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
        )
    ticket = await ticket_repo.get_ticket(ticket_id)
    ticket = await apply_create_side_effects(session, ticket_repo, ticket)
    if ticket is not None:
        current_custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
        queue = await ticket_repo.get_queue(getattr(ticket, "queue_id", None)) if getattr(ticket, "queue_id", None) is not None else None
        computed_custom_fields = attach_request_template_computed_snapshot(
            current_custom_fields,
            priority_decision=current_custom_fields.get("priority_decision"),
            routing_decision=current_custom_fields.get("routing_decision"),
            queue=queue,
        )
        if computed_custom_fields != current_custom_fields:
            await ticket_repo.update_ticket(ticket_id, custom_fields=computed_custom_fields)
            ticket = await ticket_repo.get_ticket(ticket_id)
            custom_fields = computed_custom_fields

    initial_message_id: Optional[str] = None
    initial_message_text = (initial_message_text if initial_message_text is not None else description).strip()
    if initial_message_text:
        initial_message_id = str(uuid.uuid4())
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": initial_message_id,
                "sender_role": initial_message_sender_role,
                "from": initial_message_from or initial_message_sender_role,
                "is_initial": True,
                "text": initial_message_text,
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id=initial_message_id,
        )

    if public_access_code:
        access_payload = build_public_access_message(public_access_code, ticket_id)
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload=access_payload,
            trace_id=str(uuid.uuid4()),
            event_id=access_payload["message_id"],
        )

    try:
        await start_ticket_created_playbooks(
            session=session,
            state=state,
            ticket=ticket,
            custom_fields=custom_fields,
        )
    except Exception as exc:
        logger.warning(f"[create] playbook form triggers failed ticket_id={ticket_id} err={exc}")

    ticket = await ticket_repo.get_ticket(ticket_id)
    return {
        "ticket": ticket,
        "ticket_id": ticket_id,
        "initial_message_id": initial_message_id,
        "public_access_code": public_access_code,
    }
