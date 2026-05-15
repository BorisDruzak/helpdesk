from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketResolutionPassport
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.graph_service import KnowledgeGraphService


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    return text or "resolution-draft"


def _passport_body(ticket: Ticket, passport: TicketResolutionPassport) -> str:
    sections = [
        ("Problem", passport.problem_summary or ticket.description),
        ("Applies to", f"service={ticket.service_code or 'unknown'}, offering={ticket.offering_code or 'unknown'}"),
        ("Symptoms", passport.problem_summary),
        ("Checks", passport.operator_checks_summary or passport.automated_checks_summary),
        ("Resolution", passport.user_result_summary or passport.changes_made_summary),
        ("Evidence", passport.evidence_summary),
        ("When to escalate", passport.repeat_guidance),
        ("Source ticket/passport", f"{ticket.ticket_id} / passport {passport.id}"),
    ]
    return "\n\n".join(f"## {title}\n\n{body}" for title, body in sections if body)


class KnowledgePassportDraftService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_draft_from_ticket(self, ticket_id: str, *, item_type: str = "article", actor_id: str | None) -> dict[str, Any]:
        ticket = (await self.session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
        if ticket is None:
            raise ValueError("ticket not found")
        passport = (
            await self.session.execute(
                select(TicketResolutionPassport)
                .where(TicketResolutionPassport.ticket_id == ticket_id)
                .order_by(TicketResolutionPassport.version.desc())
            )
        ).scalar_one_or_none()
        if passport is None:
            raise ValueError("ticket passport not found")
        repo = KnowledgeRepo(self.session)
        await repo.upsert_space(
            {
                "code": "it-support",
                "title": "IT Support",
                "visibility": "support_internal",
                "lifecycle_status": "active",
            },
            actor_id=actor_id,
        )
        warnings: list[str] = []
        source_payload = passport.source_payload if isinstance(passport.source_payload, dict) else {}
        passport_stale = bool(source_payload.get("stale") or source_payload.get("stale_reasons"))
        if passport_stale:
            warnings.append("Passport is stale and must be reviewed before publication.")
        item = await repo.create_item_draft(
            {
                "space_code": "it-support",
                "slug": f"{_slug(ticket.ticket_id)}-knowledge-draft",
                "item_type": item_type,
                "title": f"Draft from {ticket.ticket_code or ticket.ticket_id}: {ticket.title}",
                "summary": passport.user_result_summary or passport.problem_summary,
                "visibility": "support_internal",
                "source_kind": "ticket_passport",
                "source_ticket_id": ticket.ticket_id,
                "source_passport_id": passport.id,
                "owner_actor_id": actor_id,
                "reviewer_actor_id": actor_id,
                "metadata": {
                    "warnings": warnings,
                    "passport_stale": passport_stale,
                    "review_required": True,
                    "publish_blockers": (
                        [
                            {
                                "severity": "error",
                                "code": "stale_passport",
                                "message": "Stale passport source must be reviewed and acknowledged before publication.",
                            }
                        ]
                        if passport_stale
                        else []
                    ),
                },
            },
            actor_id=actor_id,
            actor_role="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": item["title"],
                "summary": item.get("summary"),
                "body_format": "markdown",
                "body": _passport_body(ticket, passport),
                "change_summary": "Draft from resolution passport",
                "source_refs": [{"ticket_id": ticket.ticket_id, "passport_id": passport.id, "created_at": datetime.now(timezone.utc).isoformat()}],
            },
            actor_id=actor_id,
            actor_role="support",
        )
        bindings = []
        bindings.append(
            await repo.add_binding(
                item["item_id"],
                {
                    "service_code": ticket.service_code,
                    "offering_code": ticket.offering_code,
                    "ticket_type": ticket.request_type or ticket.ticket_type,
                    "reporting_category": ticket.reporting_category,
                },
                actor_id=actor_id,
                actor_role="support",
            )
        )
        await KnowledgeGraphService(self.session).ensure_item_binding_edges(
            item["item_id"],
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            actor_id=actor_id,
        )
        await KnowledgeFeedbackService(self.session).record_event(
            {
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "event_type": "draft_created",
                "ticket_id": ticket.ticket_id,
                "service_code": ticket.service_code,
                "offering_code": ticket.offering_code,
                "surface": "support_workspace",
            },
            actor_role="support",
            actor_id=actor_id,
        )
        return {"item": item, "version": version, "bindings": bindings, "warnings": warnings}
