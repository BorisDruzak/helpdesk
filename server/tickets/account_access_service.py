from __future__ import annotations

from typing import Any

from sqlalchemy import and_, false, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket
from registry.account_session_service import AccountSessionService


PENDING_REGISTRATION_STATUSES = {
    "self_reported",
    "pending_user_confirmation",
    "user_confirmed",
    "pending_admin_review",
    "conflict",
    "registration_pending",
}


def requester_account_from_payload(
    payload: dict[str, Any] | None = None,
    *,
    query: Any | None = None,
    headers: Any | None = None,
) -> dict[str, Any] | None:
    payload = payload if isinstance(payload, dict) else {}
    account = payload.get("requester_account") if isinstance(payload.get("requester_account"), dict) else {}
    query = query or {}
    headers = headers or {}
    session_id = str(
        account.get("session_id")
        or account.get("account_session_id")
        or query.get("account_session_id")
        or query.get("session_id")
        or headers.get("X-Account-Session-Id")
        or ""
    ).strip()
    session_token = str(
        account.get("session_token")
        or query.get("session_token")
        or headers.get("X-Account-Session-Token")
        or ""
    ).strip()
    if not session_id and not session_token:
        return None
    return {"session_id": session_id, "session_token": session_token or None}


class TicketAccountAccessService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_sessions = AccountSessionService(session)

    async def validate_agent_account_session(
        self,
        *,
        device_id: str,
        requester_account: dict[str, Any] | None,
        require: bool = True,
    ) -> dict[str, Any]:
        session_id = str((requester_account or {}).get("session_id") or (requester_account or {}).get("account_session_id") or "").strip()
        session_token = str((requester_account or {}).get("session_token") or "").strip() or None
        if not session_id:
            return {
                "valid": False,
                "error_code": "ACCOUNT_SESSION_REQUIRED" if require else "ACCOUNT_SESSION_MISSING",
            }
        validation = await self.account_sessions.validate_session(
            device_id=device_id,
            session_id=session_id,
            session_token=session_token,
        )
        if not validation.get("valid"):
            return {
                "valid": False,
                "error_code": validation.get("error_code") or "ACCOUNT_SESSION_INVALID",
                "validation": validation,
            }
        return {"valid": True, "session": validation.get("session") or {}}

    async def can_create_ticket(self, *, device_id: str, account_session: dict[str, Any]) -> bool:
        return str(account_session.get("device_id") or "") == str(device_id) and str(
            account_session.get("account_mode") or ""
        ) in {"confirmed_binding", "verified_other_account"}

    async def can_view_ticket(self, *, ticket: Ticket, account_session: dict[str, Any]) -> bool:
        return self._ticket_allowed(ticket, account_session)

    async def can_send_message(self, *, ticket: Ticket, account_session: dict[str, Any]) -> bool:
        return self._ticket_allowed(ticket, account_session)

    def _ticket_allowed(self, ticket: Ticket, account_session: dict[str, Any]) -> bool:
        mode = str(account_session.get("account_mode") or "")
        session_id = str(account_session.get("session_id") or "")
        if str(getattr(ticket, "device_id", "") or "") != str(account_session.get("device_id") or ""):
            return False
        if mode == "confirmed_binding":
            if session_id and getattr(ticket, "requester_account_session_id", None) == session_id:
                return True
            binding_id = str(account_session.get("binding_id") or "")
            person_id = str(account_session.get("person_id") or "")
            return bool(
                (binding_id and getattr(ticket, "requester_binding_id", None) == binding_id)
                or (person_id and getattr(ticket, "requester_person_id", None) == person_id)
            )
        if mode == "verified_other_account":
            return bool(session_id and getattr(ticket, "requester_account_session_id", None) == session_id)
        if mode == "registration_pending":
            if session_id and getattr(ticket, "requester_account_session_id", None) == session_id:
                return True
            person_id = str(account_session.get("person_id") or "")
            return bool(
                person_id
                and getattr(ticket, "requester_person_id", None) == person_id
                and str(getattr(ticket, "requester_registration_status", "") or "") in PENDING_REGISTRATION_STATUSES
            )
        return False

    def apply_ticket_list_filter(self, stmt, *, account_session: dict[str, Any]):
        mode = str(account_session.get("account_mode") or "")
        session_id = str(account_session.get("session_id") or "")
        if mode == "confirmed_binding":
            binding_id = str(account_session.get("binding_id") or "")
            person_id = str(account_session.get("person_id") or "")
            clauses = []
            if session_id:
                clauses.append(Ticket.requester_account_session_id == session_id)
            if binding_id:
                clauses.append(Ticket.requester_binding_id == binding_id)
            if person_id:
                clauses.append(Ticket.requester_person_id == person_id)
            return stmt.where(or_(*clauses)) if clauses else stmt.where(false())
        if mode == "verified_other_account":
            return stmt.where(Ticket.requester_account_session_id == session_id)
        if mode == "registration_pending":
            person_id = str(account_session.get("person_id") or "")
            clauses = [Ticket.requester_account_session_id == session_id] if session_id else []
            if person_id:
                clauses.append(
                    and_(
                        Ticket.requester_person_id == person_id,
                        Ticket.requester_registration_status.in_(list(PENDING_REGISTRATION_STATUSES)),
                    )
                )
            return stmt.where(or_(*clauses)) if clauses else stmt.where(false())
        return stmt.where(false())
