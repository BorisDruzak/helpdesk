from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select

from app.db.models import Problem, ProblemCandidate, ProblemTicketLink


class ProblemAnalyticsService:
    def __init__(self, session) -> None:
        self.session = session

    async def summary(self) -> dict[str, Any]:
        problems = (await self.session.execute(select(Problem))).scalars().all()
        candidates = (await self.session.execute(select(ProblemCandidate))).scalars().all()
        links = (await self.session.execute(select(ProblemTicketLink).where(ProblemTicketLink.unlinked_at.is_(None)))).scalars().all()
        non_terminal = [row for row in problems if row.status not in {"resolved", "closed", "canceled"}]
        by_status = Counter(row.status for row in problems)
        by_severity = Counter(row.severity for row in problems)
        by_service = Counter(row.service_code or "legacy" for row in problems)
        unresolved_known_errors = sum(1 for row in problems if row.status in {"known_error", "workaround_available", "permanent_fix_planned", "permanent_fix_in_progress"})
        without_rca = sum(1 for row in non_terminal if not (row.root_cause_summary or row.root_cause))
        return {
            "open_problem_count": len(non_terminal),
            "candidate_count": len([row for row in candidates if row.status == "open"]),
            "linked_ticket_count": len(links),
            "problems_by_status": dict(by_status),
            "problems_by_severity": dict(by_severity),
            "problems_by_service": dict(by_service),
            "unresolved_known_errors": unresolved_known_errors,
            "problems_without_rca": without_rca,
        }
