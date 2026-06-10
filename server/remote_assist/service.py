from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.db.models import Device, RemoteAccessSession, Ticket
from app.repos.devices_repo import DevicesRepo
from app.repos.remote_access_repo import RemoteAccessRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from consent.service import UserConsentService
from remote_assist.features import build_remote_assist_features
from remote_assist.ice import build_remote_assist_ice_servers
from remote_assist.media import build_remote_assist_media_options
from remote_assist.policy import (
    get_remote_assist_feature_flags,
    get_remote_assist_mode_policy,
    is_remote_assist_mode_enabled,
    normalize_remote_assist_mode,
)
from tickets.statuses import TERMINAL_STATUSES


class RemoteAssistError(Exception):
    def __init__(self, error_code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class IssuedToken:
    token: str
    token_hash: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_short_lived_token() -> IssuedToken:
    token = secrets.token_urlsafe(32)
    return IssuedToken(token=token, token_hash=_hash_token(token))


def verify_token_hash(token: str, expected_hash: str | None) -> bool:
    if not token or not expected_hash:
        return False
    return secrets.compare_digest(_hash_token(token), expected_hash)


def _remote_assist_risk_level(mode: str) -> str:
    if mode == "view_only":
        return "remote_view"
    if mode in {"interactive_control", "file_transfer"}:
        return "remote_control"
    if mode == "elevated_admin":
        return "remote_admin"
    return "remote_assist"


def _remote_assist_title(mode: str) -> str:
    labels = {
        "view_only": "Подтвердите просмотр экрана",
        "interactive_control": "Подтвердите удаленное управление",
        "file_transfer": "Подтвердите передачу файлов",
        "elevated_admin": "Подтвердите административную удаленную помощь",
    }
    return labels.get(mode, "Подтвердите удаленную помощь")


def _remote_assist_description(mode: str, duration_minutes: int) -> str:
    labels = {
        "view_only": "Специалист сможет видеть экран этого устройства.",
        "interactive_control": "Специалист сможет видеть экран и управлять мышью и клавиатурой.",
        "file_transfer": "Специалист сможет видеть экран и использовать канал передачи файлов.",
        "elevated_admin": "Специалист запросил административный режим удаленной помощи.",
    }
    return f"{labels.get(mode, 'Специалист запросил удаленную помощь.')} Максимальная длительность: {duration_minutes} мин."


def remote_session_to_dict(session: RemoteAccessSession) -> dict[str, Any]:
    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "session_id": session.id,
        "ticket_id": session.ticket_id,
        "device_id": session.device_id,
        "operator_id": session.operator_id,
        "requester_id": session.requester_id,
        "mode": session.mode,
        "status": session.status,
        "reason": session.reason,
        "consent_required": session.consent_required,
        "consent_status": session.consent_status,
        "requested_at": iso(session.requested_at),
        "approved_at": iso(session.approved_at),
        "denied_at": iso(session.denied_at),
        "started_at": iso(session.started_at),
        "ended_at": iso(session.ended_at),
        "expires_at": iso(session.expires_at),
        "max_duration_sec": session.max_duration_sec,
        "close_reason": session.close_reason,
        "error_code": session.error_code,
        "error_message": session.error_message,
        "ice_servers": (session.ice_config or {}).get("ice_servers", []),
        "media": (session.ice_config or {}).get("media", build_remote_assist_media_options()),
        "features": (session.ice_config or {}).get("features", build_remote_assist_features()),
    }


