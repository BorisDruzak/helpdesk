"""OBS1 quality/problem/change governance integrity checks."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Change, ChangePlan, ChangeRiskAssessment, ProblemCandidate
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput
from observer.checks.types import ObserverIntegrityCheckResult, limit_plus_one_window


SOURCE = "observer.governance"
DUPLICATE_QUERY_LIMIT = 100
CHANGE_QUERY_LIMIT = 300


async def check_governance(session: AsyncSession, *, run_id: str | None = None) -> ObserverIntegrityCheckResult:
    events: list[ObserverIntegrityEventInput] = []
    duplicate_events, duplicate_complete, duplicate_scanned = await _duplicate_problem_candidates(session, run_id=run_id)
    change_events, change_complete, change_scanned = await _approved_changes_missing_package(session, run_id=run_id)
    events.extend(duplicate_events)
    events.extend(change_events)
    return ObserverIntegrityCheckResult(
        source=SOURCE,
        events=events,
        complete=duplicate_complete and change_complete,
        scanned_count=duplicate_scanned + change_scanned,
        limit=max(DUPLICATE_QUERY_LIMIT, CHANGE_QUERY_LIMIT),
    )


async def _duplicate_problem_candidates(
    session: AsyncSession,
    *,
    run_id: str | None,
) -> tuple[list[ObserverIntegrityEventInput], bool, int]:
    rows = (
        await session.execute(
            select(
                ProblemCandidate.signal_type,
                ProblemCandidate.service_code,
                ProblemCandidate.offering_code,
                ProblemCandidate.request_type,
                func.count(ProblemCandidate.candidate_id),
            )
            .where(ProblemCandidate.status == "open")
            .group_by(
                ProblemCandidate.signal_type,
                ProblemCandidate.service_code,
                ProblemCandidate.offering_code,
                ProblemCandidate.request_type,
            )
            .having(func.count(ProblemCandidate.candidate_id) > 1)
            .limit(DUPLICATE_QUERY_LIMIT + 1)
        )
    ).all()
    rows_window, complete = limit_plus_one_window(rows, limit=DUPLICATE_QUERY_LIMIT)
    events: list[ObserverIntegrityEventInput] = []
    for signal_type, service_code, offering_code, request_type, count in rows_window:
        key = "|".join(str(value or "none") for value in (signal_type, service_code, offering_code, request_type))
        events.append(
            ObserverIntegrityEventInput(
                event_type="problem_duplicate_open_candidates",
                severity="error",
                source=SOURCE,
                dedupe_key=f"problem_duplicate_open_candidates:{key}",
                expected="Problem scanner should not leave duplicate open candidates for the same stable signal dimensions.",
                actual=f"{int(count or 0)} open candidates share signal dimensions {key}.",
                evidence={
                    "signal_type": signal_type,
                    "service_code": service_code,
                    "offering_code": offering_code,
                    "request_type": request_type,
                    "open_candidate_count": int(count or 0),
                },
                runbook="docs/runbooks/observer_governance.md",
                run_id=run_id,
            )
        )
    return events, complete, len(rows)


async def _approved_changes_missing_package(
    session: AsyncSession,
    *,
    run_id: str | None,
) -> tuple[list[ObserverIntegrityEventInput], bool, int]:
    rows = (
        await session.execute(
            select(Change)
            .where(Change.status.in_(("approved", "scheduled", "implementation_in_progress", "implemented", "closed")))
            .limit(CHANGE_QUERY_LIMIT + 1)
        )
    ).scalars().all()
    change_window, complete = limit_plus_one_window(rows, limit=CHANGE_QUERY_LIMIT)
    events: list[ObserverIntegrityEventInput] = []
    for change in change_window:
        risk_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ChangeRiskAssessment)
                .where(ChangeRiskAssessment.change_id == change.change_id, ChangeRiskAssessment.status == "approved")
            )
            or 0
        )
        plan_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ChangePlan)
                .where(ChangePlan.change_id == change.change_id, ChangePlan.status.in_(("approved", "active")))
            )
            or 0
        )
        if risk_count > 0 and plan_count > 0:
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="change_approved_without_package",
                severity="critical" if str(change.status) in {"implementation_in_progress", "implemented", "closed"} else "error",
                source=SOURCE,
                dedupe_key=f"change_approved_without_package:{change.change_id}",
                expected="Approved or later changes must have approved risk and plan package before implementation.",
                actual=f"status={change.status}; approved_risk_count={risk_count}; approved_plan_count={plan_count}",
                evidence={
                    "change_id": change.change_id,
                    "change_key": change.change_key,
                    "status": change.status,
                    "change_type": change.change_type,
                    "risk_level": change.risk_level,
                    "approved_risk_count": risk_count,
                    "approved_plan_count": plan_count,
                },
                runbook="docs/runbooks/observer_governance.md",
                run_id=run_id,
            )
        )
    return events, complete, len(rows)
