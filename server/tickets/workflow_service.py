"""Ticket workflow FSM and side effects."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select

from app.db.models import TicketApproval, TicketEvidenceItem, TicketWait
from app.repos.auth_tokens_repo import AuthTokensRepo
from tickets.approval_policy import ensure_approval_requests, validate_approval_policy
from tickets.closure_policy import validate_closure_policy
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.sla_service import TicketSlaService
from tickets.side_effects import run_workflow_side_effect
from tickets.statuses import (
    WAITING_STATUSES,
    next_action_owner_for_status,
    requester_status_for_internal,
    wait_type_for_status,
)
from tickets.workflow_profiles import (
    DEFAULT_REQUESTER_TRANSITIONS,
    DEFAULT_SUPPORT_TRANSITIONS,
    WorkflowProfile,
    WorkflowTransitionGate,
    load_workflow_profiles,
    workflow_profile_by_type,
)


SUPPORT_TRANSITIONS = {key: list(value) for key, value in DEFAULT_SUPPORT_TRANSITIONS.items()}

REQUESTER_TRANSITIONS = {key: list(value) for key, value in DEFAULT_REQUESTER_TRANSITIONS.items()}


def _allowed_transitions(from_status: str, is_support_or_admin: bool) -> List[str]:
    if is_support_or_admin:
        return list(SUPPORT_TRANSITIONS.get(from_status, []))
    return list(REQUESTER_TRANSITIONS.get(from_status, []))


def validate_transition(
    from_status: str,
    to_status_canonical: str,
    is_support_or_admin: bool,
) -> bool:
    return to_status_canonical in _allowed_transitions(from_status, is_support_or_admin)


def validate_transition_for_profile(
    profile: WorkflowProfile,
    from_status: str,
    to_status_canonical: str,
    is_support_or_admin: bool,
) -> bool:
    if not is_support_or_admin:
        return to_status_canonical in REQUESTER_TRANSITIONS.get(from_status, [])
    if to_status_canonical not in profile.allowed_statuses:
        return False
    transitions = profile.transitions or DEFAULT_SUPPORT_TRANSITIONS
    return to_status_canonical in transitions.get(from_status, ())


def _transition_gate_for_profile(
    profile: WorkflowProfile,
    from_status: str,
    to_status_canonical: str,
) -> WorkflowTransitionGate | None:
    return ((profile.transition_gates or {}).get(from_status) or {}).get(to_status_canonical)


def _auto_triggered_transition_for_profile(
    profile: WorkflowProfile,
    from_status: str,
    trigger: str,
) -> tuple[str, WorkflowTransitionGate] | None:
    normalized_trigger = str(trigger or "").strip()
    if not normalized_trigger:
        return None
    transitions = profile.transitions or DEFAULT_SUPPORT_TRANSITIONS
    gates = (profile.transition_gates or {}).get(from_status) or {}
    for to_status in transitions.get(from_status, ()):
        gate = gates.get(to_status)
        if gate and gate.auto and gate.trigger == normalized_trigger:
            return to_status, gate
    return None


def _field_value(ticket, updates: dict, field_name: str):
    field = str(field_name or "").strip()
    if not field:
        return None
    if field in updates:
        return updates[field]
    aliases = {
        "public_summary": ("resolution_summary", "requester_resolution_summary"),
        "resolution_public_summary": ("resolution_summary", "requester_resolution_summary"),
    }
    for alias in aliases.get(field, ()):
        if alias in updates:
            return updates[alias]
        if ticket is not None and hasattr(ticket, alias):
            value = getattr(ticket, alias)
            if value not in (None, ""):
                return value
    if ticket is not None and hasattr(ticket, field):
        return getattr(ticket, field)
    current = getattr(ticket, "custom_fields", None) or {}
    parts = field.split(".")
    if parts and parts[0] == "custom_fields":
        parts = parts[1:]
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _is_missing_required_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | set | dict):
        return len(value) == 0
    return False


def _actor_matches_allowed_role(ticket, *, actor_id: str, actor_role: str, allowed_role: str) -> bool:
    role = str(allowed_role or "").strip()
    if not role:
        return False
    actor_id = str(actor_id or "").strip()
    actor_role = str(actor_role or "").strip()
    if role == actor_role:
        return True
    if role == "assignee":
        return bool(ticket is not None and actor_id and actor_id == str(getattr(ticket, "assignee_id", "") or ""))
    if role == "requester":
        return actor_role in {"requester", "user"} or bool(
            ticket is not None and actor_id and actor_id == str(getattr(ticket, "requester_id", "") or "")
        )
    if role == "queue_lead":
        return actor_role == "queue_lead"
    if role == "system":
        return actor_role == "system"
    return False


def _comment_value_for_requirement(required_comment: str | None, *, public_comment: str | None, internal_comment: str | None):
    if required_comment == "public":
        return public_comment
    if required_comment == "internal":
        return internal_comment
    if required_comment == "any":
        return public_comment or internal_comment
    return None


def _transition_log_field_payload(gate: WorkflowTransitionGate | None, *, ticket, updates: dict) -> list[dict]:
    if gate is None or not gate.log_fields:
        return []
    payload: list[dict] = []
    for field in gate.log_fields:
        value = _field_value(ticket, updates, field)
        payload.append(
            {
                "field": field,
                "value": value,
                "present": not _is_missing_required_value(value),
            }
        )
    return payload


def _validate_status_invariants(ticket, to_status: str) -> None:
    if to_status != "assigned":
        return
    missing_fields = []
    if _is_missing_required_value(getattr(ticket, "queue_id", None)):
        missing_fields.append("queue_id")
    if _is_missing_required_value(getattr(ticket, "assignee_id", None)):
        missing_fields.append("assignee_id")
    if missing_fields:
        raise ValueError(
            "workflow_profile transition gate missing required_fields: "
            + ", ".join(missing_fields)
        )


async def _validate_transition_gate(
    *,
    gate: WorkflowTransitionGate | None,
    session,
    ticket,
    updates: dict,
    actor_id: str,
    actor_role: str,
    public_comment: str | None = None,
    internal_comment: str | None = None,
) -> dict | None:
    if gate is None:
        return None
    missing_fields = [
        field
        for field in gate.required_fields
        if _is_missing_required_value(_field_value(ticket, updates, field))
    ]
    if missing_fields:
        raise ValueError(
            "workflow_profile transition gate missing required_fields: "
            + ", ".join(missing_fields)
        )
    if gate.allowed_roles and not any(
        _actor_matches_allowed_role(ticket, actor_id=actor_id, actor_role=actor_role, allowed_role=role)
        for role in gate.allowed_roles
    ):
        raise ValueError(
            "workflow_profile transition gate blocked by allowed_roles: "
            f"{actor_role} is not allowed for {gate.to_status}; allowed_roles="
            + ", ".join(gate.allowed_roles)
        )
    if gate.required_comment and _is_missing_required_value(
        _comment_value_for_requirement(
            gate.required_comment,
            public_comment=public_comment,
            internal_comment=internal_comment,
        )
    ):
        raise ValueError(
            "workflow_profile transition gate missing required_comment: "
            f"{gate.required_comment}"
        )
    if gate.require_evidence:
        ticket_id = str(getattr(ticket, "ticket_id", "") or "")
        evidence_ref = getattr(ticket, "evidence_ref", None) if ticket is not None else None
        evidence_exists = None
        if ticket_id:
            evidence_exists = await session.scalar(
                select(TicketEvidenceItem.id)
                .where(TicketEvidenceItem.ticket_id == ticket_id)
                .limit(1)
            )
        if not evidence_ref and evidence_exists is None:
            raise ValueError("workflow_profile transition gate blocked by require_evidence")
    if gate.require_approval:
        ticket_id = str(getattr(ticket, "ticket_id", "") or "")
        rows = await session.execute(
            select(TicketApproval.status).where(TicketApproval.ticket_id == ticket_id)
        )
        approval_statuses = [str(status or "").strip().lower() for status in rows.scalars().all()]
        if any(status in {"rejected", "denied", "declined"} for status in approval_statuses):
            raise ValueError("workflow_profile transition gate rejected approval blocks transition")
        if "approved" not in approval_statuses:
            raise ValueError("workflow_profile transition gate requires approved approval")
    return {
        "to": gate.to_status,
        "allowed_roles": list(gate.allowed_roles),
        "required_fields": list(gate.required_fields),
        "required_comment": gate.required_comment,
        "require_approval": gate.require_approval,
        "require_evidence": gate.require_evidence,
        "log_fields": list(gate.log_fields),
    }


async def load_ticket_workflow_profile(session, ticket) -> WorkflowProfile:
    profiles = await load_workflow_profiles(session)
    profile_key = getattr(ticket, "ticket_type", None) if ticket else None
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if isinstance(custom_fields, dict):
        request_template = custom_fields.get("request_template") or {}
        if isinstance(request_template, dict):
            profile_key = (
                request_template.get("workflow_profile_id")
                or request_template.get("workflow_profile")
                or request_template.get("workflow_profile_code")
                or profile_key
            )
    return workflow_profile_by_type(profiles, profile_key)


async def validate_transition_for_ticket(
    session,
    ticket,
    to_status_canonical: str,
    is_support_or_admin: bool,
) -> bool:
    profile = await load_ticket_workflow_profile(session, ticket)
    return validate_transition_for_profile(
        profile,
        getattr(ticket, "status", "") if ticket else "",
        to_status_canonical,
        is_support_or_admin,
    )


class TicketWorkflowService:
    """Apply status transitions and keep lifecycle side effects in sync."""

    def __init__(self, session, ticket_repo):
        self.session = session
        self.ticket_repo = ticket_repo
        self.sla_service = TicketSlaService(session, ticket_repo)

    async def apply_status_transition(
        self,
        ticket_id: str,
        from_status: str,
        to_status: str,
        actor_id: str,
        actor_role: str,
        reason: Optional[str] = None,
        resolution_code: Optional[str] = None,
        resolution_summary: Optional[str] = None,
        requester_resolution_summary: Optional[str] = None,
        root_cause: Optional[str] = None,
        public_comment: Optional[str] = None,
        internal_comment: Optional[str] = None,
        source: str = "api",
        workflow_trigger: dict | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        workflow_profile = await load_ticket_workflow_profile(self.session, ticket)
        updates = {
            "next_action_owner": next_action_owner_for_status(to_status),
            "requester_status": requester_status_for_internal(to_status),
            "status_reason": (
                reason or None
                if to_status in WAITING_STATUSES or to_status in {"scheduled", "canceled"}
                else None
            ),
        }
        event_payload = {
            "from_status": from_status,
            "to_status": to_status,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": reason or "",
            "source": source,
            "normalized": True,
            "workflow_profile": workflow_profile.ticket_type,
            "next_action_owner": updates["next_action_owner"],
            "requester_status": updates["requester_status"],
        }
        if workflow_trigger:
            event_payload["workflow_trigger"] = dict(workflow_trigger)
        if resolution_code is not None:
            event_payload["resolution_code"] = resolution_code
            updates["resolution_code"] = resolution_code
        if resolution_summary is not None:
            event_payload["resolution_summary"] = resolution_summary
            updates["resolution_summary"] = resolution_summary
        if requester_resolution_summary is not None:
            event_payload["requester_resolution_summary"] = requester_resolution_summary
            updates["requester_resolution_summary"] = requester_resolution_summary
        if root_cause is not None:
            event_payload["root_cause"] = root_cause
            updates["root_cause"] = root_cause
        if public_comment is not None:
            event_payload["public_comment"] = public_comment
        if internal_comment is not None:
            event_payload["internal_comment"] = internal_comment

        _validate_status_invariants(ticket, to_status)
        transition_gate = _transition_gate_for_profile(workflow_profile, from_status, to_status)
        gate_payload = await _validate_transition_gate(
            gate=transition_gate,
            session=self.session,
            ticket=ticket,
            updates=updates,
            actor_id=actor_id,
            actor_role=actor_role,
            public_comment=public_comment,
            internal_comment=internal_comment,
        )
        if gate_payload:
            event_payload["workflow_transition_gate"] = gate_payload
            action_payload: dict[str, object] = {}
            action_results: dict[str, object] = {}
            if transition_gate and transition_gate.notify:
                action_payload["notify"] = list(transition_gate.notify)
                action_results["notify"] = {
                    "status": "recorded_marker",
                    "recipients": list(transition_gate.notify),
                }
            if transition_gate and transition_gate.sla_action:
                action_payload["sla"] = transition_gate.sla_action
            if transition_gate and transition_gate.approval_action:
                action_payload["approval"] = transition_gate.approval_action
            if action_payload:
                event_payload["workflow_transition_actions"] = action_payload
            log_fields_payload = _transition_log_field_payload(
                transition_gate,
                ticket=ticket,
                updates=updates,
            )
            if log_fields_payload:
                event_payload["workflow_transition_log_fields"] = log_fields_payload
            if action_results:
                event_payload["workflow_transition_action_results"] = action_results

        approval_decision = await validate_approval_policy(
            self.session,
            ticket,
            from_status=from_status,
            to_status=to_status,
            reject_comment=reason or public_comment or internal_comment,
        )
        if approval_decision.get("applied"):
            if approval_decision.get("gate") == "waiting":
                approval_decision.update(
                    await ensure_approval_requests(
                        self.session,
                        ticket,
                        actor_id=actor_id,
                        actor_role=actor_role,
                    )
                )
            event_payload["approval_policy"] = approval_decision

        if to_status == "resolved":
            closure_decision = await validate_closure_policy(
                self.session,
                ticket,
                to_status=to_status,
                resolution_code=resolution_code,
                resolution_summary=resolution_summary,
                requester_resolution_summary=requester_resolution_summary,
            )
            if closure_decision.get("applied"):
                event_payload["closure_policy"] = closure_decision
                confirmation_policy = closure_decision.get("requester_confirmation")
                if isinstance(confirmation_policy, dict) and confirmation_policy:
                    custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
                    custom_fields["resolution_confirmation_policy"] = confirmation_policy
                    updates["custom_fields"] = custom_fields
            if ticket and getattr(ticket, "evidence_required", False) and not getattr(ticket, "evidence_ref", None):
                evidence_exists = await self.session.scalar(
                    select(TicketEvidenceItem.id)
                    .where(TicketEvidenceItem.ticket_id == ticket_id)
                    .limit(1)
                )
                if evidence_exists is None:
                    raise ValueError(
                        "Для решения тикета требуется подтверждение: "
                        "добавьте доказательство или ссылку evidence_ref"
                    )
            if ticket and getattr(ticket, "resolved_at", None) is None:
                updates["resolved_at"] = now

        if to_status == "closed":
            updates["closed_at"] = now
            updates["resolution_at"] = now

        if to_status == "canceled":
            updates["canceled_at"] = now

        if from_status in ("resolved", "closed", "canceled") and to_status in {"new", "in_progress"}:
            updates["resolved_at"] = None
            updates["closed_at"] = None
            updates["resolution_at"] = None
            updates["resolution_code"] = None
            updates["root_cause"] = None
            updates["canceled_at"] = None

        transition_trigger = transition_gate.trigger if transition_gate and transition_gate.trigger else None
        approval_completed_trigger = (
            "approval_completed"
            if transition_gate and transition_gate.require_approval and from_status == "waiting_on_approval"
            else None
        )
        pause_trigger = transition_trigger or "status_changed"
        resume_trigger = transition_trigger or approval_completed_trigger or "status_changed"
        side_effect_correlation_id = str(uuid.uuid4())
        current_device_id = str(getattr(ticket, "device_id", "") or "")

        if to_status in WAITING_STATUSES:
            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="sla",
                action="pause",
                trigger=pause_trigger,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=True,
                operation=lambda: self.sla_service.pause_sla(ticket_id, trigger=pause_trigger, status=to_status),
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

            async def _pause_ola() -> object:
                from tickets.ola_service import pause_ola

                return await pause_ola(self.session, ticket_id, trigger=pause_trigger, status=to_status)

            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="ola",
                action="pause",
                trigger=pause_trigger,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=False,
                operation=_pause_ola,
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

        if from_status in WAITING_STATUSES and to_status not in WAITING_STATUSES:
            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="sla",
                action="resume",
                trigger=resume_trigger,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=True,
                operation=lambda: self.sla_service.resume_sla(ticket_id, trigger=resume_trigger, status=to_status),
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

            async def _resume_ola() -> object:
                from tickets.ola_service import resume_ola

                return await resume_ola(self.session, ticket_id, trigger=resume_trigger, status=to_status)

            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="ola",
                action="resume",
                trigger=resume_trigger,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=False,
                operation=_resume_ola,
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

        if transition_gate and transition_gate.sla_action == "pause":
            applied = await self.sla_service.pause_sla(ticket_id, trigger=pause_trigger, status=to_status)
            event_payload.setdefault("workflow_transition_action_results", {})["sla"] = {
                "status": "executed" if applied else "no_op",
                "action": "pause",
            }
        elif transition_gate and transition_gate.sla_action == "resume":
            applied = await self.sla_service.resume_sla(ticket_id, trigger=resume_trigger, status=to_status)
            event_payload.setdefault("workflow_transition_action_results", {})["sla"] = {
                "status": "executed" if applied else "no_op",
                "action": "resume",
            }
        elif transition_gate and transition_gate.sla_action == "stop":
            event_payload.setdefault("workflow_transition_action_results", {})["sla"] = {
                "status": "skipped_use_terminal_status",
                "action": "stop",
            }

        if transition_gate and transition_gate.approval_action:
            approval_action = transition_gate.approval_action
            approval_policy = await resolve_effective_ticket_policy(self.session, ticket, "approval")
            if not approval_policy or not approval_policy.get("required"):
                event_payload.setdefault("workflow_transition_action_results", {})["approval"] = {
                    "status": "skipped_no_active_policy",
                    "action": approval_action,
                }
            elif approval_action == "create_request":
                approval_results: list[dict] = []

                async def _ensure_approval_requests() -> dict:
                    result = await ensure_approval_requests(
                        self.session,
                        ticket,
                        actor_id=actor_id,
                        actor_role=actor_role,
                    )
                    approval_results.append(result)
                    return result

                await run_workflow_side_effect(
                    ticket_repo=self.ticket_repo,
                    ticket_id=ticket_id,
                    device_id=current_device_id,
                    side_effect="approval",
                    action=approval_action,
                    trigger=transition_trigger or "transition_gate",
                    from_status=from_status,
                    to_status=to_status,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    critical=True,
                    operation=_ensure_approval_requests,
                    event_payload=event_payload,
                    correlation_id=side_effect_correlation_id,
                )
                approval_request_result = approval_results[0] if approval_results else {}
                created = int(approval_request_result.get("requests_created") or 0)
                event_payload.setdefault("workflow_transition_action_results", {})["approval"] = {
                    "status": "executed" if created else "no_op_existing",
                    "action": approval_action,
                    "requests_created": created,
                    "approval_mode": approval_request_result.get("approval_mode"),
                    "approver_source": approval_request_result.get("approver_source"),
                }
            else:
                event_payload.setdefault("workflow_transition_action_results", {})["approval"] = {
                    "status": "recorded_marker",
                    "action": approval_action,
                }

        await self._sync_wait_ledger(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
            now=now,
        )

        if to_status in ("resolved", "closed"):
            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="sla",
                action="stop_resolution",
                trigger="status_changed",
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=True,
                operation=lambda: self.sla_service.stop_resolution(
                    ticket_id,
                    status=to_status,
                    trigger="status_changed",
                ),
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

        await self.ticket_repo.update_ticket(
            ticket_id,
            status=to_status,
            **updates,
        )

        if to_status in ("resolved", "closed"):
            async def _close_ola_processing() -> object:
                from tickets.ola_service import close_ola_processing

                return await close_ola_processing(self.session, ticket_id, status=to_status, trigger="status_changed")

            await run_workflow_side_effect(
                ticket_repo=self.ticket_repo,
                ticket_id=ticket_id,
                device_id=current_device_id,
                side_effect="ola",
                action="close_processing",
                trigger="status_changed",
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                critical=False,
                operation=_close_ola_processing,
                event_payload=event_payload,
                correlation_id=side_effect_correlation_id,
            )

        if to_status == "closed":
            try:
                auth_repo = AuthTokensRepo(self.session)
                revoked = await auth_repo.revoke_ticket_public_sessions(ticket_id, commit=False)
                if revoked:
                    logger.info(
                        f"[Workflow] revoked public ticket sessions: ticket_id={ticket_id} count={revoked}"
                    )
            except Exception as revoke_err:
                logger.warning(
                    f"[Workflow] failed to revoke public ticket sessions: "
                    f"ticket_id={ticket_id} err={revoke_err}"
                )

        if from_status in ("resolved", "closed") and to_status == "new":
            await self.sla_service.on_reopen(ticket_id)

        ticket = await self.ticket_repo.get_ticket(ticket_id)
        event_result = await self.ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="status_changed",
            payload=event_payload,
            trace_id=str(uuid.uuid4()),
        )
        logger.info(
            f"[Workflow] status_changed ticket_id={ticket_id} "
            f"{from_status} -> {to_status} actor_role={actor_role} source={source}"
        )
        return {
            "applied": True,
            "no_op": False,
            "updates": {"status": to_status, **updates},
            "event_payload": event_payload,
            "event_result": event_result,
        }

    async def apply_triggered_transition(
        self,
        ticket_id: str,
        *,
        trigger: str,
        actor_id: str,
        actor_role: str,
        reason: Optional[str] = None,
        source: str = "workflow_trigger",
        trigger_actor_id: str | None = None,
        trigger_actor_role: str | None = None,
        fallback_status: str | None = None,
    ) -> dict:
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if ticket is None:
            return {"applied": False, "no_op": True, "reason": "ticket_not_found"}
        from_status = str(getattr(ticket, "status", "") or "").strip()
        workflow_profile = await load_ticket_workflow_profile(self.session, ticket)
        matched = _auto_triggered_transition_for_profile(workflow_profile, from_status, trigger)
        fallback = False
        if matched:
            to_status, gate = matched
            auto = gate.auto
        elif fallback_status:
            to_status = fallback_status
            auto = False
            fallback = True
        else:
            return {
                "applied": False,
                "no_op": True,
                "reason": "no_matching_workflow_trigger",
                "trigger": trigger,
            }
        effective_actor_id = actor_id
        effective_actor_role = actor_role
        if fallback and trigger_actor_id:
            effective_actor_id = trigger_actor_id
            effective_actor_role = trigger_actor_role or actor_role
        return await self.apply_status_transition(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=effective_actor_id,
            actor_role=effective_actor_role,
            reason=reason or trigger,
            source=source,
            workflow_trigger={
                "trigger": trigger,
                "trigger_actor_id": trigger_actor_id,
                "trigger_actor_role": trigger_actor_role,
                "auto": auto,
                "matched": matched is not None,
                "fallback": fallback,
            },
        )

    async def _sync_wait_ledger(
        self,
        *,
        ticket_id: str,
        from_status: str,
        to_status: str,
        actor_id: str,
        reason: Optional[str],
        now: datetime,
    ) -> None:
        from_wait_type = wait_type_for_status(from_status)
        to_wait_type = wait_type_for_status(to_status)
        if from_wait_type and from_wait_type != to_wait_type:
            result = await self.session.execute(
                select(TicketWait).where(
                    TicketWait.ticket_id == ticket_id,
                    TicketWait.ended_at.is_(None),
                )
            )
            for wait in result.scalars().all():
                wait.ended_at = now
                wait.closed_by = actor_id
        if to_wait_type and to_wait_type != from_wait_type:
            self.session.add(
                TicketWait(
                    ticket_id=ticket_id,
                    wait_type=to_wait_type,
                    started_at=now,
                    reason=reason or None,
                    related_party=reason or None,
                    created_by=actor_id,
                )
            )
