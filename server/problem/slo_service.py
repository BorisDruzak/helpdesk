from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select

from app.db.models import Problem, ProblemSLOPolicy


DEFAULT_SLO_HOURS: dict[str, dict[str, int]] = {
    "critical": {"investigation": 1, "known_error": 8, "workaround": 12, "rca": 24, "resolution": 72, "closure": 96},
    "high": {"investigation": 4, "known_error": 24, "workaround": 48, "rca": 72, "resolution": 168, "closure": 240},
    "medium": {"investigation": 24, "known_error": 72, "workaround": 96, "rca": 120, "resolution": 336, "closure": 504},
    "low": {"investigation": 48, "known_error": 120, "workaround": 168, "rca": 168, "resolution": 504, "closure": 672},
}


MILESTONE_DUE_FIELDS = {
    "investigation": "investigation_due_at",
    "known_error": "known_error_due_at",
    "workaround": "workaround_due_at",
    "rca": "rca_due_at",
    "resolution": "resolution_due_at",
    "closure": "closure_due_at",
}

MILESTONE_ACTUAL_FIELDS = {
    "investigation": "investigation_started_at",
    "known_error": "known_error_at",
    "workaround": "workaround_available_at",
    "rca": None,
    "resolution": "resolved_at",
    "closure": "closed_at",
}


class ProblemSLOService:
    def __init__(self, session) -> None:
        self.session = session

    async def get_problem_row(self, problem_id: str) -> Problem:
        row = await self.session.get(Problem, problem_id)
        if row is None:
            raise ValueError("problem not found")
        return row

    async def apply_due_dates(self, row: Problem, *, now: datetime | None = None) -> None:
        base = row.opened_at or row.created_at or now or datetime.now(timezone.utc)
        policy = await self.effective_policy(row)
        row.investigation_due_at = base + timedelta(hours=policy["investigation"])
        row.known_error_due_at = base + timedelta(hours=policy["known_error"])
        row.workaround_due_at = base + timedelta(hours=policy["workaround"])
        row.rca_due_at = base + timedelta(hours=policy["rca"])
        row.resolution_due_at = base + timedelta(hours=policy["resolution"])
        row.closure_due_at = base + timedelta(hours=policy["closure"])
        self.refresh_breached_milestones(row, now=now)

    async def effective_policy(self, row: Problem) -> dict[str, int]:
        policies = (
            await self.session.execute(
                select(ProblemSLOPolicy).where(
                    ProblemSLOPolicy.enabled.is_(True),
                    or_(ProblemSLOPolicy.severity.is_(None), ProblemSLOPolicy.severity == row.severity),
                    or_(ProblemSLOPolicy.service_code.is_(None), ProblemSLOPolicy.service_code == row.service_code),
                    or_(ProblemSLOPolicy.offering_code.is_(None), ProblemSLOPolicy.offering_code == row.offering_code),
                )
            )
        ).scalars().all()
        selected = sorted(policies, key=self._policy_specificity, reverse=True)
        if selected:
            policy = selected[0]
            return {
                "investigation": int(policy.investigation_due_hours),
                "known_error": int(policy.known_error_due_hours),
                "workaround": int(policy.workaround_due_hours),
                "rca": int(policy.rca_due_hours),
                "resolution": int(policy.resolution_due_hours),
                "closure": int(policy.closure_due_hours),
            }
        return dict(DEFAULT_SLO_HOURS.get(row.severity or "medium", DEFAULT_SLO_HOURS["medium"]))

    def refresh_breached_milestones(self, row: Problem, *, now: datetime | None = None, rca_approved_at: datetime | None = None) -> list[str]:
        now = now or datetime.now(timezone.utc)
        breached: list[str] = []
        for milestone, due_field in MILESTONE_DUE_FIELDS.items():
            due_at = getattr(row, due_field, None)
            if due_at is None or due_at >= now:
                continue
            actual_field = MILESTONE_ACTUAL_FIELDS[milestone]
            actual = rca_approved_at if milestone == "rca" else getattr(row, actual_field, None) if actual_field else None
            if actual is None or actual > due_at:
                breached.append(milestone)
        row.breached_milestones = breached
        return breached

    def operational_status(self, row: Problem, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        self.refresh_breached_milestones(row, now=now)
        next_due = None
        next_due_at = None
        for milestone, due_field in MILESTONE_DUE_FIELDS.items():
            actual_field = MILESTONE_ACTUAL_FIELDS[milestone]
            if actual_field and getattr(row, actual_field, None) is not None:
                continue
            due_at = getattr(row, due_field, None)
            if due_at is None:
                continue
            if next_due_at is None or due_at < next_due_at:
                next_due = milestone
                next_due_at = due_at
        return {
            "breached_milestones": list(row.breached_milestones or []),
            "next_due_milestone": next_due,
            "next_due_at": next_due_at,
            "is_overdue": bool(row.breached_milestones),
        }

    @staticmethod
    def _policy_specificity(policy: ProblemSLOPolicy) -> tuple[int, int]:
        scope_score = {"global": 0, "severity": 1, "service": 2, "offering": 3}.get(policy.scope_type, 0)
        field_score = sum(1 for value in (policy.severity, policy.service_code, policy.offering_code) if value)
        return scope_score, field_score
