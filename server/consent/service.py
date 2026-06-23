from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceAccountSession, DeviceUserBinding, UserConsentRequest
from app.repos.operations_repo import OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.user_consent_repo import UserConsentRepo
from app.services.operation_service import OperationService


FINAL_STATUSES = {"approved", "denied", "expired", "superseded", "canceled"}
OPERATION_SUBJECT_TYPES = {"operation", "tool_run", "diagnostic"}
OPERATION_CONSENT_NO_LONGER_ACTIONABLE_STATUSES = {
    "cancel_requested",
    "canceled",
    "denied",
    "failed",
    "succeeded",
    "timed_out",
}
PENDING_SUBJECT_UNIQUE_INDEX = "ux_user_consent_requests_pending_subject"


class ConsentAccessError(Exception):
    def __init__(self, message: str, *, error_code: str = "FORBIDDEN", status: int = 403):
        super().__init__(message)
        self.error_code = error_code
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _clean(value: Any, *, max_length: int = 1000) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


def _integrity_error_matches_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    candidates: list[Any] = [exc, getattr(exc, "orig", None)]
    orig = getattr(exc, "orig", None)
    candidates.append(getattr(orig, "__cause__", None))
    for candidate in list(candidates):
        if candidate is None:
            continue
        candidates.append(getattr(candidate, "diag", None))

    for candidate in candidates:
        if candidate is None:
            continue
        if getattr(candidate, "constraint_name", None) == constraint_name:
            return True
        if getattr(candidate, "constraint", None) == constraint_name:
            return True
        text = str(candidate)
        if constraint_name in text:
            return True
    return False


