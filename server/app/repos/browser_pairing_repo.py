from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceBrowserPairing


def new_id() -> str:
    return str(uuid.uuid4())


class BrowserPairingRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_pairing(self, pairing_id: str) -> DeviceBrowserPairing | None:
        return await self.session.get(DeviceBrowserPairing, str(pairing_id))

    async def create_pairing(self, **fields: Any) -> DeviceBrowserPairing:
        row = DeviceBrowserPairing(pairing_id=fields.pop("pairing_id", new_id()), **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_pending_for_device_purpose(self, *, device_id: str, purpose: str) -> list[DeviceBrowserPairing]:
        result = await self.session.execute(
            select(DeviceBrowserPairing)
            .where(DeviceBrowserPairing.device_id == str(device_id))
            .where(DeviceBrowserPairing.purpose == str(purpose))
            .where(DeviceBrowserPairing.status == "pending")
            .order_by(desc(DeviceBrowserPairing.created_at))
        )
        return list(result.scalars().all())

    async def find_pending_by_code_hash(self, pairing_code_hash: str) -> DeviceBrowserPairing | None:
        result = await self.session.execute(
            select(DeviceBrowserPairing)
            .where(DeviceBrowserPairing.pairing_code_hash == str(pairing_code_hash))
            .where(DeviceBrowserPairing.status == "pending")
            .order_by(desc(DeviceBrowserPairing.created_at))
            .limit(1)
        )
        return result.scalars().first()

    async def mark_superseded(self, row: DeviceBrowserPairing) -> DeviceBrowserPairing:
        now = datetime.now(timezone.utc)
        row.status = "superseded"
        row.completed_at = now
        row.metadata_json = {**(row.metadata_json or {}), "completion_reason": "superseded_by_new_pairing"}
        await self.session.flush()
        return row
