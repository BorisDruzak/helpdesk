"""Requester create reservations owned by the caller's ticket transaction."""
from dataclasses import dataclass
import hashlib
import json
import re

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import ticket_to_dict
from app.db.models import RequesterTicketCreateRequest, TicketEvent
from tickets.public_access import PUBLIC_ACCESS_MESSAGE_KIND, verify_public_access_code


class CreateRequestConflict(ValueError):
    def __init__(self):
        super().__init__("Этот запрос уже использован. Проверьте ранее созданное обращение.")


@dataclass(frozen=True)
class CreateRequestKey:
    actor_hash: str
    key_hash: str
    payload_hash: str

    @classmethod
    def parse(cls, actor_id: str, key: str, payload: dict):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
            raise ValueError("Некорректный ключ повторного запроса.")
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        return cls(digest(str(actor_id)), digest(key), digest(canonical))


class RequesterCreateLedger:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lookup(self, key: CreateRequestKey) -> RequesterTicketCreateRequest | None:
        row = await self.session.get(RequesterTicketCreateRequest, (key.actor_hash, key.key_hash), populate_existing=True)
        if row is not None and (row.payload_hash != key.payload_hash or not row.ticket_id):
            raise CreateRequestConflict()
        return row

    async def reserve(self, key: CreateRequestKey) -> RequesterTicketCreateRequest | None:
        result = await self.session.execute(
            insert(RequesterTicketCreateRequest)
            .values(actor_hash=key.actor_hash, key_hash=key.key_hash, payload_hash=key.payload_hash)
            .on_conflict_do_nothing(index_elements=["actor_hash", "key_hash"])
            .returning(RequesterTicketCreateRequest.key_hash)
        )
        if result.scalar_one_or_none() is not None:
            return None
        row = await self.lookup(key)
        if row is None:
            raise CreateRequestConflict()
        return row

    async def complete(self, key: CreateRequestKey, ticket_id: str) -> None:
        await self.session.flush()
        result = await self.session.execute(
            update(RequesterTicketCreateRequest)
            .where(RequesterTicketCreateRequest.actor_hash == key.actor_hash,
                   RequesterTicketCreateRequest.key_hash == key.key_hash,
                   RequesterTicketCreateRequest.ticket_id.is_(None),
                   RequesterTicketCreateRequest.payload_hash == key.payload_hash)
            .values(ticket_id=ticket_id)
            .returning(RequesterTicketCreateRequest.key_hash)
        )
        if result.scalar_one_or_none() is None:
            raise CreateRequestConflict()


def created_ticket_response(ticket, public_access_code: str | None) -> dict:
    projected = ticket_to_dict(ticket, visibility="requester")
    return {"ticket": projected, "ticket_id": projected["ticket_id"],
            "ticket_code": projected.get("ticket_code"), "public_access_code": public_access_code,
            "public_access_url": projected.get("public_access_url")}


async def replay_created_ticket(session: AsyncSession, row: RequesterTicketCreateRequest, resolver, *, actor_id: str) -> dict:
    ticket = await resolver.get_ticket(actor_id=actor_id, ticket_id=row.ticket_id)
    if ticket is None:
        raise PermissionError("requester ticket unavailable")
    result = await session.execute(
        select(TicketEvent.payload["metadata"]["public_access_code"].astext)
        .where(TicketEvent.ticket_id == ticket.ticket_id, TicketEvent.event_type == "chat_message",
               TicketEvent.payload["metadata"]["kind"].astext == PUBLIC_ACCESS_MESSAGE_KIND,
               TicketEvent.payload["visibility"].astext == "public")
        .order_by(TicketEvent.id.desc()).limit(1)
    )
    code = result.scalar_one_or_none()
    if not isinstance(code, str) or not verify_public_access_code(ticket, code):
        code = None
    return created_ticket_response(ticket, code)
