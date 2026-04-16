"""Repository for ticket form pack registry and preferred version settings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig, TicketFormPack


TICKET_FORM_PREFERRED_KEY_PREFIX = "ticket_form_pack_preferred:"


class TicketFormPacksRepo:
    """Repository for form-pack versions stored in the database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _preferred_key(pack_key: str) -> str:
        return f"{TICKET_FORM_PREFERRED_KEY_PREFIX}{pack_key}"

    async def list_packs(self, pack_key: Optional[str] = None) -> list[TicketFormPack]:
        stmt = select(TicketFormPack)
        if pack_key:
            stmt = stmt.where(TicketFormPack.pack_key == pack_key)
        stmt = stmt.order_by(TicketFormPack.created_at.desc(), TicketFormPack.version.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pack(self, pack_key: str, version: str) -> Optional[TicketFormPack]:
        result = await self.session.execute(
            select(TicketFormPack).where(
                TicketFormPack.pack_key == pack_key,
                TicketFormPack.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_pack(
        self,
        *,
        pack_key: str,
        version: str,
        schema_json: dict[str, Any],
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> TicketFormPack:
        existing = await self.get_pack(pack_key, version)
        if existing is not None:
            existing.schema_json = schema_json
            existing.created_by = created_by
            existing.notes = notes
            await self.session.flush()
            return existing

        pack = TicketFormPack(
            pack_key=pack_key,
            version=version,
            schema_json=schema_json,
            created_by=created_by,
            notes=notes,
        )
        self.session.add(pack)
        await self.session.flush()
        return pack

    async def delete_pack(self, pack_key: str, version: str) -> None:
        await self.session.execute(
            delete(TicketFormPack).where(
                TicketFormPack.pack_key == pack_key,
                TicketFormPack.version == version,
            )
        )
        await self.session.flush()

    async def get_preferred(self, pack_key: str) -> Optional[dict[str, Any]]:
        result = await self.session.execute(
            select(ServerConfig.value).where(ServerConfig.key == self._preferred_key(pack_key))
        )
        value = result.scalar_one_or_none()
        if not value:
            return None
        try:
            payload = json.loads(value)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        version = str(payload.get("version") or "").strip()
        if not version:
            return None
        return {
            "pack_key": pack_key,
            "version": version,
            "updated_at": payload.get("updated_at"),
            "updated_by": payload.get("updated_by"),
        }

    async def set_preferred(
        self,
        *,
        pack_key: str,
        version: str,
        updated_by: Optional[str] = None,
    ) -> dict[str, Any]:
        payload = {
            "pack_key": pack_key,
            "version": version,
            "updated_by": updated_by,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        value = json.dumps(payload, ensure_ascii=False)
        await self.session.execute(
            insert(ServerConfig)
            .values(key=self._preferred_key(pack_key), value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self.session.flush()
        return payload
