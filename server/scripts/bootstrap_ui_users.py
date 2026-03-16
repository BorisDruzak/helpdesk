"""
Stage 10: Bootstrap ui_users из config.USERS.

Запуск один раз после миграции 028 и включения AUTH_UI_DB_USERS_ENABLED
(с AUTH_UI_CONFIG_FALLBACK_ENABLED=true). Переносит логин/пароль из USERS
в ui_users с хешем пароля и ролью из UI_USER_ROLES или admin.

Использование (из каталога server):
  python -m scripts.bootstrap_ui_users

Требует: DATABASE_URL, миграции до 028 включительно.
"""
import asyncio
import os
import sys

# Добавить корень server в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import USERS
from app.db import get_session
from app.repos.ui_users_repo import UiUsersRepo
from auth.password_service import hash_password


def _get_role(login: str) -> str:
    try:
        from config import UI_USER_ROLES
        role = UI_USER_ROLES.get(login, "admin")
    except Exception:
        role = "admin"
    valid = ("admin", "support", "auditor", "user")
    return role if role in valid else "admin"


async def main() -> None:
    if not USERS:
        print("USERS is empty, nothing to bootstrap.")
        return
    created = 0
    skipped = 0
    async with get_session() as session:
        repo = UiUsersRepo(session)
        for login, password in USERS.items():
            if not login or not isinstance(password, str):
                continue
            existing = await repo.get_by_login(login)
            if existing:
                print(f"  skip (exists): {login}")
                skipped += 1
                continue
            role = _get_role(login)
            password_hash = hash_password(password)
            try:
                await repo.create_user(login, password_hash, actor_role=role)
                await session.commit()
                print(f"  created: {login} role={role}")
                created += 1
            except ValueError as e:
                await session.rollback()
                print(f"  error {login}: {e}")
    print(f"Done. Created={created}, Skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
