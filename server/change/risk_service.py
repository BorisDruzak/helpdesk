from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import Change, ChangeRiskAssessment
from change.contracts import CHANGE_LEVELS, clean_text, validate_choice
from change.serializers import risk_to_dict


class RiskAssessmentService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_assessment(self, change_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        change = await self.session.get(Change, change_id)
        if change is None:
            raise ValueError("change not found")
        factors = payload.get("risk_factors") if isinstance(payload.get("risk_factors"), dict) else {}
        suggested = self.suggest_risk(factors)
        risk_level = validate_choice(payload.get("risk_level") or suggested, CHANGE_LEVELS, "risk_level")
        if self._level_rank(risk_level) < self._level_rank(suggested) and not clean_text(payload.get("override_reason")):
            raise ValueError("override reason is required when lowering suggested risk")
        version = (
            await self.session.execute(select(func.coalesce(func.max(ChangeRiskAssessment.version_number), 0)).where(ChangeRiskAssessment.change_id == change_id))
        ).scalar_one() + 1
        row = ChangeRiskAssessment(
            assessment_id=str(uuid.uuid4()),
            change_id=change_id,
            version_number=version,
            risk_level=risk_level,
            impact_level=validate_choice(payload.get("impact_level") or risk_level, CHANGE_LEVELS, "impact_level"),
            suggested_risk_level=suggested,
            risk_factors_json=factors,
            mitigation_plan=clean_text(payload.get("mitigation_plan")),
            test_plan_summary=clean_text(payload.get("test_plan_summary")),
            assessed_by_actor_id=actor_id,
            override_reason=clean_text(payload.get("override_reason")),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        change.risk_level = risk_level
        change.impact_level = row.impact_level
        self.session.add(row)
        await self.session.flush()
        return risk_to_dict(row)

    async def submit_assessment(self, change_id: str, assessment_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, assessment_id)
        row.status = "submitted"
        row.submitted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return risk_to_dict(row)

    async def approve_assessment(self, change_id: str, assessment_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, assessment_id)
        row.status = "approved"
        row.approved_by_actor_id = actor_id
        row.approved_at = datetime.now(timezone.utc)
        await self.session.flush()
        return risk_to_dict(row)

    def suggest_risk(self, factors: dict[str, Any]) -> str:
        score = 0
        for value in factors.values():
            score += {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(str(value).lower(), 0)
        if score >= 7:
            return "critical"
        if score >= 5:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    def _level_rank(self, value: str) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[value]

    async def _get(self, change_id: str, assessment_id: str) -> ChangeRiskAssessment:
        row = (
            await self.session.execute(
                select(ChangeRiskAssessment).where(ChangeRiskAssessment.change_id == change_id, ChangeRiskAssessment.assessment_id == assessment_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("risk assessment not found")
        return row

