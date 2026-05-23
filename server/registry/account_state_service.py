from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo
from registry.account_session_service import AccountSessionService
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
    account_service = AccountSessionService(session)
    registration = await RegistrationService(session).get_device_registration_status(device_id)
    active_bindings = await registration_repo.list_active_bindings_for_device(device_id)
    server_sessions = await account_service.list_device_sessions(device_id)
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
                "phone": person.phone,
                "login": login,
                "relationship_type": binding.relationship_type,
                "registration_status": "admin_confirmed",
                "can_login": True,
                "is_primary": binding.relationship_type == "primary_user",
            }
        )

    pending_claim = registration.get("pending_claim") if isinstance(registration.get("pending_claim"), dict) else None
    has_pending_server_session = any(
        item.get("account_mode") == "registration_pending"
        and item.get("verification_status") == "pending_verification"
        for item in server_sessions
    )
    if pending_claim and not accounts and not has_pending_server_session:
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

    for account_session in server_sessions:
        if (
            account_session.get("account_mode") == "registration_pending"
            and account_session.get("verification_status") == "pending_verification"
            and not accounts
        ):
            declared = account_session.get("declared_account") if isinstance(account_session.get("declared_account"), dict) else {}
            accounts.append(
                {
                    "account_mode": "registration_pending",
                    "session_id": account_session.get("session_id"),
                    "session_token": None,
                    "person_id": account_session.get("person_id"),
                    "claim_id": account_session.get("claim_id"),
                    "display_name": declared.get("display_name") or declared.get("full_name") or declared.get("login"),
                    "full_name": declared.get("full_name"),
                    "email": declared.get("email"),
                    "phone": declared.get("phone"),
                    "login": declared.get("login"),
                    "registration_status": (pending_claim or {}).get("status") or registration.get("status"),
                    "verification_status": "pending_verification",
                    "verification_method": account_session.get("verification_method"),
                    "can_login": True,
                    "is_primary": False,
                }
            )
        if (
            account_session.get("account_mode") == "verified_other_account"
            and account_session.get("verification_status") == "verified"
        ):
            if not account_session.get("base_binding_id") or not await registration_repo.get_active_binding_for_device(
                device_id,
                str(account_session.get("base_binding_id")),
            ):
                continue
            declared = account_session.get("declared_account") if isinstance(account_session.get("declared_account"), dict) else {}
            accounts.append(
                {
                    "account_mode": "verified_other_account",
                    "session_id": account_session.get("session_id"),
                    "session_token": None,
                    "source_request_id": account_session.get("source_request_id"),
                    "person_id": account_session.get("person_id"),
                    "display_name": declared.get("display_name") or declared.get("full_name") or declared.get("login"),
                    "full_name": declared.get("full_name"),
                    "email": declared.get("email"),
                    "phone": declared.get("phone"),
                    "login": declared.get("login"),
                    "reason": account_session.get("reason") or declared.get("reason"),
                    "base_binding_id": account_session.get("base_binding_id"),
                    "base_person_id": account_session.get("base_person_id"),
                    "registration_status": "other_account",
                    "verification_status": "verified",
                    "verification_method": account_session.get("verification_method"),
                    "can_login": True,
                    "is_primary": False,
                }
            )
    has_active_binding = bool(active_bindings)
    pending_login_requests = await account_service.list_pending_login_requests_for_device(device_id)
    return {
        "device_id": device_id,
        "registration": registration,
        "accounts": accounts,
        "server_sessions": server_sessions,
        "pending_login_requests": pending_login_requests,
        "can_register": not has_active_binding,
        "can_login_confirmed_binding": has_active_binding,
        "can_login_other_account": has_active_binding,
        "can_request_other_account_login": has_active_binding,
        "can_use_break_glass_other_account": False,
        "registration_form_available": True,
        "message": (
            "Устройство зарегистрировано. Можно войти как подтвержденный пользователь."
            if has_active_binding
            else "Подтвержденной регистрации устройства пока нет."
        ),
    }
