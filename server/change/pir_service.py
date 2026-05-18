from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Change, ChangePIRRecord
from change.contracts import clean_text
from change.serializers import pir_to_dict


class PIRService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_pir(self, change_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        if await self.session.get(Change, change_id) is None:
            raise ValueError("change not found")
        row = ChangePIRRecord(
            pir_id=str(uuid.uuid4()),
            change_id=change_id,
            implementation_successful=payload.get("implementation_successful"),
            rollback_used=bool(payload.get("rollback_used", False)),
            caused_incident=bool(payload.get("caused_incident", False)),
            met_objectives=payload.get("met_objectives"),
            downtime_actual_minutes=payload.get("downtime_actual_minutes"),
            issues_json=payload.get("issues") if isinstance(payload.get("issues"), list) else [],
            lessons_learned=clean_text(payload.get("lessons_learned")),
            follow_up_actions_json=payload.get("follow_up_actions") if isinstance(payload.get("follow_up_actions"), list) else [],
            reviewed_by_actor_id=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        return pir_to_dict(row)

    async def submit_pir(self, change_id: str, pir_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, pir_id)
        row.status = "submitted"
        row.submitted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return pir_to_dict(row)

    async def approve_pir(self, change_id: str, pir_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, pir_id)
        row.status = "approved"
        row.approved_by_actor_id = actor_id
        row.approved_at = datetime.now(timezone.utc)
        await self.session.flush()
        return pir_to_dict(row)

    async def list_pirs(self, change_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(ChangePIRRecord).where(ChangePIRRecord.change_id == change_id))).scalars().all()
        return [pir_to_dict(row) for row in rows]

    async def _get(self, change_id: str, pir_id: str) -> ChangePIRRecord:
        row = (await self.session.execute(select(ChangePIRRecord).where(ChangePIRRecord.change_id == change_id, ChangePIRRecord.pir_id == pir_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("PIR not found")
        return row

