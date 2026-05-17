from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Problem, ProblemCandidate, ProblemRCARecord, ProblemTicketLink


class ProblemAnalyticsService:
    def __init__(self, session) -> None:
        self.session = session

    async def summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        problems = (await self.session.execute(select(Problem))).scalars().all()
        candidates = (await self.session.execute(select(ProblemCandidate))).scalars().all()
        links = (await self.session.execute(select(ProblemTicketLink).where(ProblemTicketLink.unlinked_at.is_(None)))).scalars().all()
        rcas = (await self.session.execute(select(ProblemRCARecord))).scalars().all()
        non_terminal = [row for row in problems if row.status not in {"resolved", "closed", "canceled"}]
        by_status = Counter(row.status for row in problems)
        by_severity = Counter(row.severity for row in problems)
        by_service = Counter(row.service_code or "legacy" for row in problems)
        unresolved_known_errors = sum(1 for row in problems if row.status in {"known_error", "workaround_available", "permanent_fix_planned", "permanent_fix_in_progress"})
        without_rca = sum(1 for row in non_terminal if not (row.root_cause_summary or row.root_cause))
        without_workaround = sum(1 for row in non_terminal if not (row.workaround_summary or row.workaround))
        overdue_milestones: Counter[str] = Counter()
        for row in non_terminal:
            for milestone in self._breached_milestones(row, now=now):
                overdue_milestones[milestone] += 1
        approved_rca_by_problem = {
            row.problem_id: row.approved_at
            for row in rcas
            if row.status == "approved" and row.approved_at is not None
        }
        return {
            "open_problem_count": len(non_terminal),
            "open_critical_count": sum(1 for row in non_terminal if row.severity == "critical"),
            "candidate_count": len([row for row in candidates if row.status == "open"]),
            "candidate_count_by_status": dict(Counter(row.status for row in candidates)),
            "candidate_count_by_source": dict(Counter(row.signal_type for row in candidates)),
            "candidate_conversion_rate": self._conversion_rate(candidates),
            "average_candidate_age_hours": self._average_hours([now - row.created_at for row in candidates if row.status == "open"]),
            "average_problem_age_hours": self._average_hours([now - row.opened_at for row in non_terminal if row.opened_at]),
            "linked_ticket_count": len(links),
            "problems_by_status": dict(by_status),
            "problems_by_severity": dict(by_severity),
            "problems_by_service": dict(by_service),
            "unresolved_known_errors": unresolved_known_errors,
            "problems_without_rca": without_rca,
            "problems_without_workaround": without_workaround,
            "overdue_problem_count": len([row for row in non_terminal if self._breached_milestones(row, now=now)]),
            "overdue_milestones": dict(overdue_milestones),
            "avg_time_to_known_error_hours": self._avg_transition_hours(problems, "known_error_at"),
            "avg_time_to_workaround_hours": self._avg_transition_hours(problems, "workaround_available_at"),
            "avg_time_to_rca_approval_hours": self._avg_rca_hours(problems, approved_rca_by_problem),
            "avg_time_to_resolution_hours": self._avg_transition_hours(problems, "resolved_at"),
        }

    def _breached_milestones(self, row: Problem, *, now: datetime) -> list[str]:
        if row.breached_milestones:
            return list(row.breached_milestones)
        due_actual = {
            "investigation": (row.investigation_due_at, row.investigation_started_at),
            "known_error": (row.known_error_due_at, row.known_error_at),
            "workaround": (row.workaround_due_at, row.workaround_available_at),
            "rca": (row.rca_due_at, None),
            "resolution": (row.resolution_due_at, row.resolved_at),
            "closure": (row.closure_due_at, row.closed_at),
        }
        return [name for name, (due_at, actual_at) in due_actual.items() if due_at is not None and due_at < now and actual_at is None]

    def _avg_transition_hours(self, problems: list[Problem], field: str) -> int | None:
        values = []
        for row in problems:
            actual = getattr(row, field, None)
            if row.opened_at and actual:
                values.append(actual - row.opened_at)
        return self._average_hours(values)

    def _avg_rca_hours(self, problems: list[Problem], approved: dict[str, datetime]) -> int | None:
        values = []
        by_id = {row.problem_id: row for row in problems}
        for problem_id, approved_at in approved.items():
            problem = by_id.get(problem_id)
            if problem and problem.opened_at:
                values.append(approved_at - problem.opened_at)
        return self._average_hours(values)

    @staticmethod
    def _average_hours(values) -> int | None:
        if not values:
            return None
        return int(sum(item.total_seconds() for item in values) / len(values) / 3600)

    @staticmethod
    def _conversion_rate(candidates: list[ProblemCandidate]) -> float:
        if not candidates:
            return 0.0
        converted = len([row for row in candidates if row.status == "converted"])
        return round(converted / len(candidates), 4)