def serialize_user_consent(row: UserConsentRequest) -> dict[str, Any]:
    return {
        "consent_id": row.consent_id,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "ticket_id": row.ticket_id,
        "device_id": row.device_id,
        "requester_person_id": row.requester_person_id,
        "requester_binding_id": row.requester_binding_id,
        "requester_account_session_id": row.requester_account_session_id,
        "requested_by_actor_id": row.requested_by_actor_id,
        "requested_by_role": row.requested_by_role,
        "risk_level": row.risk_level,
        "policy_snapshot": row.policy_snapshot or {},
        "risk_explanation": row.risk_explanation,
        "requested_action_payload_redacted": row.requested_action_payload_redacted or {},
        "title": row.title,
        "description": row.description,
        "reason": row.reason,
        "status": row.status,
        "expires_at": _iso(row.expires_at),
        "decided_by_actor_id": row.decided_by_actor_id,
        "decided_by_role": row.decided_by_role,
        "decided_from_surface": row.decided_from_surface,
        "decided_at": _iso(row.decided_at),
        "metadata": row.metadata_json or {},
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


class UserConsentService:
    def __init__(self, session: AsyncSession, *, publisher: Any = None, state: Any = None):
        self.session = session
        self.repo = UserConsentRepo(session)
        self.publisher = publisher
        self.state = state

    async def create_request(
        self,
        *,
        subject_type: str,
        subject_id: str,
        title: str,
        ticket_id: str | None = None,
        device_id: str | None = None,
        requester_person_id: str | None = None,
        requester_binding_id: str | None = None,
        requester_account_session_id: str | None = None,
        requested_by_actor_id: str | None = None,
        requested_by_role: str | None = None,
        risk_level: str | None = None,
        policy_snapshot: dict[str, Any] | None = None,
        risk_explanation: str | None = None,
        requested_action_payload_redacted: dict[str, Any] | None = None,
        description: str | None = None,
        reason: str | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserConsentRequest:
        pending = await self.repo.get_pending_by_subject(subject_type, subject_id)
        if pending is not None:
            await self._expire_if_due_with_event(pending)
            pending = await self.repo.get_pending_by_subject(subject_type, subject_id)
            if pending is not None:
                return pending

        try:
            async with self.session.begin_nested():
                row = await self.repo.create(
                    consent_id=str(uuid.uuid4()),
                    subject_type=str(subject_type),
                    subject_id=str(subject_id),
                    ticket_id=ticket_id,
                    device_id=device_id,
                    requester_person_id=requester_person_id,
                    requester_binding_id=requester_binding_id,
                    requester_account_session_id=requester_account_session_id,
                    requested_by_actor_id=requested_by_actor_id,
                    requested_by_role=requested_by_role,
                    risk_level=risk_level,
                    policy_snapshot=policy_snapshot or {},
                    risk_explanation=risk_explanation,
                    requested_action_payload_redacted=requested_action_payload_redacted or {},
                    title=_clean(title, max_length=500) or "Consent required",
                    description=_clean(description, max_length=4000),
                    reason=_clean(reason, max_length=1000),
                    expires_at=expires_at,
                    metadata_json=metadata or {},
                    status="pending",
                )
        except IntegrityError as exc:
            if not _integrity_error_matches_constraint(exc, PENDING_SUBJECT_UNIQUE_INDEX):
                raise
            pending = await self.repo.get_pending_by_subject(subject_type, subject_id)
            if pending is not None:
                return pending
            raise
        await self._append_ticket_event(row, "user_consent_requested", actor_id=requested_by_actor_id, actor_role=requested_by_role)
        return row

    async def list_for_requester(self, *, requester_person_id: str | None, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        if not requester_person_id:
            return []
        rows = await self.repo.list_for_person(requester_person_id, statuses=statuses)
        for row in rows:
            await self._expire_if_due_with_event(row)
        rows = await self.repo.list_for_person(requester_person_id, statuses=statuses)
        return [serialize_user_consent(row) for row in rows]

    async def list_for_agent(
        self,
        *,
        device_id: str,
        account_session: dict[str, Any] | None = None,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        person_id = (account_session or {}).get("person_id")
        rows = await self.repo.list_for_device(device_id, person_id=person_id, statuses=statuses)
        for row in rows:
            await self._expire_if_due_with_event(row)
        rows = await self.repo.list_for_device(device_id, person_id=person_id, statuses=statuses)
        return [serialize_user_consent(row) for row in rows]

    async def get_for_requester(self, *, consent_id: str, requester_person_id: str | None) -> UserConsentRequest | None:
        row = await self.repo.get(consent_id)
        if row is None or not requester_person_id or row.requester_person_id != requester_person_id:
            return None
        await self._expire_if_due_with_event(row)
        return await self.repo.get(consent_id)

    async def get_for_agent(
        self,
        *,
        consent_id: str,
        device_id: str,
        account_session: dict[str, Any] | None = None,
    ) -> UserConsentRequest | None:
        row = await self.repo.get(consent_id)
        if row is None or row.device_id != device_id:
            return None
        if account_session and row.requester_person_id != account_session.get("person_id"):
            return None
        await self._expire_if_due_with_event(row)
        return await self.repo.get(consent_id)

    async def decide_from_browser(
        self,
        *,
        consent_id: str,
        decision: str,
        requester_person_id: str | None,
        actor_id: str,
        reason: str | None = None,
    ) -> UserConsentRequest:
        row = await self.get_for_requester(consent_id=consent_id, requester_person_id=requester_person_id)
        if row is None:
            raise ConsentAccessError("consent not found", error_code="NOT_FOUND", status=404)
        return await self._decide(row, decision=decision, actor_id=actor_id, actor_role="requester", surface="browser", reason=reason)

    async def decide_from_agent(
        self,
        *,
        consent_id: str,
        decision: str,
        device_id: str,
        account_session: dict[str, Any],
        actor_id: str,
        reason: str | None = None,
    ) -> UserConsentRequest:
        row = await self.get_for_agent(consent_id=consent_id, device_id=device_id, account_session=account_session)
        if row is None:
            raise ConsentAccessError("consent not found", error_code="NOT_FOUND", status=404)
        if row.requester_account_session_id and row.requester_account_session_id != account_session.get("session_id"):
            raise ConsentAccessError("account session does not match consent", error_code="ACCOUNT_SESSION_MISMATCH", status=403)
        return await self._decide(row, decision=decision, actor_id=actor_id, actor_role="requester", surface="agent_gui", reason=reason)

    async def _decide(
        self,
        row: UserConsentRequest,
        *,
        decision: str,
        actor_id: str,
        actor_role: str,
        surface: str,
        reason: str | None,
    ) -> UserConsentRequest:
        if decision not in {"approved", "denied"}:
            raise ValueError("decision must be approved or denied")
        current = await self.repo.get(row.consent_id)
        if current is None:
            raise ConsentAccessError("consent not found", error_code="NOT_FOUND", status=404)
        if current.status in FINAL_STATUSES:
            return current
        expired = await self._expire_if_due_with_event(current)
        if expired:
            return await self.repo.get(current.consent_id) or current
        current = await self.repo.get(current.consent_id)
        if current is None:
            raise ConsentAccessError("consent not found", error_code="NOT_FOUND", status=404)
        await self._ensure_active_scope(current)
        stale = await self._cancel_if_operation_no_longer_actionable(current)
        if stale is not None:
            return stale

        changed = await self.repo.decide_pending(
            current.consent_id,
            decision=decision,
            actor_id=actor_id,
            actor_role=actor_role,
            surface=surface,
            reason=_clean(reason, max_length=1000),
        )
        decided = await self.repo.get(current.consent_id)
        if decided is None:
            raise ConsentAccessError("consent not found", error_code="NOT_FOUND", status=404)
        if changed:
            await self._append_ticket_event(decided, "user_consent_decided", actor_id=actor_id, actor_role=actor_role)
            await self._apply_subject_decision(decided, decision=decision, actor_id=actor_id, reason=reason)
        return decided

    async def _ensure_active_scope(self, row: UserConsentRequest) -> None:
        now = _now()
        if row.requester_binding_id:
            binding = await self.session.get(DeviceUserBinding, row.requester_binding_id)
            if binding is None or binding.status != "active":
                raise ConsentAccessError("requester binding is not active", error_code="REQUESTER_BINDING_INACTIVE", status=403)
            if row.requester_person_id and binding.person_id != row.requester_person_id:
                raise ConsentAccessError("requester binding mismatch", error_code="REQUESTER_BINDING_MISMATCH", status=403)
            if row.device_id and binding.device_id != row.device_id:
                raise ConsentAccessError("requester binding device mismatch", error_code="REQUESTER_BINDING_MISMATCH", status=403)
        if row.requester_account_session_id:
            account_session = await self.session.get(DeviceAccountSession, row.requester_account_session_id)
            if account_session is None or account_session.verification_status != "verified" or account_session.revoked_at:
                raise ConsentAccessError("requester account session is not active", error_code="ACCOUNT_SESSION_INACTIVE", status=403)
            if account_session.expires_at and account_session.expires_at <= now:
                raise ConsentAccessError("requester account session expired", error_code="ACCOUNT_SESSION_EXPIRED", status=403)
            if row.requester_person_id and account_session.person_id != row.requester_person_id:
                raise ConsentAccessError("requester account session mismatch", error_code="ACCOUNT_SESSION_MISMATCH", status=403)
            if row.device_id and account_session.device_id != row.device_id:
                raise ConsentAccessError("requester account session device mismatch", error_code="ACCOUNT_SESSION_MISMATCH", status=403)

    async def _cancel_if_operation_no_longer_actionable(self, row: UserConsentRequest) -> UserConsentRequest | None:
        if row.subject_type not in OPERATION_SUBJECT_TYPES:
            return None
        operation = await OperationsRepo(self.session).get_by_operation_id(row.subject_id)
        if operation is None or operation.status not in OPERATION_CONSENT_NO_LONGER_ACTIONABLE_STATUSES:
            return None
        reason = f"Operation is {operation.status}; consent is no longer actionable"
        changed = await self.repo.cancel_pending(row.consent_id, reason=reason)
        canceled = await self.repo.get(row.consent_id)
        if changed and canceled is not None:
            await self._append_ticket_event(canceled, "user_consent_canceled", actor_id="system", actor_role="system")
        return canceled or row

    async def _expire_if_due_with_event(self, row: UserConsentRequest) -> bool:
        now = _now()
        if row.status != "pending" or not row.expires_at or row.expires_at > now:
            return False
        changed = await self.repo.expire_if_due(row.consent_id, now=now)
        if changed:
            expired = await self.repo.get(row.consent_id)
            if expired is not None:
                await self._append_ticket_event(expired, "user_consent_expired", actor_id="system", actor_role="system")
        return changed

    async def _apply_subject_decision(self, row: UserConsentRequest, *, decision: str, actor_id: str, reason: str | None) -> None:
        if row.subject_type == "remote_assist":
            await self._apply_remote_assist_decision(row, decision=decision, actor_id=actor_id, reason=reason)
            return
        if row.subject_type not in OPERATION_SUBJECT_TYPES:
            return
        operation = await OperationsRepo(self.session).get_by_operation_id(row.subject_id)
        if operation is None or operation.status != "waiting_consent":
            return
        service = OperationService(self.session, publisher=self.publisher)
        if decision == "approved":
            await service.approve_consent(row.subject_id, decided_by=actor_id, reason=reason)
        else:
            await service.deny_consent(row.subject_id, decided_by=actor_id, reason=reason)

    async def _apply_remote_assist_decision(
        self,
        row: UserConsentRequest,
        *,
        decision: str,
        actor_id: str,
        reason: str | None,
    ) -> None:
        from remote_assist.service import RemoteAssistError, RemoteAssistService

        service = RemoteAssistService(self.session)
        if decision == "approved":
            if self.state is None:
                raise ConsentAccessError("remote assist state is unavailable", error_code="REMOTE_ASSIST_STATE_UNAVAILABLE", status=409)
            try:
                await service.approve_user_consent(
                    session_id=row.subject_id,
                    state=self.state,
                    actor_type=row.decided_from_surface or "user_consent",
                    actor_id=actor_id,
                    consent_id=row.consent_id,
                    reason=reason,
                )
            except RemoteAssistError as exc:
                raise ConsentAccessError(exc.message, error_code=exc.error_code, status=exc.status) from exc
        else:
            try:
                await service.deny_user_consent(
                    session_id=row.subject_id,
                    actor_type=row.decided_from_surface or "user_consent",
                    actor_id=actor_id,
                    consent_id=row.consent_id,
                    reason=reason,
                )
            except RemoteAssistError as exc:
                raise ConsentAccessError(exc.message, error_code=exc.error_code, status=exc.status) from exc

    async def _append_ticket_event(
        self,
        row: UserConsentRequest,
        event_type: str,
        *,
        actor_id: str | None,
        actor_role: str | None,
    ) -> None:
        if not row.ticket_id:
            return
        payload = {
            "consent_id": row.consent_id,
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "status": row.status,
            "risk_level": row.risk_level,
            "title": row.title,
            "decided_from_surface": row.decided_from_surface,
        }
        await TicketEventsRepo(self.session).add_event(
            ticket_id=row.ticket_id,
            device_id=row.device_id,
            agent_seq=None,
            event_type=event_type,
            payload=payload,
            trace_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            operation_id=row.subject_id if row.subject_type in OPERATION_SUBJECT_TYPES else None,
        )
