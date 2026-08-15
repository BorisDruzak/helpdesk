"""Shared ticket creation flow for HTTP, agent WS, and legacy chat entrypoints."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from loguru import logger

from app.repos import DevicesRepo, TicketEventsRepo
from domain_ports import (
    AccountStatusProjection,
    DeviceRef,
    DomainPortContainer,
    RegistryPort,
    RegistryUnavailable,
)
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
from tickets.ticket_context import TicketContextBuilder, ticket_context_resolved_event_payload
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


def _safe_account_payload(account: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "account_session_id",
        "account_mode",
        "person_id",
        "binding_id",
        "display_name",
        "full_name",
        "login",
        "email",
        "phone",
        "reason",
        "session_id",
        "verification_status",
        "verification_method",
        "validation",
        "other_account",
        "base_binding_id",
        "base_person_id",
        "base_display_name",
        "created_from_other_account",
    }
    result: dict[str, Any] = {}
    for key in allowed:
        value = account.get(key)
        if isinstance(value, bool):
            result[key] = value
        elif value is not None:
            result[key] = str(value).strip()[:320]
    return result


def _declared_account_payload(account: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in _safe_account_payload(account).items()
        if key in {"display_name", "full_name", "login", "email", "phone", "reason", "account_session_id", "session_id"}
    }


def _requester_create_marker_payload(
    *,
    custom_fields: dict[str, Any],
    requester_account_mode: str | None,
    ticket_context_snapshot: dict[str, Any],
    internal: bool = False,
) -> dict[str, Any]:
    ticket_context = (
        custom_fields.get("ticket_context")
        if isinstance(custom_fields.get("ticket_context"), dict)
        else ticket_context_snapshot
    )
    request_context = str(custom_fields.get("request_context") or "web_requester").strip() or "web_requester"
    request_form = custom_fields.get("request_form") if isinstance(custom_fields.get("request_form"), dict) else {}
    policy_refs = custom_fields.get("policy_refs") if isinstance(custom_fields.get("policy_refs"), dict) else {}
    effective_policy_snapshots = (
        custom_fields.get("effective_policy_snapshots")
        if isinstance(custom_fields.get("effective_policy_snapshots"), dict)
        else {}
    )
    diagnostic_target = (
        ticket_context.get("diagnostic_target")
        if isinstance(ticket_context, dict) and isinstance(ticket_context.get("diagnostic_target"), dict)
        else {}
    )
    payload: dict[str, Any] = {
        "source": "requester_ticket_create",
        "request_context": request_context,
        "requester_account_mode": requester_account_mode or "unknown",
        "has_ticket_context": bool(ticket_context),
        "created_on_behalf": bool(
            ticket_context.get("created_on_behalf")
            if isinstance(ticket_context, dict)
            else False
        ),
        "has_request_form_snapshot": bool(request_form),
        "has_policy_snapshot": bool(policy_refs or effective_policy_snapshots),
        "diagnostic_target_available": bool(diagnostic_target.get("available")),
        "diagnostic_target_status": str(
            diagnostic_target.get("status")
            or diagnostic_target.get("agent_status")
            or "unknown"
        ).strip()[:80],
    }
    if internal:
        payload["visibility"] = "internal"
    else:
        payload["history_event_type"] = "ticket_created"
    return payload


async def _read_registry_account_status(
    registry_port: RegistryPort,
    device_id: str | None,
) -> dict[str, Any]:
    """Translate the redacted port outcome for the legacy ticket-create flow."""

    if not device_id:
        return {
            "status": "no_device",
            "active_binding": None,
            "active_person": None,
            "requires_user_action": False,
            "requires_admin_action": False,
            "conflict_reason": None,
            "registry_source": "not_applicable",
        }
    requested_device_id = str(device_id)
    outcome = await registry_port.account_status(
        DeviceRef(external_id=requested_device_id)
    )
    if isinstance(outcome, AccountStatusProjection):
        if outcome.device.external_id != requested_device_id:
            raise ValueError("registry_projection_invalid")
        active_binding = None
        active_person = None
        if outcome.active_binding is not None:
            if (
                outcome.active_binding.device.external_id != requested_device_id
                or outcome.active_binding.requester.external_id
                != outcome.active_binding.requester_snapshot.person.external_id
            ):
                raise ValueError("registry_projection_invalid")
            active_binding = {
                "binding_id": outcome.active_binding.binding.external_id,
                "person_id": outcome.active_binding.requester.external_id,
                "relationship_type": outcome.active_binding.relationship_type,
            }
            active_person = {
                "person_id": outcome.active_binding.requester.external_id,
                "display_name": outcome.active_binding.requester_snapshot.display_name,
            }
        return {
            "status": outcome.status,
            "active_binding": active_binding,
            "active_person": active_person,
            "requires_user_action": outcome.requires_user_action,
            "requires_admin_action": outcome.requires_admin_action,
            "conflict_reason": outcome.code,
            "registry_source": outcome.source,
        }
    if isinstance(outcome, RegistryUnavailable):
        if outcome.code == "registry_projection_invalid":
            raise ValueError("registry_projection_invalid")
        return {
            "status": "registry_unavailable",
            "active_binding": None,
            "active_person": None,
            "requires_user_action": False,
            "requires_admin_action": False,
            "conflict_reason": outcome.code,
            "registry_source": "unavailable",
        }
    raise ValueError("registry_projection_invalid")


_SUBMITTED_REGISTRATION_STATUS = {
    "pending_user_confirmation": "self_reported",
    "self_reported": "self_reported",
    "user_confirmed": "pending_admin_review",
    "pending_admin_review": "pending_admin_review",
    "conflict": "conflict",
}


def _compose_submitted_registration_status(
    current: dict[str, Any],
    submitted: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay a trusted same-transaction submission only onto stale absence."""

    observed_status = str(current.get("status") or "").strip()
    if current.get("active_binding") or observed_status not in {"", "unregistered"}:
        return current
    submitted_status = str((submitted or {}).get("status") or "").strip()
    composed_status = _SUBMITTED_REGISTRATION_STATUS.get(submitted_status)
    if composed_status is None:
        return current
    conflict_reason = str((submitted or {}).get("conflict_reason") or "").strip() or None
    return {
        **current,
        "status": composed_status,
        "requires_user_action": bool((submitted or {}).get("requires_user_action")),
        "requires_admin_action": bool((submitted or {}).get("requires_admin_action")),
        "conflict_reason": conflict_reason,
    }


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

    async def add_routing_event(ticket_id: str, device_id: str | None, event_type: str, payload: Dict[str, Any]) -> None:
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
    device_id: str | None,
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
    requester_account: Optional[dict[str, Any]] = None,
    ticket_context: Optional[dict[str, Any]] = None,
    state: Any | None = None,
    registry_port: RegistryPort | None = None,
) -> Dict[str, Any]:
    ticket_repo = TicketEventsRepo(session)
    ticket_id = new_ticket_id()
    registry = registry_port or DomainPortContainer.from_config(
        registry_session=session
    ).registry
    asset_id = None
    registry_context: dict[str, Any] | None = None
    has_requester_account = isinstance(requester_account, dict)
    existing_active_binding = None
    try:
        registration_precheck = await _read_registry_account_status(registry, device_id)
        existing_active_binding = registration_precheck.get("active_binding")
        if existing_active_binding:
            registry_context = {
                "person_id": existing_active_binding.get("person_id"),
                "registration": {
                    "binding_id": existing_active_binding.get("binding_id"),
                    "status": "admin_confirmed",
                    "relationship_type": existing_active_binding.get("relationship_type"),
                },
                "source": "active_registration_binding",
            }
    except ValueError as exc:
        if str(exc) == "registry_projection_invalid":
            raise
        logger.warning(f"[create] registration precheck failed ticket_id={ticket_id} err={exc}")
    except Exception as exc:
        logger.warning(f"[create] registration precheck failed ticket_id={ticket_id} err={exc}")
    account_mode = ""
    requester_account_session_validation: dict[str, Any] | None = None
    if has_requester_account:
        session_id = str(requester_account.get("session_id") or requester_account.get("account_session_id") or "").strip()
        if session_id:
            try:
                from registry.account_session_service import AccountSessionService

                if device_id:
                    requester_account_session_validation = await AccountSessionService(session).validate_session(
                        device_id=device_id,
                        session_id=session_id,
                        session_token=str(requester_account.get("session_token") or "").strip() or None,
                    )
                    if requester_account_session_validation.get("valid"):
                        server_session = requester_account_session_validation.get("session") or {}
                        declared = server_session.get("declared_account") if isinstance(server_session.get("declared_account"), dict) else {}
                        requester_account = {
                            **declared,
                            **server_session,
                            "account_session_id": server_session.get("session_id"),
                            "session_token": requester_account.get("session_token"),
                            "validation": "server_session_verified",
                        }
                        account_mode = str(server_session.get("account_mode") or "").strip()
                    else:
                        account_mode = "account_session_invalid"
                else:
                    account_mode = str(requester_account.get("account_mode") or "").strip()
            except Exception as exc:
                logger.warning(f"[create] account session validation failed ticket_id={ticket_id} err={exc}")
                account_mode = "account_session_invalid"
        else:
            account_mode = str(requester_account.get("account_mode") or "").strip()
    skip_profile_ingest = bool(requester_account_session_validation) or account_mode in {
        "confirmed_binding",
        "browser_no_device",
        "other_account",
        "verified_other_account",
        "unverified_other_account",
        "registration_pending",
    }
    if requester_profile:
        if existing_active_binding is None and not skip_profile_ingest:
            try:
                from registry.service import RegistryIngestionService

                registry_result = await RegistryIngestionService(session).ingest_requester_profile(
                    device_id=device_id,
                    requester_id=requester_id,
                    display_name=user_display_name,
                    profile=requester_profile or {},
                )
                asset_id = registry_result.asset_id
                registry_context = {
                    "person_id": registry_result.person_id,
                    "asset_id": registry_result.asset_id,
                    "location_id": registry_result.location_id,
                    "department_id": registry_result.department_id,
                    "registration": registry_result.registration,
                    "source": "agent_profile",
                }
            except Exception as exc:
                logger.warning(f"[create] registry profile ingest failed ticket_id={ticket_id} err={exc}")
    requester_person_id = None
    requester_binding_id = None
    verified_requester_person_id: str | None = None
    requester_registration_status = "unregistered"
    requester_registration_context: dict[str, Any] = {"status": "unregistered"}
    legacy_agent_only = not has_requester_account
    requester_account_context: dict[str, Any] = {
        "account_mode": "agent_legacy_or_device_only" if legacy_agent_only else (account_mode or "none")
    }
    requester_account_session_id: str | None = None
    requester_account_mode: str | None = None
    requester_account_warning: str | None = None
    try:
        registration_status = await _read_registry_account_status(registry, device_id)
        submitted_registration = registry_context.get("registration") if isinstance(registry_context, dict) else None
        registration_status = _compose_submitted_registration_status(
            registration_status,
            submitted_registration if isinstance(submitted_registration, dict) else None,
        )
        active_binding = registration_status.get("active_binding") if isinstance(registration_status, dict) else None
        if account_mode == "account_session_invalid":
            requester_registration_status = "account_session_invalid"
            requester_account_context = {
                "account_mode": "none",
                "validation": "server_session_invalid",
                "error_code": (requester_account_session_validation or {}).get("error_code") or "ACCOUNT_SESSION_INVALID",
            }
        elif account_mode in {"other_account", "verified_other_account", "unverified_other_account"}:
            verified = account_mode == "verified_other_account"
            requester_registration_status = "other_account" if verified else "unverified_other_account"
            requester_binding_id = None
            if verified and requester_account_session_validation and requester_account_session_validation.get("valid"):
                requester_person_id = str((requester_account or {}).get("person_id") or "").strip() or None
                verified_requester_person_id = requester_person_id
            if isinstance(active_binding, dict) and active_binding.get("binding_id"):
                asset_id = active_binding.get("asset_id") or asset_id
                requester_account_context = {
                    "account_mode": account_mode,
                    "account_session_id": str((requester_account or {}).get("account_session_id") or (requester_account or {}).get("session_id") or ""),
                    "created_from_other_account": True,
                    "declared_account": _declared_account_payload(requester_account or requester_profile or {}),
                    "active_device_binding_id": active_binding.get("binding_id"),
                    "active_device_person_id": active_binding.get("person_id"),
                    "active_device_person_name": (
                        (registration_status.get("active_person") or {}).get("display_name")
                        if isinstance(registration_status.get("active_person"), dict)
                        else None
                    ),
                    "verification_status": "verified" if verified else "unverified",
                    "verification_method": (requester_account or {}).get("verification_method"),
                    "validation": (requester_account or {}).get("validation") or ("legacy_payload_unverified" if not verified else "server_session_verified"),
                    "warning": "ticket_created_from_other_account_on_registered_device"
                    if verified
                    else "unverified_other_account_legacy_payload",
                }
            else:
                requester_account_context = {
                    "account_mode": account_mode,
                    "account_session_id": str((requester_account or {}).get("account_session_id") or (requester_account or {}).get("session_id") or ""),
                    "created_from_other_account": True,
                    "declared_account": _declared_account_payload(requester_account or requester_profile or {}),
                    "verification_status": "verified" if verified else "unverified",
                    "verification_method": (requester_account or {}).get("verification_method"),
                    "validation": (requester_account or {}).get("validation") or ("legacy_payload_unverified" if not verified else "server_session_verified"),
                    "warning": "ticket_created_from_other_account" if verified else "unverified_other_account_legacy_payload",
                }
        elif account_mode == "browser_no_device":
            requester_person_id = str((requester_account or {}).get("person_id") or "").strip() or None
            requester_binding_id = None
            requester_registration_status = "no_device"
            requester_registration_context = {
                "status": "no_device",
                "device_scope": "none",
                "validation": (requester_account or {}).get("validation") or "web_requester_identity_resolved",
            }
            requester_account_context = {
                **_safe_account_payload(requester_account or {}),
                "account_mode": "browser_no_device",
                "person_id": requester_person_id,
                "validation": (requester_account or {}).get("validation") or "web_requester_identity_resolved",
            }
        elif account_mode == "registration_pending":
            pending_claim = registration_status.get("pending_claim") if isinstance(registration_status, dict) else None
            requester_registration_status = str(
                (pending_claim or {}).get("status")
                or (requester_account or {}).get("registration_status")
                or (requester_account or {}).get("verification_status")
                or "registration_pending"
            )
            requester_person_id = (pending_claim or {}).get("person_id") or (requester_account or {}).get("person_id")
            requester_binding_id = None
            if isinstance(registration_status, dict):
                active_asset = registration_status.get("asset") if isinstance(registration_status.get("asset"), dict) else None
                asset_id = (active_asset or {}).get("asset_id") or asset_id
            requester_account_context = {
                **_safe_account_payload(requester_account or {}),
                "account_mode": "registration_pending",
                "validation": "accepted_pending_registration",
            }
        elif account_mode == "confirmed_binding":
            requested_binding_id = str((requester_account or {}).get("binding_id") or "").strip()
            requested_person_id = str((requester_account or {}).get("person_id") or "").strip()
            account_validation = str((requester_account or {}).get("validation") or "").strip()
            session_binding = None
            if requested_binding_id and (
                requester_account_session_validation or account_validation == "web_requester_identity_resolved"
            ):
                from app.repos.registration_repo import RegistrationRepo

                session_binding = await RegistrationRepo(session).get_active_binding_for_device(device_id, requested_binding_id)
                if session_binding is not None and requested_person_id and session_binding.person_id != requested_person_id:
                    session_binding = None
            if session_binding is not None or (
                isinstance(active_binding, dict) and active_binding.get("binding_id") == requested_binding_id
            ):
                binding_payload = (
                    {
                        "person_id": session_binding.person_id,
                        "binding_id": session_binding.binding_id,
                        "asset_id": session_binding.asset_id,
                    }
                    if session_binding is not None
                    else active_binding
                )
                requester_person_id = binding_payload.get("person_id")
                requester_binding_id = binding_payload.get("binding_id")
                verified_requester_person_id = requester_person_id
                asset_id = binding_payload.get("asset_id") or asset_id
                requester_registration_status = "admin_confirmed"
                requester_account_context = {
                    **_safe_account_payload(requester_account or {}),
                    "account_mode": "confirmed_binding",
                    "validation": (requester_account or {}).get("validation")
                    or ("server_session_verified" if requester_account_session_validation else "active_binding_confirmed"),
                }
            else:
                requester_registration_status = "no_account"
                requester_account_context = {
                    **_safe_account_payload(requester_account or {}),
                    "account_mode": "confirmed_binding",
                    "validation": "active_binding_not_found",
                }
        elif isinstance(active_binding, dict) and active_binding.get("binding_id"):
            requester_person_id = active_binding.get("person_id")
            requester_binding_id = active_binding.get("binding_id")
            verified_requester_person_id = requester_person_id
            asset_id = active_binding.get("asset_id") or asset_id
            requester_registration_status = "admin_confirmed"
            if legacy_agent_only:
                requester_account_context = {
                    "account_mode": "agent_legacy_or_device_only",
                    "validation": "agent_token_without_account_session",
                    "context_scope": "limited",
                    "profile_completion_evidence": False,
                }
        else:
            pending_claim = registration_status.get("pending_claim") if isinstance(registration_status, dict) else None
            requester_registration_status = str(
                (pending_claim or {}).get("status")
                or (registration_status or {}).get("status")
                or "unregistered"
            )
            if legacy_agent_only:
                requester_account_context = {
                    "account_mode": "agent_legacy_or_device_only",
                    "validation": "agent_token_without_account_session",
                    "context_scope": "limited",
                    "profile_completion_evidence": False,
                }
        if account_mode != "browser_no_device":
            requester_registration_context = registration_status if isinstance(registration_status, dict) else requester_registration_context
    except ValueError as exc:
        if str(exc) == "registry_projection_invalid":
            raise
        logger.warning(f"[create] registration requester context failed ticket_id={ticket_id} err={exc}")
    except Exception as exc:
        logger.warning(f"[create] registration requester context failed ticket_id={ticket_id} err={exc}")

    if account_mode == "browser_no_device" and requester_person_id:
        try:
            from requester.identity_service import RequesterIdentityResolver

            server_person = await RequesterIdentityResolver(session, state=state).resolve_person_for_web_user(
                requester_id
            )
            if server_person is not None and str(server_person.person_id) == str(requester_person_id):
                verified_requester_person_id = str(server_person.person_id)
        except Exception as exc:
            logger.warning(
                f"[create] web requester identity verification failed ticket_id={ticket_id} err={exc}"
            )

    if isinstance(requester_account_context, dict):
        requester_account_session_id = str(
            requester_account_context.get("account_session_id") or requester_account_context.get("session_id") or ""
        ).strip() or None
        requester_account_mode = str(requester_account_context.get("account_mode") or "").strip() or None
        requester_account_warning = str(requester_account_context.get("warning") or "").strip() or None

    requester_ref = None
    requester_snapshot = None
    if verified_requester_person_id:
        requester_ref, requester_snapshot = await TicketContextBuilder(
            session,
            state=state,
            registry_port=registry,
        ).requester_reference_snapshot(verified_requester_person_id)
        if requester_ref is None or requester_snapshot is None:
            raise ValueError("verified requester requires a complete requester reference snapshot")

    ticket_context_snapshot: dict[str, Any] | None = None
    if requester_person_id:
        try:
            context_input = ticket_context if isinstance(ticket_context, dict) else {}
            context_custom_fields = extra_custom_fields if isinstance(extra_custom_fields, dict) else {}
            requester_context_snapshot = (
                context_custom_fields.get("requester_context_snapshot")
                if isinstance(context_custom_fields.get("requester_context_snapshot"), dict)
                else requester_account_context
            )
            request_form_snapshot = (
                context_custom_fields.get("request_form")
                if isinstance(context_custom_fields.get("request_form"), dict)
                else {}
            )
            policy_refs_snapshot = (
                context_custom_fields.get("policy_refs")
                if isinstance(context_custom_fields.get("policy_refs"), dict)
                else {}
            )
            ticket_context_snapshot = await TicketContextBuilder(
                session,
                state=state,
                registry_port=registry,
            ).build(
                creator_person_id=str(requester_person_id),
                creator_actor_id=requester_id,
                affected_person_id=str(context_input.get("affected_person_id") or "").strip() or None,
                on_behalf_reason=str(
                    context_input.get("on_behalf_reason") or context_input.get("reason") or ""
                ).strip()
                or None,
                requester_context=requester_context_snapshot,
                form=request_form_snapshot,
                policy_refs=policy_refs_snapshot,
            )
        except Exception as exc:
            logger.warning(f"[create] ticket context build failed ticket_id={ticket_id} err={exc}")

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
        asset_id=asset_id,
        requester_person_id=requester_person_id,
        requester_binding_id=requester_binding_id,
        requester_registration_status=requester_registration_status,
        requester_account_session_id=requester_account_session_id,
        requester_account_mode=requester_account_mode,
        requester_account_warning=requester_account_warning,
        requester_ref=requester_ref,
        requester_snapshot=requester_snapshot,
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
    if ticket_context_snapshot:
        custom_fields.update(TicketContextBuilder.custom_fields(ticket_context_snapshot))
    custom_fields["requester_registration"] = requester_registration_context
    custom_fields["requester_account_context"] = requester_account_context
    if registry_context:
        custom_fields["registry_context"] = registry_context

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
    if ticket_context_snapshot:
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="ticket_context_resolved",
            payload=ticket_context_resolved_event_payload(ticket_context_snapshot),
            trace_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
        )
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="customer_history_ticket_created",
            payload=_requester_create_marker_payload(
                custom_fields=custom_fields,
                requester_account_mode=requester_account_mode,
                ticket_context_snapshot=ticket_context_snapshot,
            ),
            trace_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
        )
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="requester_ticket_create_audit",
            payload=_requester_create_marker_payload(
                custom_fields=custom_fields,
                requester_account_mode=requester_account_mode,
                ticket_context_snapshot=ticket_context_snapshot,
                internal=True,
            ),
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
                "requester_account_session_id": requester_account_session_id,
                "requester_account_mode": requester_account_mode,
                "requester_person_id": requester_person_id,
                "requester_binding_id": requester_binding_id,
                "created_from_other_account": requester_account_mode == "verified_other_account",
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
        if requester_account_session_id and device_id:
            from registry.account_session_service import AccountSessionService
            await AccountSessionService(session).repo.append_event(
                device_id=device_id,
                session_id=requester_account_session_id,
                ticket_id=ticket_id,
                event_type="ticket_created_with_other_account"
                if requester_account_mode == "verified_other_account"
                else "ticket_created_with_account_session",
                actor_id=requester_id,
                actor_role="agent" if requester_id == device_id else "user",
                payload={
                    "account_mode": requester_account_mode,
                    "requester_registration_status": requester_registration_status,
                    "warning": requester_account_warning,
                },
            )
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
