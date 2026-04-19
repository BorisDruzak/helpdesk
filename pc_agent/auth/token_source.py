import asyncio
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from loguru import logger


def _auth_lookup_ids(identity_manager: Any) -> list[str]:
    if identity_manager is None:
        return []
    if hasattr(identity_manager, "auth_lookup_ids"):
        try:
            ids = identity_manager.auth_lookup_ids()
            if ids:
                return [str(item) for item in ids if item]
        except Exception as exc:
            logger.debug("Не удалось получить auth lookup ids из identity_manager: {}", exc)
    candidates = [
        getattr(identity_manager, "device_id", None),
        getattr(identity_manager, "install_id", None),
        getattr(identity_manager, "legacy_uuid", None),
        getattr(identity_manager, "uuid", None),
    ]
    result: list[str] = []
    for item in candidates:
        if not item:
            continue
        normalized = str(item).strip().lower()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


async def load_auth_token_from_db(
    db_manager: Any,
    identity_manager: Any,
    *,
    migrate_to_primary: bool = True,
) -> Optional[str]:
    if not db_manager or not identity_manager:
        return None

    lookup_ids = _auth_lookup_ids(identity_manager)
    if not lookup_ids:
        return None

    primary_device_id = lookup_ids[0]
    for candidate_device_id in lookup_ids:
        token = await db_manager.get_auth_token(candidate_device_id)
        if not token:
            continue
        if migrate_to_primary and candidate_device_id != primary_device_id:
            try:
                await db_manager.save_auth_token(token, primary_device_id)
                logger.info(
                    "✅ Локальный токен мигрирован с legacy device_id={} на machine_id={}",
                    candidate_device_id[:8],
                    primary_device_id[:8],
                )
            except Exception as exc:
                logger.warning(
                    "⚠️ Не удалось сохранить локальную миграцию токена {} -> {}: {}",
                    candidate_device_id[:8],
                    primary_device_id[:8],
                    exc,
                )
        identity_manager.token = token
        if candidate_device_id == primary_device_id:
            logger.info("✅ Токен найден в БД агента")
        else:
            logger.info(
                "✅ Токен найден в БД агента по legacy device_id={} (primary={})",
                candidate_device_id[:8],
                primary_device_id[:8],
            )
        return token

    return None


async def load_auth_token(
    db_manager: Any,
    identity_manager: Any,
    gui_wait_callback: Optional[Callable[[], Awaitable[Optional[str]]]] = None,
) -> Optional[str]:
    """
    Загружает токен аутентификации в порядке приоритета:
    1) ENV AUTH_TOKEN
    2) БД агента (auth_tokens)
    3) Опциональный GUI callback ожидания токена
    """
    env_token = os.getenv("AUTH_TOKEN")
    lookup_ids = _auth_lookup_ids(identity_manager)
    device_id = lookup_ids[0] if lookup_ids else None
    if env_token:
        logger.info("✅ Токен найден в переменной окружения AUTH_TOKEN")
        identity_manager.token = env_token
        if db_manager:
            try:
                await db_manager.save_auth_token(env_token, device_id)
                logger.info("✅ Токен из ENV сохранен в БД агента")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось сохранить токен в БД: {e}")
        return env_token

    try:
        token = await load_auth_token_from_db(db_manager, identity_manager)
        if token:
            return token
    except Exception as e:
        logger.debug(f"Не удалось проверить токен в БД: {e}")

    if gui_wait_callback is not None:
        token = await gui_wait_callback()
        if token:
            identity_manager.token = token
            return token

    return None


def import_missing_auth_token_from_data_roots(
    source_data_root: str | Path,
    target_data_root: str | Path,
    *,
    log_message: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Import the active auth token from another data root if the current one is empty.

    This is used by local Windows testing flows where a portable launcher or an
    isolated instance should reuse the token of the primary agent install on the
    same machine, but only when both data roots resolve to the same machine_id.
    """
    source_root = Path(source_data_root).expanduser().resolve()
    target_root = Path(target_data_root).expanduser().resolve()
    if source_root == target_root:
        return False

    source_db_path = source_root / "storage.db"
    if not source_db_path.exists():
        return False

    def _emit(message: str) -> None:
        if log_message is not None:
            try:
                log_message(message)
            except Exception:
                pass

    async def _copy() -> tuple[bool, Optional[str]]:
        from pc_agent.core.database import DatabaseManager
        from pc_agent.core.identity import IdentityManager

        target_identity = IdentityManager(target_root / "identity.json")
        target_payload = target_identity.load_or_create()
        source_identity = IdentityManager(source_root / "identity.json")
        source_payload = source_identity.load_or_create()

        target_machine_id = str(target_payload.get("machine_id") or "").strip().lower()
        source_machine_id = str(source_payload.get("machine_id") or "").strip().lower()
        if not target_machine_id or target_machine_id != source_machine_id:
            return (
                False,
                f"skip auth token import: machine_id mismatch source={source_machine_id[:8]} target={target_machine_id[:8]}",
            )

        DatabaseManager._instance = None
        target_db = DatabaseManager(str(target_root / "storage.db"))
        await target_db.init_db()
        existing_token = await load_auth_token_from_db(
            target_db,
            target_identity,
            migrate_to_primary=False,
        )
        if existing_token:
            return False, None

        DatabaseManager._instance = None
        source_db = DatabaseManager(str(source_db_path))
        await source_db.init_db()
        source_token = await load_auth_token_from_db(source_db, source_identity)
        if not source_token:
            return False, None

        DatabaseManager._instance = None
        target_db = DatabaseManager(str(target_root / "storage.db"))
        await target_db.init_db()
        saved = await target_db.save_auth_token(source_token, target_machine_id)
        if not saved:
            return False, None

        return (
            True,
            f"imported auth token from {source_root} for machine_id={target_machine_id[:8]}",
        )

    try:
        imported, note = asyncio.run(_copy())
    except Exception as exc:
        logger.warning(
            "Failed to import local auth token from {} to {}: {}",
            source_root,
            target_root,
            exc,
        )
        _emit(f"warning: failed to import local auth token: {exc}")
        return False
    finally:
        try:
            from pc_agent.core.database import DatabaseManager

            DatabaseManager._instance = None
        except Exception:
            pass

    if note:
        logger.info(note)
        _emit(note)
    return imported
