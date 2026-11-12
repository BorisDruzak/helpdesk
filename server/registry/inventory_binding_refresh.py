"""Refresh inventory links independently of requester activity."""

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import DeviceUserBinding, RegistryInventoryLink, RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.inventory_binding_authority import INVENTORY_ACTIVE, automatic_inventory_binding_enabled
from app.repos.ui_users_repo import normalize_user_login
from domain_ports.container import DomainPortContainer
from registry import inventory_directory
from registry.inventory_device_binding import (
    SOURCE, InventoryDeviceBindingService, fresh_inventory_observation,
)


def active_inventory_account(person: RegistryPerson | None, account: UiUser | None) -> bool:
    return bool(person is not None and person.status in {"active", "self_reported"}
                and not (person.metadata_json or {}).get("merged_into")
                and account is not None and account.is_active and account.actor_role == "user")


def verified_inventory_alias(alias: RegistryPersonIdentity | None, canonical_login: str) -> bool:
    return bool(alias is not None and normalize_user_login(alias.identifier) == canonical_login
                and not any((alias.metadata_json or {}).get(key) for key in ("collision_person_id", "merge_conflict")))


async def inventory_link_owner(session, person_id: str, login: str) -> bool:
    person = await session.get(RegistryPerson, person_id)
    account = await session.get(UiUser, login)
    if account is None or not active_inventory_account(person, account):
        return False
    canonical = normalize_user_login(account.user_login)
    alias = await session.scalar(select(RegistryPersonIdentity).where(
        RegistryPersonIdentity.person_id == person_id,
        RegistryPersonIdentity.provider == "ui_login",
        RegistryPersonIdentity.normalized_identifier == canonical,
        RegistryPersonIdentity.verified.is_(True),
    ))
    return verified_inventory_alias(alias, canonical)


async def sync_managed_inventory(session, link, profile, *, missing=False, endpoint=None) -> dict[str, dict]:
    enabled = automatic_inventory_binding_enabled()
    if not enabled:
        await InventoryDeviceBindingService(session, None).revoke_all(link.person_id, "inventory_policy_disabled")
        return {}
    if missing or not await inventory_link_owner(session, link.person_id, link.user_login):
        await InventoryDeviceBindingService(session, None).revoke_all(link.person_id, "inventory_identity_unavailable")
        return {}
    if profile is None or not fresh_inventory_observation(profile.observed_at):
        if not fresh_inventory_observation(link.observed_at):
            await InventoryDeviceBindingService(session, None).revoke_all(link.person_id, "inventory_confirmation_expired")
        return {}
    if fresh_inventory_observation(link.observed_at) and profile.observed_at < link.observed_at:
        return {}
    endpoint = endpoint or DomainPortContainer.from_config(registry_session=session).endpoint
    return await InventoryDeviceBindingService(session, endpoint).reconcile(link, profile)


async def _refresh_one(person_id: str) -> None:
    enabled = automatic_inventory_binding_enabled()
    async with get_session() as session:
        link = await session.get(RegistryInventoryLink, person_id)
        approval = link.approval_id if link else None
        employee = UUID(link.inventory_person_id) if link else None

    profile = None
    missing = False
    if enabled and employee is not None:
        try:
            profile = await inventory_directory.fetch_person(employee)
        except inventory_directory.InventoryPersonMissing:
            missing = True
        except inventory_directory.InventoryUnavailable:
            pass

    async with get_session() as session:
        # A replacement link must never inherit results fetched for an old approval.
        current = await session.get(RegistryInventoryLink, person_id, with_for_update=True, populate_existing=True)
        if current is None:
            await InventoryDeviceBindingService(session, None).revoke_all(person_id, "inventory_link_removed")
        elif current.approval_id == approval:
            await sync_managed_inventory(session, current, profile, missing=missing)
            if missing:
                current.snapshot = None
                current.observed_at = None
            elif (profile is not None and fresh_inventory_observation(profile.observed_at)
                  and (not fresh_inventory_observation(current.observed_at) or profile.observed_at > current.observed_at)):
                current.snapshot = profile.model_dump(mode="json")
                current.observed_at = profile.observed_at


async def refresh_inventory_for_login(login: str) -> None:
    if not automatic_inventory_binding_enabled():
        return
    try:
        async with asyncio.timeout(5):
            async with get_session() as session:
                person_id = await session.scalar(select(RegistryInventoryLink.person_id).where(
                    RegistryInventoryLink.user_login == login,
                ))
            if person_id:
                await _refresh_one(person_id)
    except TimeoutError:
        pass
    except Exception:
        logger.warning("[inventory_bindings] requester refresh unavailable")


async def refresh_inventory_links() -> None:
    async with get_session() as session:
        active = select(DeviceUserBinding.person_id).where(
            DeviceUserBinding.source == SOURCE, DeviceUserBinding.status == INVENTORY_ACTIVE,
        ).distinct()
        person_ids = set(await session.scalars(active))
        if automatic_inventory_binding_enabled():
            person_ids.update(await session.scalars(select(RegistryInventoryLink.person_id)))

    gate = asyncio.Semaphore(4)

    async def refresh(person_id):
        async with gate:
            try:
                await _refresh_one(person_id)
            except Exception:
                logger.warning("[inventory_bindings] employee reconciliation failed")

    await asyncio.gather(*(refresh(person_id) for person_id in person_ids))


async def run_inventory_link_refresh() -> None:
    while True:
        try:
            await refresh_inventory_links()
        except Exception:
            logger.warning("[inventory_bindings] reconciliation pass unavailable")
        await asyncio.sleep(120)
