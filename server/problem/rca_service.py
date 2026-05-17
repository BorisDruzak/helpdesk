from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import Problem, ProblemActivityEvent, ProblemRCARecord
from problem.contracts import PROBLEM_RCA_METHODOLOGIES, clean_text, validate_choice
from problem.serializers import rca_to_dict


class RCAService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_draft(self, problem_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        problem = await self.session.get(Problem, problem_id)
        if problem is None:
            raise ValueError("problem not found")
        statement = clean_text(payload.get("problem_statement"))
        root_cause = clean_text(payload.get("root_cause"))
        if not statement:
            raise ValueError("problem_statement is required")
        if not root_cause:
            raise ValueError("root_cause is required")
        version = (
            await self.session.execute(
                select(func.coalesce(func.max(ProblemRCARecord.version_number), 0)).where(ProblemRCARecord.problem_id == problem_id)
            )
        ).scalar_one()
        row = ProblemRCARecord(
            rca_id=str(uuid.uuid4()),
            problem_id=problem_id,
            version_number=int(version) + 1,
            status="draft",
            methodology=validate_choice(payload.get("methodology"), PROBLEM_RCA_METHODOLOGIES, "methodology", default="narrative"),
            problem_statement=statement,
            impact_summary=clean_text(payload.get("impact_summary")),
            timeline_json=payload.get("timeline") if isinstance(payload.get("timeline"), list) else [],
            contributing_factors_json=payload.get("contributing_factors") if isinstance(payload.get("contributing_factors"), list) else [],
            root_cause=root_cause,
            root_cause_category=clean_text(payload.get("root_cause_category")),
            evidence_refs_json=payload.get("evidence_refs") if isinstance(payload.get("evidence_refs"), list) else [],
            corrective_actions_json=payload.get("corrective_actions") if isinstance(payload.get("corrective_actions"), list) else [],
            preventive_actions_json=payload.get("preventive_actions") if isinstance(payload.get("preventive_actions"), list) else [],
            created_by=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(problem_id=problem_id, event_type="rca_created", actor_id=actor_id, payload={"rca_id": row.rca_id})
        return rca_to_dict(row)

    async def submit_review(self, problem_id: str, rca_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(problem_id, rca_id)
        row.status = "in_review"
        row.reviewer_actor_id = actor_id
        row.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return rca_to_dict(row)

    async def approve(self, problem_id: str, rca_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(problem_id, rca_id)
        row.status = "approved"
        row.approved_by_actor_id = actor_id
        row.approved_at = datetime.now(timezone.utc)
        problem = await self.session.get(Problem, problem_id)
        if problem is not None:
            problem.root_cause_summary = row.root_cause
            problem.root_cause = row.root_cause
            problem.root_cause_category = row.root_cause_category
        await self.session.flush()
        await self._activity(problem_id=problem_id, event_type="rca_approved", actor_id=actor_id, payload={"rca_id": row.rca_id})
        return rca_to_dict(row)

    async def reject(self, problem_id: str, rca_id: str, *, actor_id: str | None, reason: str | None = None) -> dict[str, Any]:
        row = await self._get(problem_id, rca_id)
        row.status = "rejected"
        row.reviewer_actor_id = actor_id
        row.reviewed_at = datetime.now(timezone.utc)
        row.metadata_json = {**(row.metadata_json or {}), "rejection_reason": clean_text(reason)}
        await self.session.flush()
        return rca_to_dict(row)

    async def _get(self, problem_id: str, rca_id: str) -> ProblemRCARecord:
        row = (
            await self.session.execute(
                select(ProblemRCARecord).where(ProblemRCARecord.problem_id == problem_id, ProblemRCARecord.rca_id == rca_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("rca not found")
        return row

    async def _activity(self, *, problem_id: str, event_type: str, actor_id: str | None, payload: dict[str, Any]) -> None:
        self.session.add(
            ProblemActivityEvent(
                event_id=str(uuid.uuid4()),
                problem_id=problem_id,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload,
            )
        )
        await self.session.flush()
