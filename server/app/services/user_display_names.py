"""Display-only names from verified Helpdesk UI aliases; never identity matching."""
from uuid import UUID

from sqlalchemy import select

from app.db.models import RegistryPerson, RegistryPersonIdentity
from app.repos.registration_repo import normalize_identifier


def _name(value: object) -> str | None:
    name = str(value or "").strip()[:160]
    if not name:
        return None
    try:
        UUID(name)
    except ValueError:
        return name
    return None


async def ui_user_display_names(session, logins: list[str]) -> dict[str, str]:
    names = {login: login for login in logins}
    normalized = {normalize_identifier("ui_login", login): login for login in logins}
    if not normalized:
        return names
    rows = await session.execute(
        select(RegistryPersonIdentity.normalized_identifier, RegistryPerson.full_name, RegistryPerson.display_name)
        .join(RegistryPerson, RegistryPerson.person_id == RegistryPersonIdentity.person_id)
        .where(
            RegistryPersonIdentity.provider == "ui_login",
            RegistryPersonIdentity.verified.is_(True),
            RegistryPersonIdentity.normalized_identifier.in_(normalized),
        )
    )
    for identifier, full_name, display_name in rows.all():
        login = normalized[identifier]
        names[login] = _name(full_name) or _name(display_name) or login
    return names