class RemoteAssistService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RemoteAccessRepo(session)

    async def request_session(
        self,
        *,
        state: Any,
        ticket_id: str,
        device_id: str,
        operator_id: str,
        requester_id: str | None,
        mode: str,
        reason: str | None,
        duration_minutes: int | None,
        media_options: dict[str, Any] | None = None,
        feature_options: dict[str, Any] | None = None,
    ) -> RemoteAccessSession:
        if not config.REMOTE_ASSIST_ENABLED:
            raise RemoteAssistError("REMOTE_ASSIST_DISABLED", "Remote Assist is disabled", status=403)
        mode = normalize_remote_assist_mode(mode)
        mode_policy = get_remote_assist_mode_policy(mode)
        if mode_policy is None or not is_remote_assist_mode_enabled(mode):
            raise RemoteAssistError("MODE_NOT_ALLOWED", "Remote Assist mode is not allowed", status=403)

        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise RemoteAssistError("TICKET_NOT_FOUND", "Ticket not found", status=404)
        normalized_status = str(ticket.status or "").strip().lower()
        if normalized_status in TERMINAL_STATUSES:
            raise RemoteAssistError("TICKET_CLOSED", "Ticket is closed or canceled", status=409)
        if str(ticket.device_id or "") != str(device_id or ""):
            raise RemoteAssistError("DEVICE_NOT_LINKED", "Device is not linked to ticket", status=403)
        if not getattr(ticket, "requester_person_id", None):
            raise RemoteAssistError(
                "REQUESTER_SCOPE_REQUIRED",
                "Remote Assist consent requires a requester-scoped ticket",
                status=409,
            )

        device = await DevicesRepo(self.session).get_by_device_id(device_id, include_deleted=False)
        if device is None:
            raise RemoteAssistError("DEVICE_NOT_FOUND", "Device not found", status=404)
        if not self._is_device_online(state, device_id):
            raise RemoteAssistError("DEVICE_OFFLINE", "Device is offline", status=409)

        active = await self.repo.active_for_ticket_device(ticket_id, device_id)
        if active is not None:
            raise RemoteAssistError("ACTIVE_SESSION_EXISTS", "Remote Assist session already exists", status=409)

        duration = int(duration_minutes or config.REMOTE_ASSIST_DEFAULT_DURATION_MINUTES)
        duration = max(1, min(duration, config.REMOTE_ASSIST_MAX_DURATION_MINUTES))
        consent_required = True
        if not consent_required:
            raise RemoteAssistError("UNATTENDED_NOT_ALLOWED", "Unattended access is not allowed", status=403)

        expires_at = _utcnow() + timedelta(minutes=config.REMOTE_ASSIST_CONSENT_TIMEOUT_MINUTES)
        remote_session = await self.repo.create_session(
            ticket_id=ticket.ticket_id,
            device_id=device.device_id,
            operator_id=operator_id,
            requester_id=requester_id or getattr(ticket, "requester_id", None),
            mode=mode,
            status="waiting_consent" if consent_required else "approved",
            reason=(reason or "").strip() or None,
            consent_required=consent_required,
            consent_status="pending" if consent_required else "not_required",
            expires_at=expires_at,
            max_duration_sec=duration * 60,
            ice_config={
                "ice_servers": build_remote_assist_ice_servers(),
                "media": build_remote_assist_media_options(media_options),
                "features": build_remote_assist_features(feature_options),
            },
        )
        await self.log_event(
            remote_session,
            "requested",
            actor_type="operator",
            actor_id=operator_id,
            payload={"mode": mode, "reason": reason, "duration_minutes": duration},
            write_timeline=True,
        )
        await UserConsentService(self.session).create_request(
            subject_type="remote_assist",
            subject_id=remote_session.id,
            ticket_id=remote_session.ticket_id,
            device_id=remote_session.device_id,
            requester_person_id=getattr(ticket, "requester_person_id", None),
            requester_binding_id=getattr(ticket, "requester_binding_id", None),
            requester_account_session_id=getattr(ticket, "requester_account_session_id", None),
            requested_by_actor_id=operator_id,
            requested_by_role="support",
            risk_level=_remote_assist_risk_level(mode),
            policy_snapshot={
                "mode": mode,
                "duration_minutes": duration,
                "consent_timeout_minutes": config.REMOTE_ASSIST_CONSENT_TIMEOUT_MINUTES,
                "features": get_remote_assist_feature_flags(),
            },
            risk_explanation=_remote_assist_description(mode, duration),
            requested_action_payload_redacted={
                "session_id": remote_session.id,
                "mode": mode,
                "duration_minutes": duration,
                "reason": reason,
                "media": (remote_session.ice_config or {}).get("media", {}),
                "features": (remote_session.ice_config or {}).get("features", {}),
            },
            title=_remote_assist_title(mode),
            description=_remote_assist_description(mode, duration),
            reason=reason,
            expires_at=expires_at,
            metadata={
                "remote_assist_session_id": remote_session.id,
                "mode": mode,
                "operator_id": operator_id,
            },
        )
        return remote_session

    async def send_request_to_agent(
        self,
        *,
        state: Any,
        remote_session: RemoteAccessSession,
        consent_id: str | None = None,
        consent_status: str | None = None,
    ) -> str:
        ticket = await self.session.get(Ticket, remote_session.ticket_id)
        if ticket is None:
            raise RemoteAssistError("TICKET_NOT_FOUND", "Ticket not found", status=404)
        from websocket.protocol import enqueue_command_async

        command_id = await enqueue_command_async(
            state,
            device_id=remote_session.device_id,
            command="remote_assist.request",
            params={
                "type": "remote_assist.request",
                "session_id": remote_session.id,
                "ticket_id": remote_session.ticket_id,
                "ticket_code": getattr(ticket, "ticket_code", None),
                "device_id": remote_session.device_id,
                "operator_id": remote_session.operator_id,
                "mode": remote_session.mode,
                "reason": remote_session.reason,
                "duration_minutes": max(1, int(remote_session.max_duration_sec / 60)),
                "expires_at": remote_session.expires_at.isoformat(),
                "consent_id": consent_id,
                "consent_status": consent_status,
                "features": get_remote_assist_feature_flags(),
                "session_features": (remote_session.ice_config or {}).get("features", build_remote_assist_features()),
                "media": (remote_session.ice_config or {}).get("media", build_remote_assist_media_options()),
            },
            actor_role="support",
            ticket_id=remote_session.ticket_id,
            require_online=True,
        )
        await self.log_event(
            remote_session,
            "consent_prompt_sent",
            actor_type="system",
            actor_id=None,
            payload={"command_id": command_id},
            write_timeline=False,
        )
        return command_id

    async def approve_user_consent(
        self,
        *,
        session_id: str,
        state: Any,
        actor_type: str,
        actor_id: str | None,
        consent_id: str,
        reason: str | None = None,
    ) -> RemoteAccessSession:
        remote_session = await self._get_or_404(session_id)
        if remote_session.status in {"ended", "denied", "expired", "failed", "canceled"}:
            return remote_session
        if remote_session.expires_at <= _utcnow():
            await self.expire_session(remote_session, actor_type="system", reason="consent_timeout")
            raise RemoteAssistError("CONSENT_TIMEOUT", "Remote Assist request expired", status=409)
        remote_session.consent_status = "approved"
        remote_session.updated_at = _utcnow()
        await self.session.flush()
        await self.log_event(
            remote_session,
            "consent_approved",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"consent_id": consent_id, "reason": reason, "source": "user_consent"},
            write_timeline=True,
        )
        await self.send_request_to_agent(
            state=state,
            remote_session=remote_session,
            consent_id=consent_id,
            consent_status="approved",
        )
        return remote_session

    async def deny_user_consent(
        self,
        *,
        session_id: str,
        actor_type: str,
        actor_id: str | None,
        consent_id: str,
        reason: str | None = None,
    ) -> RemoteAccessSession:
        remote_session = await self._get_or_404(session_id)
        if remote_session.status in {"ended", "denied", "expired", "failed", "canceled"}:
            return remote_session
        await self.repo.set_status(
            remote_session,
            status="denied",
            consent_status="denied",
            close_reason=reason or "user_denied",
            error_code="USER_DENIED",
        )
        await self.log_event(
            remote_session,
            "consent_denied",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"consent_id": consent_id, "reason": reason or "user_denied", "source": "user_consent"},
            write_timeline=True,
        )
        return remote_session

    async def approve_session(self, *, session_id: str, device_id: str) -> tuple[RemoteAccessSession, str]:
        remote_session = await self._get_or_404(session_id)
        self._assert_device(remote_session, device_id)
        if remote_session.status not in {"waiting_consent", "requested"}:
            raise RemoteAssistError("INVALID_SESSION_STATUS", "Session cannot be approved", status=409)
        if remote_session.expires_at <= _utcnow():
            await self.expire_session(remote_session, actor_type="system", reason="consent_timeout")
            raise RemoteAssistError("CONSENT_TIMEOUT", "Remote Assist request expired", status=409)

        token = issue_short_lived_token()
        remote_session.agent_token_hash = token.token_hash
        await self.repo.set_status(
            remote_session,
            status="approved",
            consent_status="approved",
            expires_at=_utcnow() + timedelta(seconds=remote_session.max_duration_sec),
        )
        await self.log_event(
            remote_session,
            "consent_approved",
            actor_type="agent",
            actor_id=device_id,
            payload={},
            write_timeline=True,
        )
        return remote_session, token.token

    async def deny_session(self, *, session_id: str, device_id: str, reason: str | None) -> RemoteAccessSession:
        remote_session = await self._get_or_404(session_id)
        self._assert_device(remote_session, device_id)
        if remote_session.status in {"ended", "denied", "expired", "failed", "canceled"}:
            return remote_session
        await self.repo.set_status(
            remote_session,
            status="denied",
            consent_status="denied",
            close_reason=reason or "user_denied",
            error_code="USER_DENIED",
        )
        await self.log_event(
            remote_session,
            "consent_denied",
            actor_type="agent",
            actor_id=device_id,
            payload={"reason": reason or "user_denied"},
            write_timeline=True,
        )
        return remote_session

    async def end_session(self, *, session_id: str, actor_type: str, actor_id: str | None, reason: str | None) -> RemoteAccessSession:
        remote_session = await self._get_or_404(session_id)
        if remote_session.status in {"ended", "denied", "expired", "failed", "canceled"}:
            return remote_session
        await self.repo.set_status(remote_session, status="ended", close_reason=reason or "finished")
        await self.log_event(
            remote_session,
            "session_ended",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"reason": reason or "finished", "duration_sec": self._duration_sec(remote_session)},
            write_timeline=True,
        )
        return remote_session

    async def fail_session(
        self,
        *,
        session_id: str,
        actor_type: str,
        actor_id: str | None,
        error_code: str,
        error_message: str,
    ) -> RemoteAccessSession:
        remote_session = await self._get_or_404(session_id)
        if remote_session.status in {"ended", "denied", "expired", "failed", "canceled"}:
            return remote_session
        await self.repo.set_status(
            remote_session,
            status="failed",
            close_reason=error_code,
            error_code=error_code,
            error_message=error_message,
        )
        await self.log_event(
            remote_session,
            "session_failed",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"error_code": error_code, "error_message": error_message},
            write_timeline=True,
        )
        return remote_session

    async def get_viewer_info(self, *, session_id: str, operator_id: str, is_admin: bool = False) -> tuple[RemoteAccessSession, str]:
        remote_session = await self._get_or_404(session_id)
        if not is_admin and str(remote_session.operator_id) != str(operator_id):
            raise RemoteAssistError("PERMISSION_DENIED", "Operator does not own this session", status=403)
        if remote_session.expires_at <= _utcnow() and remote_session.status in {"waiting_consent", "approved", "starting", "active"}:
            await self.expire_session(remote_session, actor_type="system", reason="timeout")
            raise RemoteAssistError("SESSION_EXPIRED", "Remote Assist session expired", status=409)
        if remote_session.status not in {"approved", "starting", "active"}:
            return remote_session, ""
        token = issue_short_lived_token()
        remote_session.operator_token_hash = token.token_hash
        remote_session.updated_at = _utcnow()
        await self.session.flush()
        return remote_session, token.token

    async def expire_old_sessions(self) -> int:
        expired = await self.repo.expired_active_sessions()
        for remote_session in expired:
            await self.expire_session(remote_session, actor_type="system", reason="timeout")
        return len(expired)

    async def expire_session(self, remote_session: RemoteAccessSession, *, actor_type: str, reason: str) -> RemoteAccessSession:
        await self.repo.set_status(
            remote_session,
            status="expired",
            consent_status="expired" if remote_session.consent_status == "pending" else None,
            close_reason=reason,
            error_code="SESSION_EXPIRED" if reason != "consent_timeout" else "CONSENT_TIMEOUT",
        )
        await self.log_event(
            remote_session,
            "session_expired",
            actor_type=actor_type,
            actor_id=None,
            payload={"reason": reason},
            write_timeline=True,
        )
        return remote_session

    async def log_event(
        self,
        remote_session: RemoteAccessSession,
        event_type: str,
        *,
        actor_type: str,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
        write_timeline: bool = False,
    ) -> None:
        payload = payload or {}
        await self.repo.add_event(
            session_id=remote_session.id,
            ticket_id=remote_session.ticket_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            payload=payload,
        )
        if write_timeline:
            await self._append_ticket_timeline(remote_session, event_type, actor_type, actor_id, payload)

    async def _append_ticket_timeline(
        self,
        remote_session: RemoteAccessSession,
        event_type: str,
        actor_type: str,
        actor_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        ticket_event_type = f"remote_assist_{event_type}"
        timeline_payload = {
            "event_id": f"remote-assist-{remote_session.id}-{event_type}",
            "session_id": remote_session.id,
            "mode": remote_session.mode,
            "status": remote_session.status,
            "consent_status": remote_session.consent_status,
            "operator_id": remote_session.operator_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "reason": remote_session.reason,
            **payload,
        }
        await TicketEventsRepo(self.session).add_event(
            ticket_id=remote_session.ticket_id,
            device_id=remote_session.device_id,
            agent_seq=None,
            event_type=ticket_event_type,
            payload=timeline_payload,
            event_id=timeline_payload["event_id"],
        )

    async def _get_or_404(self, session_id: str) -> RemoteAccessSession:
        remote_session = await self.repo.get(session_id)
        if remote_session is None:
            raise RemoteAssistError("SESSION_NOT_FOUND", "Remote Assist session not found", status=404)
        return remote_session

    @staticmethod
    def _assert_device(remote_session: RemoteAccessSession, device_id: str) -> None:
        if str(remote_session.device_id) != str(device_id):
            raise RemoteAssistError("PERMISSION_DENIED", "Agent device does not match session", status=403)

    @staticmethod
    def _is_device_online(state: Any, device_id: str) -> bool:
        checker = getattr(state, "is_agent_online", None)
        if callable(checker):
            return bool(checker(device_id))
        return bool(getattr(state, "get_agent", lambda _device_id: None)(device_id))

    @staticmethod
    def _duration_sec(remote_session: RemoteAccessSession) -> int:
        if remote_session.started_at and remote_session.ended_at:
            return max(0, int((remote_session.ended_at - remote_session.started_at).total_seconds()))
        if remote_session.started_at:
            return max(0, int((_utcnow() - remote_session.started_at).total_seconds()))
        return 0
