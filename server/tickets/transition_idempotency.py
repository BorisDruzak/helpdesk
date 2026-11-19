"""Durable, actor-scoped receipts for canonical Helpdesk status mutations."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text

from app.db.models import TicketAdminAudit


RECEIPT_ACTION = "support_transition_receipt"


def transition_intent(data: dict) -> tuple[str, str]:
    key = str(UUID(data["operation_id"]))
    body = {field: value for field, value in data.items() if field != "operation_id"}
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return key, fingerprint


async def read_transition_receipt(session, *, ticket_id: str, actor_id: str, key: str) -> dict | None:
    receipt = (await session.execute(select(TicketAdminAudit.after_json).where(
        TicketAdminAudit.entity_type == "ticket",
        TicketAdminAudit.entity_id == ticket_id,
        TicketAdminAudit.action == RECEIPT_ACTION,
        TicketAdminAudit.actor_id == actor_id,
        TicketAdminAudit.after_json["operation_id"].as_string() == key,
    ))).scalar_one_or_none()
    if receipt is not None:
        return receipt
    archived = await session.execute(text(
        "SELECT after_json FROM ticket_admin_audit_archive "
        "WHERE entity_type = 'ticket' AND entity_id = :ticket_id AND action = :action "
        "AND actor_id = :actor_id AND after_json ->> 'operation_id' = :key"
    ), {"ticket_id": ticket_id, "action": RECEIPT_ACTION, "actor_id": actor_id, "key": key})
    return archived.scalar_one_or_none()


def store_transition_receipt(session, *, actor, key: str, fingerprint: str, source: str, result: dict) -> None:
    session.add(TicketAdminAudit(
        entity_type="ticket", entity_id=result["ticket_id"], action=RECEIPT_ACTION,
        actor_id=actor.actor_id, actor_role=actor.actor_role,
        after_json={"operation_id": key, "fingerprint": fingerprint, "source": source, "result": result},
    ))
