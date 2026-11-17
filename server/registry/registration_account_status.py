"""Advisory duplicate-account hints for registration suggestions."""

from sqlalchemy import and_, func, or_, select

from app.db import get_session
from app.db.models import (
    RegistryDepartment, RegistryInventoryLink, RegistryPerson, RegistryPersonIdentity, UiUser,
)
from registry.inventory_directory import RegistrationEmployee


def _label_key(value: str | None) -> str:
    return " ".join((value or "").lower().split())


async def mark_registered_employees(people: list[RegistrationEmployee]) -> None:
    if not people:
        return
    name = func.regexp_replace(func.lower(func.trim(
        func.coalesce(RegistryPerson.full_name, RegistryPerson.display_name),
    )), r"\s+", " ", "g")
    link = RegistryInventoryLink
    identities = RegistryPersonIdentity
    async with get_session() as session:
        rows = await session.execute(
            select(name, RegistryDepartment.name, link.inventory_person_id)
            .select_from(RegistryPerson)
            .join(identities, and_(
                identities.person_id == RegistryPerson.person_id,
                identities.provider == "ui_login",
                identities.verified.is_(True),
            ))
            .join(UiUser, identities.normalized_identifier == func.lower(func.trim(UiUser.user_login)))
            .outerjoin(RegistryDepartment, RegistryDepartment.department_id == RegistryPerson.department_id)
            .outerjoin(link, and_(link.person_id == RegistryPerson.person_id, link.user_login == UiUser.user_login))
            .where(or_(
                name.in_([_label_key(person.full_name) for person in people]),
                link.inventory_person_id.in_([
                    str(person.inventory_person_id) for person in people if person.inventory_person_id
                ]),
            ))
        )
        accounts = list(rows)
    for person in people:
        person.registered = any(
            (person.inventory_person_id is not None and str(person.inventory_person_id) == inventory_id)
            or (name == _label_key(person.full_name)
                and (not person.department or _label_key(department) == _label_key(person.department)))
            for name, department, inventory_id in accounts
        )
