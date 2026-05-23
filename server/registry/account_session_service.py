from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceAccountLoginRequest, DeviceAccountSession
from app.repos.account_session_repo import AccountSessionRepo
from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo


OTHER_ACCOUNT_WARNING = "ticket_created_from_other_account_on_registered_device"
PENDING_REGISTRATION_CLAIM_STATUSES = {
    "self_reported",
    "pending_user_confirmation",
    "user_confirmed",
    "pending_admin_review",
    "conflict",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Any, *, max_length: int = 320) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if "<script" in text.lower() or "</" in text.lower():
        return ""
    return text[:max_length]


def _token_hash(token: str | None) -> str | None:
    if not token:
        return None
    return sha256(str(token).encode("utf-8")).hexdigest()


def _safe_declared_account(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    result: dict[str, Any] = {}
    for key in ("display_name", "full_name", "login", "email", "phone", "reason"):
        value = _clean(payload.get(key), max_length=500 if key == "reason" else 320)
        if value:
            result[key] = value.lower() if key == "email" else value
    return result


class AccountSessionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AccountSessionRepo(session)
        self.registration_repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    async def _serialize_person(self, person_id: str | None) -> dict[str, Any] | None:
        if not person_id:
            return None
        person = await self.registry_repo.get_person(person_id)
        if person is None:
            return None
        return {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "phone": person.phone,
        }

    async def _person_login(self, person_id: str | None) -> str | None:
        if not person_id:
            return None
        identities = await self.registration_repo.list_identities_for_person(person_id)
        for provider in ("windows_login", "ui_login", "ad", "agent_profile"):
            for identity in identities:
                if str(getattr(identity, "provider", "") or "").lower() == provider:
                    value = _clean(getattr(identity, "identifier", None))
                    if value:
                        return value
        return None

    async def serialize_session(self, row: DeviceAccountSession) -> dict[str, Any]:
        person = await self._serialize_person(row.person_id)
        declared = row.declared_account or {}
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        return {
            "session_id": row.session_id,
            "account_mode": row.account_mode,
            "verification_status": row.verification_status,
            "verification_method": row.verification_method,
            "device_id": row.device_id,
            "person_id": row.person_id,
            "binding_id": row.binding_id,
            "claim_id": row.claim_id,
            "base_binding_id": row.base_binding_id,
            "base_person_id": row.base_person_id,
            "declared_account": declared,
            "reason": row.reason,
            "warning_code": row.warning_code,
            "source_request_id": metadata.get("source_request_id"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "revoked_by": row.revoked_by,
            "display_name": (person or {}).get("display_name") or declared.get("display_name"),
            "full_name": (person or {}).get("full_name") or declared.get("full_name"),
            "email": (person or {}).get("email") or declared.get("email"),
            "phone": (person or {}).get("phone") or declared.get("phone"),
            "login": declared.get("login") or await self._person_login(row.person_id),
            "person": person,
        }

    def serialize_login_request(self, row: DeviceAccountLoginRequest, *, include_session_token: bool = False) -> dict[str, Any]:
        payload = {
            "request_id": row.request_id,
            "device_id": row.device_id,
            "requested_account": row.requested_account or {},
            "matched_person_id": row.matched_person_id,
            "base_binding_id": row.base_binding_id,
            "base_person_id": row.base_person_id,
            "status": row.status,
            "verification_method": row.verification_method,
            "reason": row.reason,
            "requested_at": row.requested_at.isoformat() if row.requested_at else None,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "rejection_reason": row.rejection_reason,
            "resulting_session_id": row.resulting_session_id,
        }
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        if include_session_token and metadata.get("session_token_once"):
            payload["session_token"] = str(metadata.get("session_token_once"))
        return payload

    async def create_confirmed_binding_session(self, *, device_id: str, binding_id: str) -> dict[str, Any]:
        binding = await self.registration_repo.get_active_binding_for_device(device_id, binding_id)
        if binding is None:
            raise ValueError("active binding not found for device")
        token = secrets.token_urlsafe(32)
        row = await self.repo.create_session(
            session_token_hash=_token_hash(token),
            device_id=str(device_id),
            account_mode="confirmed_binding",
            verification_status="verified",
            verification_method="device_binding",
            person_id=binding.person_id,
            binding_id=binding.binding_id,
            verified_at=_now(),
            declared_account={},
            metadata_json={},
        )
        await self.repo.append_event(
            device_id=device_id,
            session_id=row.session_id,
            event_type="confirmed_binding_session_created",
            actor_role="agent",
            payload={"binding_id": binding.binding_id, "person_id": binding.person_id},
        )
        return {"session": await self.serialize_session(row), "session_token": token}

    async def create_registration_pending_session(self, *, device_id: str, claim_id: str) -> dict[str, Any]:
        claim = await self.registration_repo.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        if str(claim.device_id) != str(device_id):
            raise ValueError("registration claim does not belong to device")
        if str(claim.status) not in PENDING_REGISTRATION_CLAIM_STATUSES:
            raise ValueError("registration claim is not pending")
        token = secrets.token_urlsafe(32)
        row = await self.repo.create_session(
            session_token_hash=_token_hash(token),
            device_id=str(device_id),
            account_mode="registration_pending",
            verification_status="pending_verification",
            verification_method="registration_claim",
            person_id=claim.person_id,
            claim_id=claim.claim_id,
            declared_account=claim.profile_snapshot or {},
            metadata_json={"source_claim_id": claim.claim_id},
        )
        await self.repo.append_event(
            device_id=device_id,
            session_id=row.session_id,
            event_type="registration_pending_session_created",
            actor_role="agent",
            payload={"claim_id": claim.claim_id, "claim_status": claim.status},
        )
        return {"session": await self.serialize_session(row), "session_token": token}

    async def _get_base_binding_for_other_account_login(self, device_id: str):
        primary = await self.registration_repo.get_active_primary_binding(device_id)
        if primary is not None:
            return primary
        for binding in await self.registration_repo.list_active_bindings_for_device(device_id):
            if binding.relationship_type in {"responsible", "shared_user"}:
                return binding
        return None

    async def _match_person_id(self, declared: dict[str, Any]) -> str | None:
        email = declared.get("email")
        if email:
            person = await self.registration_repo.find_person_by_identity("email", email)
            if person:
                return person.person_id
        login = declared.get("login")
        if login:
            for provider in ("windows_login", "ui_login", "ad"):
                person = await self.registration_repo.find_person_by_identity(provider, login)
                if person:
                    return person.person_id
        phone = declared.get("phone")
        if phone:
            identity = await self.registration_repo.find_identity("phone", phone)
            if identity and identity.verified:
                return identity.person_id
        return None

    async def create_other_account_login_request(self, *, device_id: str, requested_account: dict[str, Any]) -> dict[str, Any]:
        active = await self._get_base_binding_for_other_account_login(device_id)
        if active is None:
            raise ValueError("active binding required for other account login")
        declared = _safe_declared_account(requested_account)
        if not declared.get("full_name") or not declared.get("login"):
            raise ValueError("full_name and login are required")
        reason = _clean(requested_account.get("reason"), max_length=500)
        if not reason:
            raise ValueError("reason is required")
        declared["reason"] = reason
        matched_person_id = await self._match_person_id(declared)
        row = await self.repo.create_login_request(
            device_id=str(device_id),
            requested_account=declared,
            matched_person_id=matched_person_id,
            base_binding_id=active.binding_id,
            base_person_id=active.person_id,
            status="pending_verification",
            verification_method="admin_approval",
            reason=reason,
            metadata_json={},
        )
        await self.repo.append_event(
            device_id=device_id,
            request_id=row.request_id,
            event_type="other_account_login_requested",
            actor_role="agent",
            payload={"base_binding_id": active.binding_id, "matched_person_id": matched_person_id},
        )
        return self.serialize_login_request(row)

    async def approve_login_request(self, request_id: str, *, reviewed_by: str) -> dict[str, Any]:
        request = await self.repo.get_login_request(request_id)
        if request is None:
            raise ValueError("account login request not found")
        if request.status == "approved" and request.resulting_session_id:
            existing = await self.repo.get_session(request.resulting_session_id)
            if existing:
                return {"request": self.serialize_login_request(request), "session": await self.serialize_session(existing)}
        if request.status != "pending_verification":
            raise ValueError("account login request is not pending")
        declared = dict(request.requested_account or {})
        token = secrets.token_urlsafe(32)
        row = await self.repo.create_session(
            session_token_hash=_token_hash(token),
            device_id=request.device_id,
            account_mode="verified_other_account",
            verification_status="verified",
            verification_method="admin_approval",
            person_id=request.matched_person_id,
            base_binding_id=request.base_binding_id,
            base_person_id=request.base_person_id,
            declared_account=declared,
            reason=request.reason or declared.get("reason"),
            warning_code=OTHER_ACCOUNT_WARNING,
            verified_at=_now(),
            verified_by=reviewed_by,
            metadata_json={"source_request_id": request.request_id},
        )
        request = await self.repo.mark_login_request(
            request.request_id,
            status="approved",
            reviewed_by=reviewed_by,
            resulting_session_id=row.session_id,
        )
        request.metadata_json = {**(request.metadata_json or {}), "session_token_once": token}
        await self.session.flush()
        await self.repo.append_event(
            device_id=row.device_id,
            session_id=row.session_id,
            request_id=request.request_id,
            event_type="other_account_login_approved",
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"matched_person_id": request.matched_person_id, "base_binding_id": request.base_binding_id},
        )
        return {
            "request": self.serialize_login_request(request),
            "session": await self.serialize_session(row),
            "session_token": token,
        }

    async def reject_login_request(self, request_id: str, *, reviewed_by: str, reason: str) -> dict[str, Any]:
        row = await self.repo.mark_login_request(
            request_id,
            status="rejected",
            reviewed_by=reviewed_by,
            rejection_reason=_clean(reason, max_length=500) or "rejected",
        )
        await self.repo.append_event(
            device_id=row.device_id,
            request_id=row.request_id,
            event_type="other_account_login_rejected",
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"reason": row.rejection_reason},
        )
        return self.serialize_login_request(row)

    async def logout_session(
        self,
        *,
        device_id: str,
        session_id: str,
        session_token: str | None = None,
    ) -> dict[str, Any]:
        validation = await self.validate_session(
            device_id=device_id,
            session_id=session_id,
            session_token=session_token,
            touch=False,
            allow_revoked=True,
        )
        row = await self.repo.get_session(session_id)
        if row is None or row.device_id != str(device_id):
            raise ValueError("account session not found")
        if row.verification_status != "revoked" and not validation.get("valid"):
            raise ValueError(str(validation.get("error_code") or "ACCOUNT_SESSION_INVALID"))
        row = await self.repo.revoke_session(session_id, revoked_by="agent", reason="logout")
        await self.repo.append_event(
            device_id=row.device_id,
            session_id=row.session_id,
            event_type="account_session_logged_out",
            actor_id=row.device_id,
            actor_role="agent",
        )
        return await self.serialize_session(row)

    async def revoke_session(self, *, session_id: str, revoked_by: str, reason: str | None = None) -> dict[str, Any]:
        row = await self.repo.revoke_session(session_id, revoked_by=revoked_by, reason=_clean(reason, max_length=500) or None)
        await self.repo.append_event(
            device_id=row.device_id,
            session_id=row.session_id,
            event_type="account_session_revoked",
            actor_id=revoked_by,
            actor_role="admin",
            payload={"reason": reason} if reason else {},
        )
        return await self.serialize_session(row)

    async def touch_session(self, *, session_id: str) -> None:
        row = await self.repo.get_session(session_id)
        if row is None:
            return
        row.metadata_json = {**(row.metadata_json or {}), "last_validated_at": _now().isoformat()}
        await self.session.flush()

    async def validate_session(
        self,
        *,
        device_id: str,
        session_id: str,
        session_token: str | None = None,
        touch: bool = True,
        allow_revoked: bool = False,
    ) -> dict[str, Any]:
        row = await self.repo.get_session(session_id)
        if row is None or row.device_id != str(device_id):
            return {"valid": False, "error_code": "ACCOUNT_SESSION_NOT_FOUND"}
        if row.verification_status == "revoked":
            payload = {"valid": False, "error_code": "ACCOUNT_SESSION_REVOKED", "session": await self.serialize_session(row)}
            if allow_revoked:
                return {"valid": True, "session": payload["session"], "already_revoked": True}
            return payload
        if row.expires_at and row.expires_at <= _now():
            row.verification_status = "expired"
            await self.session.flush()
            return {"valid": False, "error_code": "ACCOUNT_SESSION_EXPIRED", "session": await self.serialize_session(row)}
        if row.session_token_hash and session_token and row.session_token_hash != _token_hash(session_token):
            return {"valid": False, "error_code": "ACCOUNT_SESSION_TOKEN_INVALID", "session": await self.serialize_session(row)}
        if row.session_token_hash and not session_token:
            return {"valid": False, "error_code": "ACCOUNT_SESSION_TOKEN_REQUIRED", "session": await self.serialize_session(row)}
        if row.account_mode == "registration_pending":
            if row.verification_status != "pending_verification":
                return {"valid": False, "error_code": "ACCOUNT_SESSION_NOT_PENDING", "session": await self.serialize_session(row)}
            if not row.claim_id:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_CLAIM_INACTIVE", "session": await self.serialize_session(row)}
            claim = await self.registration_repo.get_claim(row.claim_id)
            if claim is None or str(claim.device_id) != str(row.device_id):
                return {"valid": False, "error_code": "ACCOUNT_SESSION_CLAIM_INACTIVE", "session": await self.serialize_session(row)}
            if claim.status == "approved":
                return {"valid": False, "error_code": "ACCOUNT_SESSION_CLAIM_APPROVED", "session": await self.serialize_session(row)}
            if claim.status not in PENDING_REGISTRATION_CLAIM_STATUSES:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_CLAIM_INACTIVE", "session": await self.serialize_session(row)}
            if touch:
                await self.touch_session(session_id=row.session_id)
            return {"valid": True, "session": await self.serialize_session(row)}
        if row.verification_status != "verified":
            return {"valid": False, "error_code": "ACCOUNT_SESSION_NOT_VERIFIED", "session": await self.serialize_session(row)}
        if row.account_mode == "confirmed_binding":
            if not row.binding_id:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_BINDING_INACTIVE", "session": await self.serialize_session(row)}
            binding = await self.registration_repo.get_active_binding_for_device(row.device_id, row.binding_id)
            if binding is None:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_BINDING_INACTIVE", "session": await self.serialize_session(row)}
        if row.account_mode == "verified_other_account":
            if not row.base_binding_id:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_BASE_BINDING_INACTIVE", "session": await self.serialize_session(row)}
            binding = await self.registration_repo.get_active_binding_for_device(row.device_id, row.base_binding_id)
            if binding is None:
                return {"valid": False, "error_code": "ACCOUNT_SESSION_BASE_BINDING_INACTIVE", "session": await self.serialize_session(row)}
        if touch:
            await self.touch_session(session_id=row.session_id)
        return {"valid": True, "session": await self.serialize_session(row)}

    async def list_device_sessions(self, device_id: str) -> list[dict[str, Any]]:
        rows = await self.repo.list_sessions_for_device(device_id, verification_status=None)
        return [await self.serialize_session(row) for row in rows]

    async def list_sessions_for_device_admin(self, device_id: str) -> list[dict[str, Any]]:
        return await self.list_device_sessions(device_id)

    async def list_pending_login_requests_for_device(self, device_id: str) -> list[dict[str, Any]]:
        rows = await self.repo.list_login_requests(device_id=device_id, status="pending_verification")
        return [self.serialize_login_request(row) for row in rows]

    async def list_login_requests(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self.repo.list_login_requests(status=status, limit=limit)
        return [self.serialize_login_request(row) for row in rows]
