"""Query predicates for active Registry ownership, including leased inventory links."""

from datetime import timedelta
import os

from sqlalchemy import and_, func, or_, select

from app.db.models import DeviceUserBinding, RegistryInventoryLink, RegistryPerson, RegistryPersonIdentity, UiUser

INVENTORY_SOURCE = "inventory_assignment"
INVENTORY_ACTIVE = "inventory_active"
INVENTORY_ACTOR = "inventory-reconciler"
STORED_ACTIVE_BINDING_STATES = ("active", INVENTORY_ACTIVE)
INVENTORY_LEASE = timedelta(minutes=5)


def automatic_inventory_binding_enabled() -> bool:
    return bool(os.getenv("HELPDESK_INVENTORY_BASE_URL", "").strip()) and os.getenv(
        "HELPDESK_INVENTORY_AUTO_BIND_ENABLED", "",
    ).strip().lower() in {"1", "true", "yes", "on"}


def active_binding_condition(binding=DeviceUserBinding):
    manual = and_(binding.status == "active", binding.source != INVENTORY_SOURCE)
    if not automatic_inventory_binding_enabled():
        return manual

    link = RegistryInventoryLink
    person = RegistryPerson
    alias = RegistryPersonIdentity
    account = UiUser
    approved = (
        select(link.person_id)
        .select_from(link)
        .join(person, person.person_id == link.person_id)
        .join(account, account.user_login == link.user_login)
        .join(alias, alias.person_id == person.person_id)
        .where(
            link.person_id == binding.person_id,
            link.approval_id == binding.metadata_json["approval_id"].astext,
            link.inventory_person_id == binding.metadata_json["inventory_person_id"].astext,
            person.status.in_(("active", "self_reported")),
            person.metadata_json["merged_into"].astext.is_(None),
            account.is_active.is_(True),
            account.actor_role == "user",
            alias.provider == "ui_login",
            alias.verified.is_(True),
            alias.normalized_identifier == func.lower(account.user_login),
            func.lower(func.trim(alias.identifier)) == func.lower(account.user_login),
            alias.metadata_json["collision_person_id"].astext.is_(None),
            alias.metadata_json["merge_conflict"].astext.is_(None),
        )
        .correlate(binding)
        .exists()
    )
    return or_(manual, and_(binding.status == INVENTORY_ACTIVE, binding.source == INVENTORY_SOURCE,
                           binding.inventory_verified_until > func.now(), approved))
