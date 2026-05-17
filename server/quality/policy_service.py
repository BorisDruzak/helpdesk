from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import QualityPolicy


DEFAULT_POLICY = {
    "policy_id": None,
    "scope_type": "global",
    "service_code": None,
    "offering_code": None,
    "queue_id": None,
    "enabled": True,
    "low_csat_threshold": 3,
    "reopen_review_enabled": True,
    "sla_breach_review_enabled": True,
    "high_priority_review_enabled": True,
    "missing_evidence_review_enabled": True,
    "random_sample_percent": 0.0,
    "qa_due_hours": 72,
}


class QualityPolicyService:
    def __init__(self, session) -> None:
        self.session = session

    async def effective_policy(
        self,
        *,
        service_code: str | None,
        offering_code: str | None,
        queue_id: int | None,
    ) -> dict[str, Any]:
        policy = dict(DEFAULT_POLICY)
        rows = (
            await self.session.execute(
                select(QualityPolicy).where(QualityPolicy.enabled.is_(True))
            )
        ).scalars().all()
        ordered = sorted(rows, key=lambda row: self._specificity(row, service_code, offering_code, queue_id))
        for row in ordered:
            if self._matches(row, service_code, offering_code, queue_id):
                policy.update(self._serialize(row))
        return policy

    async def save_policy(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        scope_type = str(payload.get("scope_type") or "global").strip() or "global"
        if scope_type not in {"global", "service", "offering", "queue"}:
            raise ValueError("scope_type is invalid")
        policy_id = str(payload.get("policy_id") or uuid.uuid4())
        row = await self.session.get(QualityPolicy, policy_id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = QualityPolicy(policy_id=policy_id, created_at=now, updated_at=now)
            self.session.add(row)
        row.scope_type = scope_type
        row.service_code = str(payload.get("service_code") or "").strip() or None
        row.offering_code = str(payload.get("offering_code") or "").strip() or None
        raw_queue = payload.get("queue_id")
        row.queue_id = int(raw_queue) if raw_queue not in (None, "") else None
        row.enabled = bool(payload.get("enabled", True))
        row.low_csat_threshold = int(payload.get("low_csat_threshold", DEFAULT_POLICY["low_csat_threshold"]))
        row.reopen_review_enabled = bool(payload.get("reopen_review_enabled", True))
        row.sla_breach_review_enabled = bool(payload.get("sla_breach_review_enabled", True))
        row.high_priority_review_enabled = bool(payload.get("high_priority_review_enabled", True))
        row.missing_evidence_review_enabled = bool(payload.get("missing_evidence_review_enabled", True))
        row.random_sample_percent = float(payload.get("random_sample_percent", 0) or 0)
        row.qa_due_hours = int(payload.get("qa_due_hours", DEFAULT_POLICY["qa_due_hours"]))
        row.metadata_json = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        row.updated_at = now
        await self.session.flush()
        result = self._serialize(row)
        result["policy_id"] = row.policy_id
        return result

    def _matches(self, row: QualityPolicy, service_code: str | None, offering_code: str | None, queue_id: int | None) -> bool:
        if row.scope_type == "global":
            return True
        if row.scope_type == "queue":
            return row.queue_id is not None and row.queue_id == queue_id
        if row.scope_type == "service":
            return bool(row.service_code) and row.service_code == service_code
        if row.scope_type == "offering":
            return bool(row.service_code) and bool(row.offering_code) and row.service_code == service_code and row.offering_code == offering_code
        return False

    def _specificity(self, row: QualityPolicy, service_code: str | None, offering_code: str | None, queue_id: int | None) -> int:
        if not self._matches(row, service_code, offering_code, queue_id):
            return -1
        return {"global": 0, "service": 1, "offering": 2, "queue": 3}.get(row.scope_type, 0)

    def _serialize(self, row: QualityPolicy) -> dict[str, Any]:
        return {
            "policy_id": row.policy_id,
            "scope_type": row.scope_type,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "queue_id": row.queue_id,
            "enabled": bool(row.enabled),
            "low_csat_threshold": int(row.low_csat_threshold),
            "reopen_review_enabled": bool(row.reopen_review_enabled),
            "sla_breach_review_enabled": bool(row.sla_breach_review_enabled),
            "high_priority_review_enabled": bool(row.high_priority_review_enabled),
            "missing_evidence_review_enabled": bool(row.missing_evidence_review_enabled),
            "random_sample_percent": float(row.random_sample_percent or 0),
            "qa_due_hours": int(row.qa_due_hours),
        }
