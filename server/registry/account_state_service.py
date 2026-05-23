from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo
from registry.registration_service import RegistrationService


def _identity_value(identities: list[Any], *providers: str) -> str | None:
    wanted = {provider.lower() for provider in providers}
    for identity in identities:
        if str(getattr(identity, "provider", "")).lower() in wanted:
            value = str(getattr(identity, "identifier", "") or "").strip()
            if value:
                return value
    return None


async def build_agent_account_state(session: AsyncSession, device_id: str) -> dict[str, Any]:
    registration_repo = RegistrationRepo(session)
    registry_repo = RegistryRepo(session)
    registration = await RegistrationService(session).get_device_registration_status(device_id)
    active_bindings = await registration_repo.list_active_bindings_for_device(device_id)
    accounts: list[dict[str, Any]] = []

    for binding in active_bindings:
        person = await registry_repo.get_person(binding.person_id)
        if person is None:
            continue
        identities = await registration_repo.list_identities_for_person(person.person_id)
        login = _identity_value(identities, "windows_login", "ui_login", "ad", "agent_profile")
        email = person.email or _identity_value(identities, "email")
        accounts.append(
            {
                "account_mode": "confirmed_binding",
                "person_id": person.person_id,
                "binding_id": binding.binding_id,
                "display_name": person.display_name,
                "full_name": person.full_name,
                "email": email,
                "login": login,
                "relationship_type": binding.relationship_type,
                "registration_status": "admin_confirmed",
                "can_login": True,
                "is_primary": binding.relationship_type == "primary_user",
            }
        )

    pending_claim = registration.get("pending_claim") if isinstance(registration.get("pending_claim"), dict) else None
    if pending_claim and not accounts:
        person = await registry_repo.get_person(pending_claim.get("person_id"))
        snapshot = pending_claim.get("profile_snapshot") if isinstance(pending_claim.get("profile_snapshot"), dict) else {}
        accounts.append(
            {
                "account_mode": "registration_pending",
                "person_id": pending_claim.get("person_id"),
                "claim_id": pending_claim.get("claim_id"),
                "display_name": (person.display_name if person else None)
                or snapshot.get("display_name")
                or snapshot.get("full_name")
                or snapshot.get("login"),
                "full_name": (person.full_name if person else None) or snapshot.get("full_name"),
                "email": (person.email if person else None) or snapshot.get("email"),
                "login": snapshot.get("login"),
                "relationship_type": pending_claim.get("relationship_type") or snapshot.get("relationship_type"),
                "registration_status": pending_claim.get("status") or registration.get("status"),
                "can_login": True,
                "is_primary": False,
            }
        )

    has_active_binding = bool(active_bindings)
    return {
        "device_id": device_id,
        "registration": registration,
        "accounts": accounts,
        "can_register": not has_active_binding,
        "can_login_other_account": has_active_binding,
        "registration_form_available": True,
        "message": (
            "Устройство зарегистрировано. Можно войти как подтвержденный пользователь."
            if has_active_binding
            else "Подтвержденной регистрации устройства пока нет."
        ),
    }
