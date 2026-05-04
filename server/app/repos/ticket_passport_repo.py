from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    TicketActionLog,
    TicketApproval,
    TicketEvidenceItem,
    TicketRelatedObject,
    TicketResolutionPassport,
)


class TicketPassportRepo:
    """Repository for ticket resolution passport facts and snapshots."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_passport(self, ticket_id: str) -> TicketResolutionPassport | None:
        result = await self.session.execute(
            select(TicketResolutionPassport)
            .where(TicketResolutionPassport.ticket_id == ticket_id)
            .order_by(TicketResolutionPassport.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_passport_version(
        self,
        *,
        ticket_id: str,
        generated_by: str | None,
        sections: dict[str, Any],
        source_payload: dict[str, Any],
    ) -> TicketResolutionPassport:
        max_version = await self.session.scalar(
            select(func.max(TicketResolutionPassport.version)).where(TicketResolutionPassport.ticket_id == ticket_id)
        )
        now = datetime.now(timezone.utc)
        passport = TicketResolutionPassport(
            ticket_id=ticket_id,
            version=int(max_version or 0) + 1,
            status="draft",
            summary_source=str(source_payload.get("summary_source") or "deterministic"),
            requester_summary=sections.get("requester"),
            problem_summary=sections.get("problem"),
            affected_object_summary=sections.get("affected_object"),
            automated_checks_summary=sections.get("automated_checks"),
            operator_checks_summary=sections.get("operator_checks"),
            changes_made_summary=sections.get("changes_made"),
            approvals_summary=sections.get("approvals"),
            evidence_summary=sections.get("evidence"),
            user_result_summary=sections.get("user_result"),
            internal_result_summary=sections.get("internal_result"),
            repeat_guidance=sections.get("repeat_guidance"),
            source_event_ids=source_payload.get("source_event_ids") or [],
            source_operation_ids=source_payload.get("source_operation_ids") or [],
            source_payload=source_payload,
            generated_by=generated_by,
            generated_at=now,
            updated_by=generated_by,
            updated_at=now,
        )
        self.session.add(passport)
        await self.session.flush()
        return passport

    async def update_passport_sections(
        self,
        passport: TicketResolutionPassport,
        *,
        updated_by: str | None,
        sections: dict[str, Any],
    ) -> TicketResolutionPassport:
        mapping = {
            "operator_check_summary": "operator_checks_summary",
            "operator_checks_summary": "operator_checks_summary",
            "changes_made_summary": "changes_made_summary",
            "repeat_guidance": "repeat_guidance",
            "user_result_summary": "user_result_summary",
            "internal_result_summary": "internal_result_summary",
        }
        for key, attr in mapping.items():
            if key in sections:
                setattr(passport, attr, sections[key])
        passport.updated_by = updated_by
        passport.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return passport

    async def list_evidence(self, ticket_id: str) -> list[TicketEvidenceItem]:
        result = await self.session.execute(
            select(TicketEvidenceItem)
            .where(TicketEvidenceItem.ticket_id == ticket_id)
            .order_by(TicketEvidenceItem.created_at.desc(), TicketEvidenceItem.id.desc())
        )
        return list(result.scalars().all())

    async def add_evidence(
        self,
        *,
        ticket_id: str,
        passport_id: int | None,
        evidence_type: str,
        source_ref: str | None,
        source_kind: str | None = None,
        source_id: str | None = None,
        required_fact: str | None = None,
        section_key: str | None = None,
        artifact_id: str | None = None,
        title: str,
        summary: str | None,
        visibility: str,
        verification_status: str = "unverified",
        verified_by: str | None = None,
        verified_at: datetime | None = None,
        captured_at: datetime | None = None,
        public_summary: str | None = None,
        internal_summary: str | None = None,
        metadata_json: dict[str, Any] | None = None,
        export_visibility: str = "internal",
        created_by: str | None,
    ) -> TicketEvidenceItem:
        if source_kind and source_id:
            existing = await self.session.scalar(
                select(TicketEvidenceItem)
                .where(
                    TicketEvidenceItem.ticket_id == ticket_id,
                    TicketEvidenceItem.evidence_type == evidence_type,
                    TicketEvidenceItem.source_kind == source_kind,
                    TicketEvidenceItem.source_id == source_id,
                    TicketEvidenceItem.required_fact == required_fact,
                )
                .limit(1)
            )
            if existing is not None:
                return existing

        item = TicketEvidenceItem(
            ticket_id=ticket_id,
            passport_id=passport_id,
            evidence_type=evidence_type,
            source_ref=source_ref,
            source_kind=source_kind,
            source_id=source_id,
            required_fact=required_fact,
            section_key=section_key,
            artifact_id=artifact_id,
            title=title,
            summary=summary,
            visibility=visibility,
            verification_status=verification_status,
            verified_by=verified_by,
            verified_at=verified_at,
            captured_at=captured_at,
            public_summary=public_summary,
            internal_summary=internal_summary,
            metadata_json=metadata_json or {},
            export_visibility=export_visibility,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_actions(self, ticket_id: str) -> list[TicketActionLog]:
        result = await self.session.execute(
            select(TicketActionLog)
            .where(TicketActionLog.ticket_id == ticket_id)
            .order_by(TicketActionLog.created_at.asc(), TicketActionLog.id.asc())
        )
        return list(result.scalars().all())

    async def replace_generated_actions(
        self,
        *,
        ticket_id: str,
        passport_id: int,
        actions: list[dict[str, Any]],
    ) -> None:
        await self.session.execute(
            delete(TicketActionLog).where(
                TicketActionLog.ticket_id == ticket_id,
                TicketActionLog.passport_id == passport_id,
            )
        )
        for action in actions:
            self.session.add(
                TicketActionLog(
                    ticket_id=ticket_id,
                    passport_id=passport_id,
                    action_type=str(action.get("action_type") or "event"),
                    actor_id=action.get("actor_id"),
                    source_event_id=action.get("source_event_id"),
                    operation_id=action.get("operation_id"),
                    title=str(action.get("title") or "Действие"),
                    summary=action.get("summary"),
                    started_at=action.get("started_at"),
                    finished_at=action.get("finished_at"),
                    created_at=action.get("created_at") or datetime.now(timezone.utc),
                )
            )
        await self.session.flush()

    async def list_approvals(self, ticket_id: str) -> list[TicketApproval]:
        result = await self.session.execute(
            select(TicketApproval)
            .where(TicketApproval.ticket_id == ticket_id)
            .order_by(TicketApproval.requested_at.asc(), TicketApproval.id.asc())
        )
        return list(result.scalars().all())

    async def list_related_objects(self, ticket_id: str) -> list[TicketRelatedObject]:
        result = await self.session.execute(
            select(TicketRelatedObject)
            .where(TicketRelatedObject.ticket_id == ticket_id)
            .order_by(TicketRelatedObject.created_at.asc(), TicketRelatedObject.id.asc())
        )
        return list(result.scalars().all())

    async def replace_related_objects(
        self,
        *,
        ticket_id: str,
        passport_id: int,
        objects: list[dict[str, Any]],
    ) -> None:
        await self.session.execute(delete(TicketRelatedObject).where(TicketRelatedObject.ticket_id == ticket_id))
        for obj in objects:
            self.session.add(
                TicketRelatedObject(
                    ticket_id=ticket_id,
                    passport_id=passport_id,
                    object_type=str(obj["object_type"]),
                    object_ref=str(obj["object_ref"]),
                    display_name=obj.get("display_name"),
                    relation_type=str(obj.get("relation_type") or "affected"),
                    source=str(obj.get("source") or "snapshot"),
                    created_at=datetime.now(timezone.utc),
                )
            )
        await self.session.flush()
