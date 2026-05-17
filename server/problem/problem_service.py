from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.db.models import (
    ContinuousImprovementAction,
    HelpdeskService,
    HelpdeskServiceOffering,
    Problem,
    ProblemActivityEvent,
    ProblemAffectedObject,
    ProblemTicketLink,
    Ticket,
)
from problem.contracts import (
    PROBLEM_PRIORITIES,
    PROBLEM_SEVERITIES,
    can_transition_problem,
    clean_text,
    normalize_problem_status,
    validate_choice,
    validate_problem_resolution_payload,
)
from problem.serializers import problem_to_dict, ticket_link_to_dict
from problem.slo_service import ProblemSLOService


class ProblemService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_problem(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        title = clean_text(payload.get("title"))
        description = clean_text(payload.get("description"))
        if not title:
            raise ValueError("title is required")
        if not description:
            raise ValueError("description is required")
        await self._validate_service_offering(payload.get("service_code"), payload.get("offering_code"))
        now = datetime.now(timezone.utc)
        row = Problem(
            problem_id=str(uuid.uuid4()),
            problem_key=await self._next_problem_key(),
            title=title,
            description=description,
            status=normalize_problem_status(payload.get("status") or "new"),
            severity=validate_choice(payload.get("severity"), PROBLEM_SEVERITIES, "severity", default="medium"),
            priority=validate_choice(payload.get("priority"), PROBLEM_PRIORITIES, "priority", default="medium"),
            impact=validate_choice(payload.get("impact"), PROBLEM_PRIORITIES, "impact", default="medium"),
            urgency=validate_choice(payload.get("urgency"), PROBLEM_PRIORITIES, "urgency", default="medium"),
            source_kind=clean_text(payload.get("source_kind")) or "manual",
            source_ref=clean_text(payload.get("source_ref")),
            service_code=clean_text(payload.get("service_code")),
            offering_code=clean_text(payload.get("offering_code")),
            request_type=clean_text(payload.get("request_type")),
            reporting_category=clean_text(payload.get("reporting_category")),
            owner_id=clean_text(payload.get("owner_id") or payload.get("owner_actor_id") or actor_id),
            owner_actor_id=clean_text(payload.get("owner_actor_id") or payload.get("owner_id") or actor_id),
            assignee_actor_id=clean_text(payload.get("assignee_actor_id")),
            queue_id=payload.get("queue_id"),
            opened_at=now,
            detected_at=now,
            root_cause_summary=clean_text(payload.get("root_cause_summary")),
            workaround_summary=clean_text(payload.get("workaround_summary")),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await ProblemSLOService(self.session).apply_due_dates(row, now=now)
        await self.session.flush()
        await self._activity(problem_id=row.problem_id, event_type="problem_created", actor_id=actor_id, payload={"status": row.status})
        return problem_to_dict(row)

    async def get_problem(self, problem_id_or_key: str) -> dict[str, Any]:
        row = await self._get_problem_row(problem_id_or_key)
        return problem_to_dict(row)

    async def list_problems(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(Problem).order_by(Problem.updated_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Problem.status == normalize_problem_status(status))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [problem_to_dict(row) for row in rows]

    async def transition_problem(self, problem_id_or_key: str, new_status: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get_problem_row(problem_id_or_key)
        status = normalize_problem_status(new_status)
        if status != row.status and not can_transition_problem(row.status, status):
            raise ValueError("problem status transition is invalid")
        now = datetime.now(timezone.utc)
        if status == "known_error" and not (clean_text(payload.get("root_cause_summary")) or row.root_cause_summary or row.root_cause):
            raise ValueError("root cause summary is required before known_error")
        if status == "workaround_available" and not (clean_text(payload.get("workaround_summary")) or row.workaround_summary or row.workaround):
            raise ValueError("workaround summary is required before workaround_available")
        if status == "resolved":
            validate_problem_resolution_payload({**payload, "root_cause_summary": payload.get("root_cause_summary") or row.root_cause_summary or row.root_cause})
        if status == "closed" and not (clean_text(payload.get("closure_summary")) or row.closure_summary):
            raise ValueError("closure summary is required before closed")
        previous = row.status
        row.status = status
        row.updated_at = now
        row.updated_by = actor_id
        self._apply_text_updates(row, payload)
        if status == "investigating" and row.investigation_started_at is None:
            row.investigation_started_at = now
        if status == "known_error" and row.known_error_at is None:
            row.known_error_at = now
        if status == "workaround_available" and row.workaround_available_at is None:
            row.workaround_available_at = now
        if status == "permanent_fix_planned" and row.permanent_fix_planned_at is None:
            row.permanent_fix_planned_at = now
        if status == "permanent_fix_in_progress" and row.permanent_fix_in_progress_at is None:
            row.permanent_fix_in_progress_at = now
        if status == "resolved" and row.resolved_at is None:
            row.resolved_at = now
        if status == "closed" and row.closed_at is None:
            row.closed_at = now
        if status == "canceled" and row.canceled_at is None:
            row.canceled_at = now
        ProblemSLOService(self.session).refresh_breached_milestones(row, now=now)
        await self.session.flush()
        await self._activity(problem_id=row.problem_id, event_type="status_changed", actor_id=actor_id, payload={"from": previous, "to": status})
        return problem_to_dict(row)

    async def link_ticket(
        self,
        problem_id_or_key: str,
        ticket_id: str,
        *,
        link_type: str = "suspected",
        evidence_summary: str | None = None,
        actor_id: str | None,
    ) -> dict[str, Any]:
        problem = await self._get_problem_row(problem_id_or_key)
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("ticket not found")
        existing = (
            await self.session.execute(
                select(ProblemTicketLink).where(
                    ProblemTicketLink.problem_id == problem.problem_id,
                    ProblemTicketLink.ticket_id == ticket_id,
                    ProblemTicketLink.link_type == link_type,
                    ProblemTicketLink.unlinked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return ticket_link_to_dict(existing)
        row = ProblemTicketLink(
            link_id=str(uuid.uuid4()),
            problem_id=problem.problem_id,
            ticket_id=ticket_id,
            link_type=link_type,
            evidence_summary=clean_text(evidence_summary),
            linked_by_actor_id=actor_id,
            linked_by=actor_id or "system",
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(problem_id=problem.problem_id, event_type="ticket_linked", actor_id=actor_id, payload={"ticket_id": ticket_id, "link_type": link_type})
        return ticket_link_to_dict(row)

    async def unlink_ticket(self, problem_id_or_key: str, ticket_id: str, *, actor_id: str | None) -> dict[str, Any]:
        problem = await self._get_problem_row(problem_id_or_key)
        row = (
            await self.session.execute(
                select(ProblemTicketLink).where(
                    ProblemTicketLink.problem_id == problem.problem_id,
                    ProblemTicketLink.ticket_id == ticket_id,
                    ProblemTicketLink.unlinked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return {"unlinked": False}
        row.unlinked_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._activity(problem_id=problem.problem_id, event_type="ticket_unlinked", actor_id=actor_id, payload={"ticket_id": ticket_id})
        return {"unlinked": True}

    async def list_ticket_problems(self, ticket_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(Problem, ProblemTicketLink)
                .join(ProblemTicketLink, Problem.problem_id == ProblemTicketLink.problem_id)
                .where(ProblemTicketLink.ticket_id == ticket_id, ProblemTicketLink.unlinked_at.is_(None))
                .order_by(ProblemTicketLink.linked_at.desc())
            )
        ).all()
        return [{"problem": problem_to_dict(problem), "link": ticket_link_to_dict(link)} for problem, link in rows]

    async def list_problem_ticket_links(self, problem_id_or_key: str) -> list[dict[str, Any]]:
        problem = await self._get_problem_row(problem_id_or_key)
        rows = (
            await self.session.execute(
                select(ProblemTicketLink)
                .where(ProblemTicketLink.problem_id == problem.problem_id, ProblemTicketLink.unlinked_at.is_(None))
                .order_by(ProblemTicketLink.linked_at.desc())
            )
        ).scalars().all()
        return [ticket_link_to_dict(row) for row in rows]

    async def add_affected_object(self, problem_id_or_key: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        problem = await self._get_problem_row(problem_id_or_key)
        object_type = clean_text(payload.get("object_type"))
        object_ref = clean_text(payload.get("object_ref"))
        if not object_type or not object_ref:
            raise ValueError("object_type and object_ref are required")
        row = ProblemAffectedObject(
            affected_id=str(uuid.uuid4()),
            problem_id=problem.problem_id,
            object_type=object_type,
            object_ref=object_ref,
            service_code=clean_text(payload.get("service_code") or problem.service_code),
            offering_code=clean_text(payload.get("offering_code") or problem.offering_code),
            impact=validate_choice(payload.get("impact"), PROBLEM_PRIORITIES, "impact", default="medium"),
            created_by=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(problem_id=problem.problem_id, event_type="affected_object_linked", actor_id=actor_id, payload={"object_type": object_type, "object_ref": object_ref})
        return {"affected_id": row.affected_id, "object_type": row.object_type, "object_ref": row.object_ref}

    async def create_improvement_action(self, problem_id_or_key: str, *, action_type: str, title: str, actor_id: str | None) -> dict[str, Any]:
        problem = await self._get_problem_row(problem_id_or_key)
        row = ContinuousImprovementAction(
            action_id=str(uuid.uuid4()),
            source_kind="problem",
            source_ref=problem.problem_key,
            problem_id=problem.problem_id,
            service_code=problem.service_code,
            offering_code=problem.offering_code,
            action_type=action_type,
            title=title,
            description=title,
            status="open",
            priority=problem.priority if problem.priority in PROBLEM_PRIORITIES else "medium",
            created_by=actor_id,
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(problem_id=problem.problem_id, event_type="improvement_action_created", actor_id=actor_id, payload={"action_id": row.action_id, "action_type": action_type})
        return {"action_id": row.action_id, "source_kind": row.source_kind, "problem_id": row.problem_id, "action_type": row.action_type}

    async def _get_problem_row(self, problem_id_or_key: str) -> Problem:
        row = (
            await self.session.execute(
                select(Problem).where(or_(Problem.problem_id == problem_id_or_key, Problem.problem_key == problem_id_or_key))
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("problem not found")
        return row

    async def _next_problem_key(self) -> str:
        count = (await self.session.execute(select(func.count(Problem.problem_id)))).scalar_one()
        return f"PRB-{int(count) + 1:06d}"

    async def _validate_service_offering(self, service_code: Any, offering_code: Any) -> None:
        service = clean_text(service_code)
        offering = clean_text(offering_code)
        if not service and not offering:
            return
        has_catalog_rows = (await self.session.execute(select(func.count(HelpdeskService.service_id)))).scalar_one()
        if not has_catalog_rows:
            return
        if service:
            exists = (await self.session.execute(select(HelpdeskService).where(HelpdeskService.code == service))).scalar_one_or_none()
            if exists is None:
                raise ValueError("service_code is invalid")
        if offering:
            exists = (
                await self.session.execute(
                    select(HelpdeskServiceOffering).where(
                        and_(HelpdeskServiceOffering.full_code == offering, HelpdeskServiceOffering.service_id == HelpdeskService.service_id)
                    ).join(HelpdeskService, HelpdeskService.service_id == HelpdeskServiceOffering.service_id)
                )
            ).scalar_one_or_none()
            if exists is None:
                raise ValueError("offering_code is invalid")

    def _apply_text_updates(self, row: Problem, payload: dict[str, Any]) -> None:
        for field in ("root_cause_summary", "workaround_summary", "permanent_fix_summary", "closure_summary", "root_cause_category"):
            if field in payload:
                setattr(row, field, clean_text(payload.get(field)))
        if row.root_cause_summary:
            row.root_cause = row.root_cause_summary
        if row.workaround_summary:
            row.workaround = row.workaround_summary

    async def _activity(self, *, problem_id: str | None = None, candidate_id: str | None = None, event_type: str, actor_id: str | None, payload: dict[str, Any] | None = None) -> None:
        self.session.add(
            ProblemActivityEvent(
                event_id=str(uuid.uuid4()),
                problem_id=problem_id,
                candidate_id=candidate_id,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload or {},
            )
        )
        await self.session.flush()
