from __future__ import annotations

from sqlalchemy import select

from app.db.models import Change, ChangePIRRecord


class ChangeAnalyticsService:
    def __init__(self, session) -> None:
        self.session = session

    async def summary(self) -> dict:
        changes = (await self.session.execute(select(Change))).scalars().all()
        pirs = (await self.session.execute(select(ChangePIRRecord))).scalars().all()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_service: dict[str, int] = {}
        for row in changes:
            by_type[row.change_type] = by_type.get(row.change_type, 0) + 1
            by_status[row.status] = by_status.get(row.status, 0) + 1
            by_risk[row.risk_level] = by_risk.get(row.risk_level, 0) + 1
            by_service[row.service_code or "legacy"] = by_service.get(row.service_code or "legacy", 0) + 1
        failed = sum(1 for row in changes if row.status in {"failed", "rolled_back"})
        return {
            "change_count": len(changes),
            "open_change_count": sum(1 for row in changes if row.status not in {"closed", "rejected", "canceled", "failed", "rolled_back"}),
            "emergency_change_count": by_type.get("emergency", 0),
            "failed_change_count": failed,
            "rollback_count": by_status.get("rolled_back", 0),
            "pir_completion_rate": (sum(1 for pir in pirs if pir.status == "approved") / len(pirs)) if pirs else 0,
            "changes_by_type": by_type,
            "changes_by_status": by_status,
            "changes_by_risk": by_risk,
            "changes_by_service": by_service,
        }

