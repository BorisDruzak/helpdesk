from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DeviceAccountSession,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from app.repos.access_control_repo import AccessControlRepo
from app.repos.registration_repo import normalize_identifier
from registry.account_session_service import AccountSessionService
from registry.audience_contracts import EffectiveAudience, EffectiveIdentity, WarningItem


TOKEN_FIELD_FRAGMENTS = ("token", "secret", "password", "hash")


def _normalize_role(actor_role: str | None) -> str:
    role = str(actor_role or "").strip().lower()
    return role if role in {"admin", "support", "auditor", "user", "agent"} else "user"


def _warning(code: str, message: str, *, source: str = "effective_identity") -> WarningItem:
    return {"code": code, "message": message, "source": source}


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(fragment in key_text.lower() for fragment in TOKEN_FIELD_FRAGMENTS):
                continue
            redacted[key_text] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


class EffectiveIdentityService:
    """Resolve the registry/person side of UI actors and account sessions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.access_repo = AccessControlRepo(session)

    async def resolve_actor_identity(self, actor_id: str, actor_role: str) -> EffectiveIdentity:
        clean_actor_id = str(actor_id or "").strip()
        role = _normalize_role(actor_role)
        if role == "agent":
            return EffectiveIdentity(
                actor_id=clean_actor_id,
                actor_role=role,
                identity_source="machine_token",
                warnings=[
                    _warning(
                        "agent_machine_identity_not_requester",
                        "Agent machine tokens identify the device, not the requester person.",
                        source="registry",
                    )
                ],
                sources={"actor": "auth_context", "person": None, "access_groups": []},
            )

        ui_user = await self._load_ui_user(clean_actor_id)
        if ui_user is not None and not actor_role:
            role = _normalize_role(ui_user.actor_role)

        person, identity = await self._resolve_person_from_actor(clean_actor_id)
        access_groups = await self._actor_group_codes(clean_actor_id)
        warnings: list[WarningItem] = []
        identity_source = "registry_identity" if person is not None else "ui_actor"
        if person is None:
            if role in {"admin", "support", "auditor"}:
                warnings.append(
                    _warning(
                        "registry_person_optional_for_privileged_actor",
                        "Privileged UI actor is not linked to a registry person.",
                        source="registry",
                    )
                )
            else:
                warnings.append(
                    _warning(
                        "registry_person_not_linked",
                        "UI actor is not linked to a verified registry person identity.",
                        source="registry",
                    )
                )

        return await self._identity_from_person(
            actor_id=clean_actor_id,
            actor_role=role,
            identity_source=identity_source,
            person=person,
            access_groups=access_groups,
            warnings=warnings,
            sources={
                "actor": "ui_users" if ui_user is not None else "auth_context",
                "person_identity": self._identity_source(identity),
                "access_groups": access_groups,
            },
        )

    async def resolve_account_session_identity(
        self,
        device_id: str,
        session_id: str,
        session_token: str | None,
    ) -> EffectiveIdentity:
        validation = await AccountSessionService(self.session).validate_session(
            device_id=str(device_id or "").strip(),
            session_id=str(session_id or "").strip(),
            session_token=session_token,
            touch=False,
        )
        session_payload = _redact_sensitive(dict(validation.get("session") or {}))
        account_session = {
            "valid": bool(validation.get("valid")),
            **session_payload,
        }
        if validation.get("error_code"):
            account_session["error_code"] = str(validation.get("error_code"))

        warnings: list[WarningItem] = []
        if not validation.get("valid"):
            warnings.append(
                _warning(
                    str(validation.get("error_code") or "ACCOUNT_SESSION_INVALID").lower(),
                    "Account session did not validate.",
                    source="account_session",
                )
            )
            return EffectiveIdentity(
                actor_id=str(device_id or "").strip(),
                actor_role="user",
                identity_source="account_session",
                account_session=account_session,
                warnings=warnings,
                sources={"account_session": "validate_session"},
            )

        account_mode = str(account_session.get("account_mode") or "")
        person_id = str(account_session.get("person_id") or "").strip() or None
        if account_mode == "verified_other_account" and not person_id:
            warnings.append(
                _warning(
                    "declared_account_unlinked_registry_person",
                    "Verified other-account session has no matched registry person; base owner is not requester identity.",
                    source="account_session",
                )
            )
        if account_mode == "registration_pending":
            warnings.append(
                _warning(
                    "registration_pending_not_authoritative",
                    "Registration-pending account sessions are not authoritative requester identities.",
                    source="account_session",
                )
            )

        person = await self.session.get(RegistryPerson, person_id) if person_id else None
        return await self._identity_from_person(
            actor_id=str(account_session.get("login") or person_id or device_id or "").strip() or None,
            actor_role="user",
            identity_source="account_session",
            person=person,
            access_groups=[],
            account_session=account_session,
            warnings=warnings,
            sources={"account_session": "validate_session", "person": "device_account_sessions.person_id"},
        )

    async def resolve_person_audience(
        self,
        person_id: str | None,
        actor_id: str | None,
        actor_role: str,
    ) -> EffectiveAudience:
        role = _normalize_role(actor_role)
        person = await self.session.get(RegistryPerson, str(person_id)) if person_id else None
        warnings: list[WarningItem] = []
        if person_id and person is None:
            warnings.append(_warning("registry_person_not_found", "Registry person was not found.", source="registry"))
        if person is None and actor_id:
            identity = await self.resolve_actor_identity(str(actor_id), role)
            payload = identity.to_dict()
            return EffectiveAudience(
                person_id=(payload.get("person") or {}).get("person_id"),
                actor_id=payload.get("actor_id"),
                actor_role=str(payload.get("actor_role") or role),
                department_path=list(payload.get("department_path") or []),
                location=payload.get("location"),
                access_groups=list(payload.get("access_groups") or []),
                audience_groups=list(payload.get("audience_groups") or []),
                warnings=list(payload.get("warnings") or []),
                sources={"derived_from": "resolve_actor_identity"},
            )

        access_groups = await self._actor_group_codes(str(actor_id or "").strip()) if actor_id else []
        return EffectiveAudience(
            person_id=getattr(person, "person_id", None),
            actor_id=str(actor_id or "").strip() or None,
            actor_role=role,
            department_path=await self._department_path(getattr(person, "department_id", None)),
            location=await self._location_payload(getattr(person, "location_id", None)),
            access_groups=access_groups,
            audience_groups=[],
            warnings=warnings,
            sources={"person": "registry_people", "access_groups": access_groups},
        )

    async def explain_identity(self, actor_id: str, actor_role: str) -> dict[str, Any]:
        identity = await self.resolve_actor_identity(actor_id, actor_role)
        payload = identity.to_dict()
        return {
            "identity": payload,
            "sources_checked": [
                "ui_users",
                "registry_person_identities",
                "registry_people",
                "registry_departments",
                "registry_locations",
                "access_group_members",
            ],
            "warnings": payload.get("warnings") or [],
        }

    async def _identity_from_person(
        self,
        *,
        actor_id: str | None,
        actor_role: str,
        identity_source: str,
        person: RegistryPerson | None,
        access_groups: list[str],
        warnings: list[WarningItem],
        sources: dict[str, Any],
        account_session: dict[str, Any] | None = None,
    ) -> EffectiveIdentity:
        return EffectiveIdentity(
            actor_id=actor_id,
            actor_role=_normalize_role(actor_role),
            identity_source=identity_source,
            person=self._person_payload(person),
            department_path=await self._department_path(getattr(person, "department_id", None)),
            location=await self._location_payload(getattr(person, "location_id", None)),
            access_groups=access_groups,
            audience_groups=[],
            account_session=account_session,
            warnings=warnings,
            sources=sources,
        )

    async def _load_ui_user(self, actor_id: str) -> UiUser | None:
        if not actor_id:
            return None
        result = await self.session.execute(
            select(UiUser).where(func.lower(UiUser.user_login) == actor_id.lower()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _resolve_person_from_actor(
        self,
        actor_id: str,
    ) -> tuple[RegistryPerson | None, RegistryPersonIdentity | None]:
        if not actor_id:
            return None, None
        for provider in ("ui_login", "email", "windows_login", "ad"):
            normalized = normalize_identifier(provider, actor_id)
            if not normalized:
                continue
            result = await self.session.execute(
                select(RegistryPerson, RegistryPersonIdentity)
                .join(RegistryPersonIdentity, RegistryPersonIdentity.person_id == RegistryPerson.person_id)
                .where(
                    RegistryPersonIdentity.provider == provider,
                    RegistryPersonIdentity.normalized_identifier == normalized,
                    RegistryPersonIdentity.verified.is_(True),
                    RegistryPerson.status == "active",
                )
                .limit(1)
            )
            row = result.first()
            if row:
                return row[0], row[1]
        return None, None

    async def _actor_group_codes(self, actor_id: str) -> list[str]:
        if not actor_id:
            return []
        groups = await self.access_repo.get_actor_group_codes(actor_id)
        lower_actor_id = actor_id.lower()
        if not groups and lower_actor_id != actor_id:
            groups = await self.access_repo.get_actor_group_codes(lower_actor_id)
        return groups

    async def _department_path(self, department_id: str | None) -> list[dict[str, Any]]:
        path: list[dict[str, Any]] = []
        current_id = str(department_id or "").strip() or None
        seen: set[str] = set()
        while current_id and current_id not in seen and len(path) < 20:
            seen.add(current_id)
            department = await self.session.get(RegistryDepartment, current_id)
            if department is None:
                break
            path.append(
                {
                    "department_id": department.department_id,
                    "code": department.code or department.department_id,
                    "name": department.name,
                    "status": department.status,
                    "parent_department_id": department.parent_department_id,
                }
            )
            current_id = department.parent_department_id
        path.reverse()
        return path

    async def _location_payload(self, location_id: str | None) -> dict[str, Any] | None:
        if not location_id:
            return None
        location = await self.session.get(RegistryLocation, str(location_id))
        if location is None:
            return None
        return {
            "location_id": location.location_id,
            "display_name": location.display_name,
            "building": location.building,
            "floor": location.floor,
            "room": location.room,
            "status": location.status,
        }

    @staticmethod
    def _person_payload(person: RegistryPerson | None) -> dict[str, Any] | None:
        if person is None:
            return None
        return {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "phone": person.phone,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
        }

    @staticmethod
    def _identity_source(identity: RegistryPersonIdentity | None) -> dict[str, Any] | None:
        if identity is None:
            return None
        return {
            "identity_id": identity.identity_id,
            "provider": identity.provider,
            "verified": bool(identity.verified),
            "source": identity.source,
        }
