"""Ticket workflow FSM and side effects."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select

from app.db.models import TicketEvidenceItem, TicketWait
from app.repos.auth_tokens_repo import AuthTokensRepo
from tickets.closure_policy import validate_closure_policy
from tickets.sla_service import TicketSlaService
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


async def load_ticket_workflow_profile(session, ticket) -> WorkflowProfile:
    profiles = await load_workflow_profiles(session)
    return workflow_profile_by_type(profiles, getattr(ticket, "ticket_type", None) if ticket else None)


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
        source: str = "api",
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

        if to_status == "resolved":
            closure_decision = await validate_closure_policy(
                self.session,
                ticket,
                to_status=to_status,
                resolution_code=resolution_code,
                resolution_summary=resolution_summary or requester_resolution_summary,
            )
            if closure_decision.get("applied"):
                event_payload["closure_policy"] = closure_decision
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

        if to_status in WAITING_STATUSES:
            await self.sla_service.pause_sla(ticket_id)

        if from_status in WAITING_STATUSES and to_status not in WAITING_STATUSES:
            await self.sla_service.resume_sla(ticket_id)

        await self._sync_wait_ledger(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
            now=now,
        )

        await self.ticket_repo.update_ticket(
            ticket_id,
            status=to_status,
            **updates,
        )

        if to_status in ("resolved", "closed"):
            try:
                from tickets.ola_service import close_ola_processing

                await close_ola_processing(self.session, ticket_id)
            except Exception:
                pass

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
