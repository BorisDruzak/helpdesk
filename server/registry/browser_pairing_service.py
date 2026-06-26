from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceBrowserPairing, RegistryPerson
from app.repos.account_session_repo import AccountSessionRepo
from app.repos.browser_pairing_repo import BrowserPairingRepo
from app.repos.registration_repo import RegistrationRepo
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService


BROWSER_PAIRING_TTL_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    return sha256(str(secret).encode("utf-8")).hexdigest()


def _clean_text(value: object, *, max_length: int = 500) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length] if text else None


def _normalize_pairing_code(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _new_pairing_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _profile_from_actor(actor_id: str) -> dict[str, Any]:
    clean = _clean_text(actor_id, max_length=320) or "Web user"
    profile: dict[str, Any] = {
        "full_name": clean,
        "display_name": clean,
        "login": clean,
        "relationship_type": "primary_user",
        "user_confirmed": True,
    }
    if "@" in clean:
        profile["email"] = clean.lower()
    return profile


def _profile_from_person(actor_id: str, person: RegistryPerson) -> dict[str, Any]:
    profile = _profile_from_actor(actor_id)
    metadata = person.metadata_json or {}
    full_name = _clean_text(person.full_name or person.display_name, max_length=320)
    if full_name:
        profile["full_name"] = full_name
        profile["display_name"] = full_name
    if person.email:
        profile["email"] = person.email
    if person.phone:
        profile["phone"] = person.phone
    if person.department_id:
        profile["department_id"] = person.department_id
    if person.location_id:
        profile["location_id"] = person.location_id
    for key in ("position", "workplace_label", "preferred_contact_method"):
        value = _clean_text(metadata.get(key), max_length=500)
        if value:
            profile[key] = value
    return profile


class BrowserPairingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BrowserPairingRepo(session)
        self.registration_repo = RegistrationRepo(session)
        self.account_session_repo = AccountSessionRepo(session)

    async def serialize_pairing(self, row: DeviceBrowserPairing) -> dict[str, Any]:
        return {
            "pairing_id": row.pairing_id,
            "device_id": row.device_id,
            "purpose": row.purpose,
            "status": row.status,
            "resulting_account_session_id": row.resulting_account_session_id,
            "confirmed_person_id": row.confirmed_person_id,
            "binding_id": row.binding_id,
            "claim_id": row.claim_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
            "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }

    async def _expire_if_needed(self, row: DeviceBrowserPairing) -> bool:
        if row.status in {"pending", "confirmed"} and row.expires_at <= _now():
            row.status = "expired"
            row.completed_at = _now()
            await self.session.flush()
            return True
        return False

    async def expire_stale_pairings(self, *, limit: int = 500) -> dict[str, Any]:
        now = _now()
        result = await self.session.execute(
            select(DeviceBrowserPairing)
            .where(DeviceBrowserPairing.status.in_(["pending", "confirmed"]))
            .where(DeviceBrowserPairing.expires_at.is_not(None))
            .where(DeviceBrowserPairing.expires_at <= now)
            .order_by(DeviceBrowserPairing.expires_at)
            .limit(max(1, min(int(limit or 500), 1000)))
        )
        rows = list(result.scalars().all())
        for row in rows:
            row.status = "expired"
            row.completed_at = row.completed_at or now
            row.metadata_json = {**(row.metadata_json or {}), "completion_reason": "expired_cleanup"}
        if rows:
            await self.session.flush()
        return {"expired_count": len(rows), "pairing_ids": [row.pairing_id for row in rows]}

    async def create_pairing(
        self,
        *,
        device_id: str,
        purpose: str,
        actor_id: str | None = None,
        agent_version: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        purpose = str(purpose or "").strip().lower()
        if purpose not in {"login", "registration"}:
            raise ValueError("unsupported browser pairing purpose")
        for pending in await self.repo.list_pending_for_device_purpose(device_id=device_id, purpose=purpose):
            await self.repo.mark_superseded(pending)
        token = secrets.token_urlsafe(32)
        code = _new_pairing_code()
        row = await self.repo.create_pairing(
            device_id=str(device_id),
            purpose=purpose,
            status="pending",
            pairing_token_hash=_hash_secret(token),
            pairing_code_hash=_hash_secret(code),
            created_at=_now(),
            expires_at=_now() + timedelta(minutes=BROWSER_PAIRING_TTL_MINUTES),
            metadata_json={
                "actor_id": _clean_text(actor_id, max_length=200),
                "agent_version": _clean_text(agent_version, max_length=80),
                "user_agent": _clean_text(user_agent, max_length=300),
            },
        )
        await self.account_session_repo.append_event(
            device_id=str(device_id),
            event_type="browser_pairing_created",
            actor_id=actor_id,
            actor_role="agent",
            payload={"pairing_id": row.pairing_id, "purpose": row.purpose},
        )
        payload = await self.serialize_pairing(row)
        route_purpose = "register" if row.purpose == "registration" else row.purpose
        payload.update(
            {
                "pairing_token": token,
                "pairing_code": code,
                "browser_url": f"/app/device/{route_purpose}?pairing_id={row.pairing_id}",
                "poll_url": f"/api/registry/agent/browser-pairings/{row.pairing_id}",
            }
        )
        return payload

    async def lookup_by_pairing_code(self, pairing_code: str) -> dict[str, Any] | None:
        normalized = _normalize_pairing_code(pairing_code)
        if not normalized:
            return None
        row = await self.repo.find_pending_by_code_hash(str(_hash_secret(normalized)))
        if row is None:
            return None
        if await self._expire_if_needed(row):
            return None
        return await self.serialize_pairing(row)

    async def get_browser_visible_pairing(self, pairing_id: str) -> DeviceBrowserPairing | None:
        row = await self.repo.get_pairing(pairing_id)
        if row is None:
            return None
        if await self._expire_if_needed(row):
            return None
        if row.status not in {"pending", "confirmed"}:
            return None
        return row

    async def _require_pending_pairing(self, pairing_id: str, pairing_token: str | None) -> DeviceBrowserPairing:
        row = await self.repo.get_pairing(pairing_id)
        if row is None:
            raise ValueError("browser pairing not found")
        if await self._expire_if_needed(row):
            raise ValueError("browser pairing expired")
        if row.status != "pending":
            raise ValueError("browser pairing is not pending")
        if not pairing_token or not hmac.compare_digest(str(row.pairing_token_hash), str(_hash_secret(pairing_token) or "")):
            raise ValueError("browser pairing token is invalid")
        return row

    async def _require_pending_pairing_link(self, pairing_id: str, *, purpose: str) -> DeviceBrowserPairing:
        row = await self.repo.get_pairing(pairing_id)
        if row is None:
            raise ValueError("browser pairing not found")
        if await self._expire_if_needed(row):
            raise ValueError("browser pairing expired")
        if row.status != "pending":
            raise ValueError("browser pairing is not pending")
        if row.purpose != purpose:
            raise ValueError(f"browser pairing purpose is not {purpose}")
        return row

    async def _resolve_person_for_actor(self, actor_id: str | None):
        actor = _clean_text(actor_id, max_length=320)
        if not actor:
            return None
        providers = ["ui_login"]
        if "@" in actor:
            providers.append("email")
        providers.extend(["windows_login", "ad"])
        for provider in providers:
            person = await self.registration_repo.find_person_by_identity(provider, actor)
            if person is not None:
                return person
        if "\\" in actor:
            local = actor.split("\\", 1)[1]
            person = await self.registration_repo.find_person_by_identity("ui_login", local)
            if person is not None:
                return person
        if "@" in actor:
            local = actor.split("@", 1)[0]
            person = await self.registration_repo.find_person_by_identity("ui_login", local)
            if person is not None:
                return person
        return None

    async def confirm_login_pairing(
        self,
        *,
        pairing_id: str,
        pairing_token: str,
        binding_id: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        row = await self._require_pending_pairing(pairing_id, pairing_token)
        if row.purpose != "login":
            raise ValueError("browser pairing purpose is not login")
        binding = await self.registration_repo.get_active_binding_for_device(row.device_id, binding_id)
        if binding is None:
            raise ValueError("active binding not found for device")
        row.status = "confirmed"
        row.binding_id = binding.binding_id
        row.confirmed_person_id = binding.person_id
        row.confirmed_at = _now()
        row.confirmed_by = _clean_text(actor_id, max_length=200)
        row.metadata_json = {**(row.metadata_json or {}), "confirmation_method": "browser_binding"}
        await self.session.flush()
        await self.account_session_repo.append_event(
            device_id=row.device_id,
            event_type="browser_pairing_confirmed",
            actor_id=actor_id,
            actor_role="browser",
            payload={"pairing_id": row.pairing_id, "binding_id": binding.binding_id, "person_id": binding.person_id},
        )
        return await self.serialize_pairing(row)

    async def confirm_login_pairing_for_web_user(
        self,
        *,
        pairing_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        row = await self._require_pending_pairing_link(pairing_id, purpose="login")
        person = await self._resolve_person_for_actor(actor_id)
        if person is None:
            raise ValueError("active binding not found for web user")
        binding = next(
            (
                item
                for item in await self.registration_repo.list_active_bindings_for_device(row.device_id)
                if item.person_id == person.person_id
                and item.relationship_type in {"primary_user", "shared_user", "responsible"}
            ),
            None,
        )
        if binding is None:
            raise ValueError("active binding not found for web user")
        row.status = "confirmed"
        row.binding_id = binding.binding_id
        row.confirmed_person_id = person.person_id
        row.confirmed_at = _now()
        row.confirmed_by = _clean_text(actor_id, max_length=200)
        row.metadata_json = {**(row.metadata_json or {}), "confirmation_method": "web_user_login"}
        await self.session.flush()
        await self.account_session_repo.append_event(
            device_id=row.device_id,
            event_type="browser_pairing_confirmed",
            actor_id=actor_id,
            actor_role="user",
            payload={"pairing_id": row.pairing_id, "binding_id": binding.binding_id, "person_id": person.person_id},
        )
        return await self.serialize_pairing(row)

    async def confirm_registration_pairing_for_web_user(
        self,
        *,
        pairing_id: str,
        actor_id: str,
        profile_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = await self._require_pending_pairing_link(pairing_id, purpose="registration")
        person = await self._resolve_person_for_actor(actor_id)
        profile = _profile_from_person(actor_id, person) if person is not None else _profile_from_actor(actor_id)
        if profile_updates:
            for key in ("department_id", "location_id"):
                value = _clean_text(profile_updates.get(key), max_length=36)
                if value and not profile.get(key):
                    profile[key] = value
        result = await RegistrationService(self.session).submit_agent_profile_claim(
            device_id=row.device_id,
            requester_id=actor_id,
            display_name=profile.get("display_name"),
            profile=profile,
            actor_id=actor_id,
            actor_role="user",
        )
        claim_id = ((result.get("registration") or {}).get("claim_id") or None)
        person_id = ((result.get("person") or {}).get("person_id") or None)
        row.status = "confirmed"
        row.claim_id = claim_id
        row.confirmed_person_id = person_id
        row.confirmed_at = _now()
        row.confirmed_by = _clean_text(actor_id, max_length=200)
        row.metadata_json = {**(row.metadata_json or {}), "confirmation_method": "web_user_registration"}
        await self.session.flush()
        await self.account_session_repo.append_event(
            device_id=row.device_id,
            event_type="browser_pairing_confirmed",
            actor_id=actor_id,
            actor_role="user",
            payload={"pairing_id": row.pairing_id, "claim_id": claim_id, "person_id": person_id},
        )
        payload = await self.serialize_pairing(row)
        registration = dict(result.get("registration") or {})
        registration["device_id"] = row.device_id
        payload["registration"] = registration
        payload["person"] = result.get("person")
        if result.get("binding"):
            payload["binding"] = result.get("binding")
        payload["claim_id"] = claim_id
        return payload

    async def pickup_agent_result(self, *, device_id: str, pairing_id: str) -> dict[str, Any]:
        row = await self.repo.get_pairing(pairing_id)
        if row is None or row.device_id != str(device_id):
            raise ValueError("browser pairing not found")
        if await self._expire_if_needed(row):
            return await self.serialize_pairing(row)
        if row.status == "pending":
            return await self.serialize_pairing(row)
        if row.status == "consumed":
            payload = await self.serialize_pairing(row)
            if row.resulting_account_session_id:
                session_row = await self.account_session_repo.get_session(row.resulting_account_session_id)
                if session_row:
                    payload["session"] = await AccountSessionService(self.session).serialize_session(session_row)
            return payload
        if row.status != "confirmed":
            return await self.serialize_pairing(row)
        if row.purpose == "registration":
            created_session: dict[str, Any] | None = None
            if row.claim_id:
                claim = await self.registration_repo.get_claim(row.claim_id)
                if claim is not None and claim.status == "approved":
                    active_bindings = await self.registration_repo.list_active_bindings_for_device(row.device_id)
                    binding = next(
                        (
                            item
                            for item in active_bindings
                            if item.person_id == claim.person_id
                            and item.relationship_type in {"primary_user", "shared_user", "responsible"}
                        ),
                        None,
                    )
                    if binding is not None:
                        created_session = await AccountSessionService(self.session).create_confirmed_binding_session(
                            device_id=row.device_id,
                            binding_id=binding.binding_id,
                        )
                        row.binding_id = binding.binding_id
                        row.resulting_account_session_id = created_session["session"]["session_id"]
            if created_session is None:
                return await self.serialize_pairing(row)
            row.status = "consumed"
            row.consumed_at = _now()
            row.completed_at = row.consumed_at
            await self.session.flush()
            await self.account_session_repo.append_event(
                device_id=row.device_id,
                session_id=row.resulting_account_session_id,
                event_type="browser_pairing_consumed",
                actor_id=row.device_id,
                actor_role="agent",
                payload={"pairing_id": row.pairing_id, "purpose": row.purpose, "claim_id": row.claim_id},
            )
            payload = await self.serialize_pairing(row)
            if created_session is not None:
                payload["session"] = created_session["session"]
                payload["session_token"] = created_session["session_token"]
            return payload
        if row.purpose != "login" or not row.binding_id:
            raise ValueError("browser pairing result is incomplete")
        created = await AccountSessionService(self.session).create_confirmed_binding_session(
            device_id=row.device_id,
            binding_id=row.binding_id,
        )
        row.status = "consumed"
        row.resulting_account_session_id = created["session"]["session_id"]
        row.consumed_at = _now()
        row.completed_at = row.consumed_at
        await self.session.flush()
        await self.account_session_repo.append_event(
            device_id=row.device_id,
            session_id=row.resulting_account_session_id,
            event_type="browser_pairing_consumed",
            actor_id=row.device_id,
            actor_role="agent",
            payload={"pairing_id": row.pairing_id, "purpose": row.purpose},
        )
        payload = await self.serialize_pairing(row)
        payload["session"] = created["session"]
        payload["session_token"] = created["session_token"]
        return payload
