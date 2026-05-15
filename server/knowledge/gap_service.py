from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import hashlib
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HelpdeskService, HelpdeskServiceOffering, KnowledgeBinding, KnowledgeFeedbackEvent, KnowledgeGapFinding, KnowledgeItem, Ticket
from app.repos.knowledge_repo import KnowledgeRepo, serialize_item
from knowledge.content_templates import default_visibility_for_item_type
from knowledge.review_task_service import KnowledgeReviewTaskService


def _new_id() -> str:
    return str(uuid.uuid4())


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def serialize_gap_finding(row: KnowledgeGapFinding) -> dict[str, Any]:
    return {
        "finding_id": row.finding_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "request_template_key": row.request_template_key,
        "gap_type": row.gap_type,
        "severity": row.severity,
        "status": row.status,
        "evidence": row.evidence_json or {},
        "evidence_hash": row.evidence_hash,
        "suggested_action": row.suggested_action,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "resolved_at": _iso(row.resolved_at),
        "metadata": row.metadata_json or {},
    }


class KnowledgeGapService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def recompute(self, *, actor_id: str | None) -> dict[str, Any]:
        services = (
            await self.session.execute(
                select(HelpdeskService).where(HelpdeskService.lifecycle_status == "published", HelpdeskService.visibility == "public")
            )
        ).scalars().all()
        offerings = (
            await self.session.execute(
                select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.lifecycle_status == "published", HelpdeskServiceOffering.visibility == "public")
            )
        ).scalars().all()
        service_by_id = {row.service_id: row for row in services}
        findings: list[dict[str, Any]] = []
        for offering in offerings:
            service = service_by_id.get(offering.service_id)
            if service is None:
                continue
            ticket_count = int(
                (
                    await self.session.execute(
                        select(func.count(Ticket.ticket_id)).where(Ticket.service_code == service.code, Ticket.offering_code == offering.full_code)
                    )
                ).scalar_one()
            )
            not_helpful = await self._feedback_count(service.code, offering.full_code, "not_helpful")
            ticket_created_after_view = await self._feedback_count(service.code, offering.full_code, "ticket_created_after_view")
            if not await self._has_binding(service.code, offering.full_code, ("public", "requester", "agent_requester_safe")):
                findings.append(
                    await self._upsert_finding(
                        service_code=service.code,
                        offering_code=offering.full_code,
                        request_template_key=offering.request_template_key,
                        gap_type="no_requester_article",
                        severity="high" if ticket_count else "medium",
                        evidence={
                            "ticket_count": ticket_count,
                            "ticket_created_after_view_count": ticket_created_after_view,
                            "not_helpful_count": not_helpful,
                            "service_title": service.public_title or service.name,
                            "offering_title": offering.public_title or offering.name,
                        },
                        suggested_action="Create requester-safe article or FAQ.",
                        actor_id=actor_id,
                    )
                )
            if not await self._has_binding(service.code, offering.full_code, ("support_internal",)):
                findings.append(
                    await self._upsert_finding(
                        service_code=service.code,
                        offering_code=offering.full_code,
                        request_template_key=offering.request_template_key,
                        gap_type="no_support_runbook",
                        severity="medium",
                        evidence={"ticket_count": ticket_count},
                        suggested_action="Create support-internal runbook.",
                        actor_id=actor_id,
                    )
                )
            if ticket_count >= 3 and not await self._has_binding(service.code, offering.full_code, ("public", "requester", "agent_requester_safe")):
                findings.append(
                    await self._upsert_finding(
                        service_code=service.code,
                        offering_code=offering.full_code,
                        request_template_key=offering.request_template_key,
                        gap_type="high_volume_no_kb",
                        severity="high",
                        evidence={"ticket_count": ticket_count},
                        suggested_action="Prioritize requester article and support runbook.",
                        actor_id=actor_id,
                    )
                )
            if not_helpful >= 3:
                findings.append(
                    await self._upsert_finding(
                        service_code=service.code,
                        offering_code=offering.full_code,
                        request_template_key=offering.request_template_key,
                        gap_type="high_not_helpful",
                        severity="high",
                        evidence={"not_helpful_count": not_helpful},
                        suggested_action="Review weak article usefulness.",
                        actor_id=actor_id,
                    )
                )
        findings = [finding for finding in findings if finding]
        return {"findings": findings, "count": len(findings)}

    async def _has_binding(self, service_code: str, offering_code: str, visibilities: tuple[str, ...]) -> bool:
        row = (
            await self.session.execute(
                select(KnowledgeItem.item_id)
                .join(KnowledgeBinding, KnowledgeBinding.item_id == KnowledgeItem.item_id)
                .where(
                    KnowledgeItem.status == "published",
                    KnowledgeItem.visibility.in_(visibilities),
                    KnowledgeBinding.service_code == service_code,
                    KnowledgeBinding.offering_code == offering_code,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _feedback_count(self, service_code: str, offering_code: str, event_type: str) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(KnowledgeFeedbackEvent.event_id)).where(
                        KnowledgeFeedbackEvent.service_code == service_code,
                        KnowledgeFeedbackEvent.offering_code == offering_code,
                        KnowledgeFeedbackEvent.event_type == event_type,
                    )
                )
            ).scalar_one()
        )

    async def _upsert_finding(
        self,
        *,
        service_code: str | None,
        offering_code: str | None,
        request_template_key: str | None,
        gap_type: str,
        severity: str,
        evidence: dict[str, Any],
        suggested_action: str,
        actor_id: str | None,
    ) -> dict[str, Any]:
        evidence_hash = _hash(evidence)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        dismissed = (
            await self.session.execute(
                select(KnowledgeGapFinding).where(
                    KnowledgeGapFinding.service_code == service_code,
                    KnowledgeGapFinding.offering_code == offering_code,
                    KnowledgeGapFinding.request_template_key == request_template_key,
                    KnowledgeGapFinding.gap_type == gap_type,
                    KnowledgeGapFinding.evidence_hash == evidence_hash,
                    KnowledgeGapFinding.status == "dismissed",
                    KnowledgeGapFinding.updated_at >= recent_cutoff,
                )
            )
        ).scalar_one_or_none()
        if dismissed is not None:
            return {}
        row = (
            await self.session.execute(
                select(KnowledgeGapFinding).where(
                    KnowledgeGapFinding.service_code == service_code,
                    KnowledgeGapFinding.offering_code == offering_code,
                    KnowledgeGapFinding.request_template_key == request_template_key,
                    KnowledgeGapFinding.gap_type == gap_type,
                    KnowledgeGapFinding.evidence_hash == evidence_hash,
                )
            )
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = KnowledgeGapFinding(
                finding_id=_new_id(),
                service_code=service_code,
                offering_code=offering_code,
                request_template_key=request_template_key,
                gap_type=gap_type,
                severity=severity,
                status="open",
                evidence_json=evidence,
                evidence_hash=evidence_hash,
                suggested_action=suggested_action,
                created_at=now,
                updated_at=now,
                metadata_json={"created_by": actor_id},
            )
            self.session.add(row)
        elif row.status != "dismissed":
            row.status = "open" if row.status == "resolved" else row.status
            row.severity = severity
            row.evidence_json = evidence
            row.suggested_action = suggested_action
            row.updated_at = now
        await self.session.flush()
        return serialize_gap_finding(row)

    async def dismiss(self, finding_id: str, *, actor_id: str | None, reason: str | None) -> dict[str, Any]:
        row = (await self.session.execute(select(KnowledgeGapFinding).where(KnowledgeGapFinding.finding_id == finding_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("knowledge gap finding not found")
        row.status = "dismissed"
        row.updated_at = datetime.now(timezone.utc)
        row.metadata_json = {**(row.metadata_json or {}), "dismissed_by": actor_id, "dismiss_reason": reason}
        await self.session.flush()
        return serialize_gap_finding(row)

    async def create_draft(self, finding_id: str, *, actor_id: str | None, item_type: str = "article") -> dict[str, Any]:
        row = (await self.session.execute(select(KnowledgeGapFinding).where(KnowledgeGapFinding.finding_id == finding_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("knowledge gap finding not found")
        repo = KnowledgeRepo(self.session)
        space_code = "it-self-service" if default_visibility_for_item_type(item_type) in {"requester", "public"} else "it-support"
        await repo.upsert_space(
            {
                "code": space_code,
                "title": "Knowledge Ops Drafts",
                "visibility": default_visibility_for_item_type(item_type),
                "lifecycle_status": "active",
                "owner_actor_id": actor_id,
                "default_reviewer_actor_id": actor_id,
            },
            actor_id=actor_id,
        )
        slug = f"{row.gap_type}-{(row.offering_code or row.service_code or row.finding_id).replace('.', '-')}"
        item = await repo.create_item_draft(
            {
                "space_code": space_code,
                "slug": slug[:118].strip("-"),
                "item_type": item_type,
                "title": f"Draft for {row.offering_code or row.service_code or row.gap_type}",
                "summary": "Draft created from a knowledge gap finding.",
                "visibility": default_visibility_for_item_type(item_type),
                "owner_actor_id": actor_id,
                "reviewer_actor_id": actor_id,
                "source_kind": "manual",
                "source_ref": f"knowledge_gap:{finding_id}",
                "metadata": {"gap_finding_id": finding_id, "gap_type": row.gap_type},
            },
            actor_id=actor_id,
            actor_role="admin",
        )
        await repo.create_version(
            item["item_id"],
            {
                "title": item["title"],
                "summary": item["summary"],
                "body_format": "markdown",
                "body": "# Draft\n\nFill this content during review.",
                "source_refs": [{"knowledge_gap": finding_id}],
            },
            actor_id=actor_id,
            actor_role="admin",
        )
        if row.service_code or row.offering_code:
            await repo.add_binding(
                item["item_id"],
                {"service_code": row.service_code, "offering_code": row.offering_code, "request_template_key": row.request_template_key},
                actor_id=actor_id,
                actor_role="admin",
            )
        task = await KnowledgeReviewTaskService(self.session).create_task(
            item_id=item["item_id"],
            task_type="gap_candidate",
            severity="warning",
            reason="Draft created from knowledge gap finding.",
            suggested_action="Review draft and complete required template sections.",
            actor_id=actor_id,
            source_kind="knowledge_gap",
            source_ref=finding_id,
            metadata={"gap_type": row.gap_type},
        )
        row.status = "accepted"
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return {"item": serialize_item(await repo.get_item_row(item["item_id"])), "review_task": task["task"]}
