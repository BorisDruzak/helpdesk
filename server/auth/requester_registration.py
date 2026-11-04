"""Server-owned requester signup, own profile and safe retry within one transaction."""
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
import uuid

from sqlalchemy import text

from app.db.models import UiUser, WebRequesterRegistration
from app.repos.ui_users_repo import UiUsersRepo
from auth.password_service import hash_password, validate_password_policy, verify_password
from requester.identity_service import RequesterIdentityResolver, RequesterProfileValidationError

_RUSSIAN = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", (
    "a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya",
)))
_NAME = re.compile(r"^[A-Za-zА-Яа-яЁё]+(?:[ -][A-Za-zА-Яа-яЁё]+)*$")


class RegistrationConflict(ValueError):
    pass


def clean_registration_name(value: str, *, optional: bool = False) -> str:
    name = " ".join(unicodedata.normalize("NFC", str(value or "")).split())
    if (not name and optional):
        return ""
    if not name or len(name) > 100 or not _NAME.fullmatch(name):
        raise ValueError("Укажите имя и фамилию буквами, без цифр и специальных символов.")
    return name


def registration_login_base(first_name: str, last_name: str) -> str:
    first = clean_registration_name(first_name).lower()
    last = clean_registration_name(last_name).lower()
    letters = first[0] + last.replace(" ", "")
    result = "".join(_RUSSIAN.get(char, char) for char in letters)[:96]
    if not re.fullmatch(r"[a-z][a-z-]+", result) or not result.strip("-"):
        raise ValueError("Не удалось сформировать логин из имени и фамилии.")
    return result


def _lock_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big", signed=True)


async def register_requester(session, payload: dict) -> dict:
    """Caller owns commit/rollback. A replay also requires the original password."""
    request_id = str(uuid.UUID(str(payload["request_id"])))
    first = clean_registration_name(payload.get("first_name"))
    last = clean_registration_name(payload.get("last_name"))
    patronymic = clean_registration_name(payload.get("patronymic", ""), optional=True)
    base = registration_login_base(first, last)
    password = payload["password"]
    if password != payload["password_repeat"]:
        raise ValueError("Пароли не совпадают.")
    validate_password_policy(password, login=base)
    profile = {key: value for key, value in payload.items() if key in {
        "department_id", "phone", "internal_extension", "position", "workplace_label", "preferred_contact_method", "custom_fields",
    }}
    profile["full_name"] = " ".join(part for part in (last, first, patronymic) if part)
    if len(profile["full_name"]) > 240:
        raise ValueError("ФИО должно содержать не более 240 символов.")
    fingerprint = hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _lock_key("requester-signup-request:" + request_id)})
    receipt = await session.get(WebRequesterRegistration, request_id)
    if receipt is not None:
        user = await session.get(UiUser, receipt.user_login)
        if (receipt.profile_fingerprint != fingerprint or user is None or not user.is_active
                or not user.password_login_enabled or user.actor_role != "user"
                or (user.locked_until and user.locked_until > datetime.now(timezone.utc))
                or not verify_password(password, user.password_hash)):
            raise RegistrationConflict("Не удалось продолжить регистрацию. Используйте вход в существующий аккаунт.")
        return {"user_login": receipt.user_login, "actor_role": "user", "profile_complete": True, "replayed": True}
    # A transaction lock serializes namesakes; the unique user constraint also
    # protects against legacy/admin writers that do not take this lock.
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _lock_key("requester-signup-login:" + base)})
    repo = UiUsersRepo(session)
    encoded = hash_password(password)
    for number in range(1, 1001):
        login = base if number == 1 else base + str(number)
        if await repo.get_by_login(login) is not None:
            continue
        # Never take over an identity left behind by another provisioning path.
        if await RequesterIdentityResolver(session).registration_repo.find_identity("ui_login", login) is not None:
            continue
        validate_password_policy(password, login=login)
        try:
            async with session.begin_nested():
                await repo.create_user(login, encoded, actor_role="user", actor_id=login, commit=False)
        except ValueError as error:
            if str(error) == "User already exists":
                continue
            raise
        result = await RequesterIdentityResolver(session).update_own_profile(actor_id=login, payload=profile)
        if not result["profile_completion"]["complete"]:
            raise RequesterProfileValidationError("Заполните обязательные поля профиля.")
        session.add(WebRequesterRegistration(request_id=request_id, user_login=login,
            person_id=result["profile"]["person_id"], profile_fingerprint=fingerprint))
        await session.flush()
        return {"user_login": login, "actor_role": "user", "profile_complete": True, "replayed": False}
    raise RegistrationConflict("Не удалось подобрать свободный логин. Обратитесь в поддержку.")
