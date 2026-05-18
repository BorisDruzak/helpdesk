from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Change, ChangePIRRecord
from change.policy_service import ChangePolicyService


class ChangeAnalyticsService:
    def __init__(self, session) -> None:
        self.session = session

    async def summary(self) -> dict:
        changes = (await self.session.execute(select(Change))).scalars().all()
        pirs = (await self.session.execute(select(ChangePIRRecord))).scalars().all()
        approved_pir_change_ids = {pir.change_id for pir in pirs if pir.status == "approved"}
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_service: dict[str, int] = {}
        lead_times: list[float] = []
        implementation_durations: list[float] = []
        for row in changes:
            by_type[row.change_type] = by_type.get(row.change_type, 0) + 1
            by_status[row.status] = by_status.get(row.status, 0) + 1
            by_risk[row.risk_level] = by_risk.get(row.risk_level, 0) + 1
            by_service[row.service_code or "legacy"] = by_service.get(row.service_code or "legacy", 0) + 1
            if row.submitted_at and row.implementation_started_at:
                lead_times.append(_hours_between(row.submitted_at, row.implementation_started_at))
            if row.actual_start_at and row.actual_end_at:
                implementation_durations.append(_hours_between(row.actual_start_at, row.actual_end_at))
        failed = by_status.get("failed", 0)
        rolled_back = by_status.get("rolled_back", 0)
        change_count = len(changes)
        emergency_overdue = await self._emergency_retrospective_overdue(changes, approved_pir_change_ids)
        return {
            "change_count": change_count,
            "open_change_count": sum(1 for row in changes if row.status not in {"closed", "rejected", "canceled", "failed", "rolled_back"}),
            "emergency_change_count": by_type.get("emergency", 0),
            "failed_change_count": failed,
            "rollback_count": rolled_back,
            "failure_rate": (failed / change_count) if change_count else 0,
            "rollback_rate": (rolled_back / change_count) if change_count else 0,
            "average_lead_time_hours": _average(lead_times),
            "average_implementation_duration_hours": _average(implementation_durations),
            "pir_completion_rate": (sum(1 for pir in pirs if pir.status == "approved") / len(pirs)) if pirs else 0,
            "emergency_retrospective_overdue_count": emergency_overdue,
            "changes_by_type": by_type,
            "changes_by_status": by_status,
            "changes_by_risk": by_risk,
            "changes_by_service": by_service,
        }

    async def _emergency_retrospective_overdue(self, changes: list[Change], approved_pir_change_ids: set[str]) -> int:
        now = datetime.now(timezone.utc)
        overdue = 0
        policy_service = ChangePolicyService(self.session)
        for row in changes:
            if row.change_type != "emergency" or not row.implemented_at or row.change_id in approved_pir_change_ids:
                continue
            policy = await policy_service.effective_policy(
                {"change_type": row.change_type, "risk_level": row.risk_level, "service_code": row.service_code, "offering_code": row.offering_code}
            )
            max_hours = policy.get("max_emergency_retro_hours") or 72
            if _hours_between(row.implemented_at, now) > float(max_hours):
                overdue += 1
        return overdue


def _hours_between(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 3600)


def _average(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0

