"""Read-only aliases for the two actor IDs issued for an existing UI account.

OIDC preserves the stored login; password tokens use its normalized form.
Never normalize arbitrary principals, and never use these aliases for CRUD.
"""
from sqlalchemy import func, select

from app.db.models import UiUser
from app.repos.ui_users_repo import normalize_user_login


async def ui_actor_membership_ids(session, actor_id: str) -> tuple[str, ...]:
    normalized = normalize_user_login(actor_id)
    users = list((await session.execute(select(UiUser.user_login).where(
        func.lower(func.trim(UiUser.user_login)) == normalized).limit(2))).scalars().all())
    if len(users) > 1:
        return ()  # An ambiguous UI identity must never receive an alias grant.
    if users and actor_id in {users[0], normalized}:
        return tuple(dict.fromkeys((users[0], normalized)))
    return (actor_id,)  # Unknown / unsupported actor spellings remain exact-only.
