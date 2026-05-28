from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select

from app.db.models import (
    Change,
    ChangeActivityEvent,
    ChangeAffectedObject,
    ChangePIRRecord,
    ChangePlan,
    ChangeRiskAssessment,
    ChangeTask,
    ContinuousImprovementAction,
    HelpdeskService,
    HelpdeskServiceOffering,
    Problem,
    ProblemActivityEvent,
    ProblemAffectedObject,
)
from change.approval_service import ChangeApprovalService
from change.contracts import (
    CHANGE_CATEGORIES,
    CHANGE_LEVELS,
    CHANGE_SOURCE_KINDS,
    CHANGE_TYPES,
    can_transition_change,
    clean_text,
    normalize_change_status,
    validate_change_approval_payload,
    validate_choice,
)
from change.policy_service import ChangePolicyService
from change.serializers import affected_object_to_dict, change_to_dict


class ChangeService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_change(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        title = clean_text(payload.get("title"))
        description = clean_text(payload.get("description"))
        if not title:
            raise ValueError("title is required")
        if not description:
            raise ValueError("description is required")
        await self._validate_service_offering(payload.get("service_code"), payload.get("offering_code"))
        now = datetime.now(timezone.utc)
        row = Change(
            change_id=str(uuid.uuid4()),
            change_key=await self._next_key(),
            title=title,
            description=description,
            change_type=validate_choice(payload.get("change_type"), CHANGE_TYPES, "change_type", default="normal"),
            status=normalize_change_status(payload.get("status") or "draft"),
            category=validate_choice(payload.get("category"), CHANGE_CATEGORIES, "category", default="other"),
            priority=validate_choice(payload.get("priority"), CHANGE_LEVELS, "priority", default="medium"),
            risk_level=validate_choice(payload.get("risk_level"), CHANGE_LEVELS, "risk_level", default="medium"),
            impact_level=validate_choice(payload.get("impact_level"), CHANGE_LEVELS, "impact_level", default="medium"),
            urgency=validate_choice(payload.get("urgency"), CHANGE_LEVELS, "urgency", default="medium"),
            source_kind=validate_choice(payload.get("source_kind"), CHANGE_SOURCE_KINDS, "source_kind", default="manual"),
            source_ref=clean_text(payload.get("source_ref")),
            problem_id=clean_text(payload.get("problem_id")),
            improvement_action_id=clean_text(payload.get("improvement_action_id")),
            service_code=clean_text(payload.get("service_code")),
            offering_code=clean_text(payload.get("offering_code")),
            request_type=clean_text(payload.get("request_type")),
            reporting_category=clean_text(payload.get("reporting_category")),
            owner_actor_id=clean_text(payload.get("owner_actor_id") or actor_id),
            assignee_actor_id=clean_text(payload.get("assignee_actor_id")),
            requested_by_actor_id=actor_id,
            emergency_justification=clean_text(payload.get("emergency_justification")),
            risk_summary=clean_text(payload.get("risk_summary")),
            impact_summary=clean_text(payload.get("impact_summary")),
            implementation_summary=clean_text(payload.get("implementation_summary")),
            rollback_summary=clean_text(payload.get("rollback_summary")),
            validation_summary=clean_text(payload.get("validation_summary")),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(row.change_id, "change_created", actor_id, {"status": row.status})
        return await self._change_dict(row)

    async def create_from_problem(self, problem_id: str, *, actor_id: str | None) -> dict[str, Any]:
        problem = await self.session.get(Problem, problem_id)
        if problem is None:
            raise ValueError("problem not found")
        change = await self.create_change(
            {
                "title": f"Permanent fix: {problem.title}",
                "description": problem.permanent_fix_summary or problem.description,
                "change_type": "normal",
                "source_kind": "problem",
                "source_ref": problem.problem_key,
                "problem_id": problem.problem_id,
                "service_code": problem.service_code,
                "offering_code": problem.offering_code,
                "request_type": problem.request_type,
                "reporting_category": problem.reporting_category,
                "priority": problem.priority,
                "impact_level": problem.impact,
                "risk_level": "high" if problem.severity in {"high", "critical"} else "medium",
            },
            actor_id=actor_id,
        )
        affected = (
            await self.session.execute(select(ProblemAffectedObject).where(ProblemAffectedObject.problem_id == problem.problem_id))
        ).scalars().all()
        for item in affected:
            self.session.add(
                ChangeAffectedObject(
                    affected_id=str(uuid.uuid4()),
                    change_id=change["change_id"],
                    object_type=item.object_type,
                    object_ref=item.object_ref,
                    service_code=item.service_code,
                    offering_code=item.offering_code,
                    impact=item.impact,
                    created_by=actor_id,
                    metadata_json={"source_problem_affected_id": item.affected_id},
                )
            )
        self.session.add(
            ProblemActivityEvent(
                event_id=str(uuid.uuid4()),
                problem_id=problem.problem_id,
                event_type="change_created",
                actor_id=actor_id,
                payload_json={"change_id": change["change_id"], "change_key": change["change_key"]},
            )
        )
        await self._activity(change["change_id"], "linked_problem", actor_id, {"problem_id": problem.problem_id})
        await self.session.flush()
        return await self.get_change(change["change_id"])

    async def create_from_improvement_action(self, action_id: str, *, actor_id: str | None) -> dict[str, Any]:
        action = await self.session.get(ContinuousImprovementAction, action_id)
        if action is None:
            raise ValueError("improvement action not found")
        change = await self.create_change(
            {
                "title": f"Change for action: {action.title}",
                "description": action.description or action.title,
                "change_type": "normal",
                "source_kind": "improvement_action",
                "source_ref": action.action_id,
                "improvement_action_id": action.action_id,
                "service_code": action.service_code,
                "offering_code": action.offering_code,
                "priority": action.priority,
            },
            actor_id=actor_id,
        )
        action.change_id = change["change_id"]
        action.updated_at = datetime.now(timezone.utc)
        await self._activity(change["change_id"], "linked_improvement_action", actor_id, {"action_id": action.action_id})
        await self.session.flush()
        return await self.get_change(change["change_id"])

    async def get_change(self, change_id_or_key: str) -> dict[str, Any]:
        row = await self._get_row(change_id_or_key)
        return await self._change_dict(row)

    async def list_changes(self, *, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(Change).order_by(Change.updated_at.desc()).limit(100)
        if status:
            stmt = stmt.where(Change.status == normalize_change_status(status))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [await self._change_dict(row) for row in rows]

    async def transition_change(self, change_id_or_key: str, new_status: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get_row(change_id_or_key)
        status = normalize_change_status(new_status)
        if status != row.status and not can_transition_change(row.status, status):
            raise ValueError("change status transition is invalid")
        if status == "awaiting_approval":
            await self._validate_assessment_ready(row)
        if status == "approved":
            await self._validate_approval_ready(row)
        if status == "implemented" and not bool(payload.get("override", False)):
            await self._validate_tasks_done(row.change_id)
        if status == "closed":
            if not clean_text(payload.get("closure_summary") or row.closure_summary):
                raise ValueError("closure summary is required")
            if row.status == "pir_required" and not await self._has_approved_pir(row.change_id):
                raise ValueError("approved PIR is required before closure")
        if status == "rolled_back" and not clean_text(payload.get("rollback_summary") or row.rollback_summary):
            raise ValueError("rollback summary is required")
        previous = row.status
        now = datetime.now(timezone.utc)
        row.status = "pir_required" if status == "implemented" and await self._requires_pir(row) else status
        row.updated_at = now
        row.updated_by = actor_id
        self._apply_payload(row, payload)
        if status == "submitted":
            row.submitted_at = row.submitted_at or now
        if status == "assessing":
            row.assessed_at = row.assessed_at or now
        if status == "approved":
            row.approved_at = row.approved_at or now
        if status == "implementation_in_progress":
            row.implementation_started_at = row.implementation_started_at or now
            row.actual_start_at = row.actual_start_at or now
        if status == "implemented":
            row.implemented_at = row.implemented_at or now
            row.actual_end_at = row.actual_end_at or now
        if status == "closed":
            row.closed_at = row.closed_at or now
        if status == "canceled":
            row.canceled_at = row.canceled_at or now
        if status == "failed":
            row.failed_at = row.failed_at or now
        if status in {"failed", "rolled_back"}:
            await self._create_failure_improvement_action(row, actor_id, status)
        await self.session.flush()
        await self._activity(row.change_id, "status_changed", actor_id, {"from": previous, "to": row.status})
        return await self._change_dict(row)

    async def force_status(self, change_id_or_key: str, status: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get_row(change_id_or_key)
        previous = row.status
        row.status = normalize_change_status(status)
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._activity(row.change_id, "status_changed", actor_id, {"from": previous, "to": row.status, "forced": True})
        return await self._change_dict(row)

    async def add_affected_object(self, change_id_or_key: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get_row(change_id_or_key)
        object_type = clean_text(payload.get("object_type"))
        object_ref = clean_text(payload.get("object_ref"))
        if not object_type or not object_ref:
            raise ValueError("object_type and object_ref are required")
        affected = ChangeAffectedObject(
            affected_id=str(uuid.uuid4()),
            change_id=row.change_id,
            object_type=object_type,
            object_ref=object_ref,
            service_code=clean_text(payload.get("service_code") or row.service_code),
            offering_code=clean_text(payload.get("offering_code") or row.offering_code),
            impact=validate_choice(payload.get("impact"), CHANGE_LEVELS, "impact", default="medium"),
            planned_downtime=bool(payload.get("planned_downtime", False)),
            notes=clean_text(payload.get("notes")),
            created_by=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(affected)
        await self.session.flush()
        return affected_object_to_dict(affected)

    async def _get_row(self, change_id_or_key: str) -> Change:
        row = (
            await self.session.execute(select(Change).where(or_(Change.change_id == change_id_or_key, Change.change_key == change_id_or_key)))
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("change not found")
        return row

    async def _next_key(self) -> str:
        count = (await self.session.execute(select(func.count(Change.change_id)))).scalar_one()
        return f"CHG-{int(count) + 1:06d}"

    async def _change_dict(self, row: Change) -> dict[str, Any]:
        affected = (await self.session.execute(select(ChangeAffectedObject).where(ChangeAffectedObject.change_id == row.change_id))).scalars().all()
        return change_to_dict(row, affected_objects=[affected_object_to_dict(item) for item in affected])

    async def _validate_service_offering(self, service_code: Any, offering_code: Any) -> None:
        service = clean_text(service_code)
        offering = clean_text(offering_code)
        if not service and not offering:
            return
        has_catalog_rows = (await self.session.execute(select(func.count(HelpdeskService.service_id)))).scalar_one()
        if not has_catalog_rows:
            return
        if service and (await self.session.execute(select(HelpdeskService).where(HelpdeskService.code == service))).scalar_one_or_none() is None:
            raise ValueError("service_code is invalid")
        if offering:
            exists = (
                await self.session.execute(
                    select(HelpdeskServiceOffering)
                    .join(HelpdeskService, HelpdeskService.service_id == HelpdeskServiceOffering.service_id)
                    .where(HelpdeskServiceOffering.full_code == offering)
                )
            ).scalar_one_or_none()
            if exists is None:
                raise ValueError("offering_code is invalid")

    def _apply_payload(self, row: Change, payload: dict[str, Any]) -> None:
        for field in (
            "risk_summary",
            "impact_summary",
            "implementation_summary",
            "rollback_summary",
            "communication_summary",
            "validation_summary",
            "closure_summary",
            "emergency_justification",
        ):
            if field in payload:
                setattr(row, field, clean_text(payload.get(field)))

    async def _latest_approved_risk(self, change_id: str) -> ChangeRiskAssessment | None:
        return (
            await self.session.execute(
                select(ChangeRiskAssessment)
                .where(ChangeRiskAssessment.change_id == change_id, ChangeRiskAssessment.status == "approved")
                .order_by(ChangeRiskAssessment.version_number.desc(), ChangeRiskAssessment.approved_at.desc(), ChangeRiskAssessment.assessment_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _latest_approved_plan(self, change_id: str) -> ChangePlan | None:
        return (
            await self.session.execute(
                select(ChangePlan)
                .where(ChangePlan.change_id == change_id, ChangePlan.status == "approved")
                .order_by(ChangePlan.version_number.desc(), ChangePlan.approved_at.desc(), ChangePlan.plan_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _validate_assessment_ready(self, row: Change) -> None:
        risk = await self._latest_approved_risk(row.change_id)
        if row.change_type in {"normal", "emergency"} and risk is None:
            raise ValueError("risk assessment is required before approval")
        plan = await self._latest_approved_plan(row.change_id)
        if row.change_type in {"normal", "emergency"} and plan is None:
            raise ValueError("implementation plan is required before approval")

    async def _validate_approval_ready(self, row: Change) -> None:
        risk = await self._latest_approved_risk(row.change_id)
        plan = await self._latest_approved_plan(row.change_id)
        approvals = await ChangeApprovalService(self.session).approval_status(row.change_id)
        validate_change_approval_payload(
            change_type=row.change_type,
            emergency_justification=row.emergency_justification,
            has_risk=risk is not None,
            has_plan=plan is not None,
            has_rollback=bool(plan and plan.rollback_steps_json),
            approvals_satisfied=approvals["satisfied"],
        )

    async def _validate_tasks_done(self, change_id: str) -> None:
        pending = (
            await self.session.execute(
                select(func.count(ChangeTask.task_id)).where(ChangeTask.change_id == change_id, ChangeTask.status.notin_(["done", "skipped"]))
            )
        ).scalar_one()
        if pending:
            raise ValueError("all implementation tasks must be completed before implemented")

    async def _has_approved_pir(self, change_id: str) -> bool:
        row = (
            await self.session.execute(
                select(ChangePIRRecord)
                .where(ChangePIRRecord.change_id == change_id, ChangePIRRecord.status == "approved")
                .order_by(ChangePIRRecord.approved_at.desc(), ChangePIRRecord.pir_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _requires_pir(self, row: Change) -> bool:
        policy = await ChangePolicyService(self.session).effective_policy(
            {"change_type": row.change_type, "risk_level": row.risk_level, "service_code": row.service_code, "offering_code": row.offering_code}
        )
        return bool(policy.get("require_pir", True)) and row.change_type in {"normal", "emergency"}

    async def _activity(self, change_id: str, event_type: str, actor_id: str | None, payload: dict[str, Any] | None = None) -> None:
        self.session.add(
            ChangeActivityEvent(
                event_id=str(uuid.uuid4()),
                change_id=change_id,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload or {},
            )
        )
        await self.session.flush()

    async def _create_failure_improvement_action(self, row: Change, actor_id: str | None, status: str) -> None:
        exists = (
            await self.session.execute(
                select(ContinuousImprovementAction).where(
                    ContinuousImprovementAction.change_id == row.change_id,
                    ContinuousImprovementAction.source_kind == "change",
                    ContinuousImprovementAction.source_ref == row.change_id,
                )
            )
        ).scalar_one_or_none()
        if exists is not None:
            return
        now = datetime.now(timezone.utc)
        self.session.add(
            ContinuousImprovementAction(
                action_id=str(uuid.uuid4()),
                source_kind="change",
                source_ref=row.change_id,
                change_id=row.change_id,
                problem_id=row.problem_id,
                service_code=row.service_code,
                offering_code=row.offering_code,
                action_type="process_review",
                title=f"Review {status} change {row.change_key}",
                description="Review failed or rolled-back change outcome and record corrective action.",
                status="open",
                priority="high" if row.risk_level in {"high", "critical"} else "medium",
                created_by=actor_id,
                created_at=now,
                updated_at=now,
                metadata_json={"change_status": status},
            )
        )
