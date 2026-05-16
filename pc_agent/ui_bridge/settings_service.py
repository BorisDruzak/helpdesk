"""
Сервис настроек агента для UI Bridge.
"""

from __future__ import annotations

import asyncio
import copy
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
import yaml
from loguru import logger

from pc_agent.config.config_loader import ConfigLoader, Settings, get_config, get_config_base
from pc_agent.core.database import db_manager
from pc_agent.core.identity import IdentityManager
from pc_agent.core.runtime_paths import resolve_data_root


class SettingsValidationError(ValueError):
    """Ошибка валидации входных настроек."""


class AgentSettingsService:
    """Чтение, валидация и сохранение настроек агента."""

    def __init__(self, data_root: Optional[Path] = None):
        base = data_root or get_config_base() or resolve_data_root()
        self._data_root = Path(base).resolve()
        self._data_root.mkdir(parents=True, exist_ok=True)

    async def get_settings(self) -> Dict[str, Any]:
        cfg = get_config()
        data = cfg.model_dump()
        device_id = self._get_device_id()
        token = await self._get_active_token(device_id)
        data["auth"] = {
            "device_id": device_id,
            "has_token": bool(token),
            "token_masked": self._mask_token(token),
        }
        data["meta"] = {
            "config_path": str(self._get_config_path()),
            "data_root": str(self._data_root),
        }
        return data

    async def update_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise SettingsValidationError("Тело запроса должно быть JSON-объектом")

        raw_settings = payload.get("settings")
        if raw_settings is None:
            raw_settings = {k: v for k, v in payload.items() if k not in {"auth"}}
        if not isinstance(raw_settings, dict):
            raise SettingsValidationError("Поле settings должно быть объектом")

        current = get_config().model_dump()
        candidate = copy.deepcopy(current)
        changed_keys: list[str] = []
        self._merge_dict(candidate, raw_settings, "", changed_keys)
        self._validate_paths(candidate)
        validated = Settings(**candidate)

        token_changed = await self._apply_token_changes(payload.get("auth"))

        config_changed = bool(changed_keys)
        if config_changed:
            self._write_config(validated)
            loader = ConfigLoader()
            loader._config = validated
            if getattr(loader, "config_path", None) is None:
                loader.config_path = self._get_config_path()
            logger.info(
                "[settings] Сохранены настройки: keys={}",
                ", ".join(sorted(changed_keys)),
            )

        return {
            "status": "ok",
            "config_changed": config_changed,
            "token_changed": token_changed,
            "changed_keys": sorted(changed_keys),
            "requires_restart": any(str(key) != "ui.theme_mode" for key in changed_keys),
        }

    async def test_connection(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        settings = payload.get("settings") if isinstance(payload, dict) else None
        if settings is not None and not isinstance(settings, dict):
            raise SettingsValidationError("settings для test_connection должен быть объектом")

        current = get_config()
        ws_url = current.server.ws_url
        api_url = current.server.api_url

        if settings:
            server = settings.get("server")
            if isinstance(server, dict):
                ws_url = str(server.get("ws_url") or ws_url)
                api_url = str(server.get("api_url") or api_url)

        ws_result = await self._check_ws_endpoint(ws_url)
        api_result = await self._check_api_endpoint(api_url)
        return {
            "status": "ok",
            "ws": ws_result,
            "api": api_result,
            "ok": bool(ws_result.get("ok") and api_result.get("ok")),
        }

    def _get_config_path(self) -> Path:
        loader = ConfigLoader()
        if getattr(loader, "config_path", None):
            return Path(loader.config_path).resolve()
        return (self._data_root / "settings.yaml").resolve()

    def _write_config(self, settings: Settings) -> None:
        config_path = self._get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = settings.model_dump()
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(config_path.parent),
            delete=False,
            suffix=".tmp",
        ) as tmp:
            yaml.safe_dump(content, tmp, allow_unicode=True, sort_keys=False)
            tmp_path = Path(tmp.name)
        tmp_path.replace(config_path)

    def _merge_dict(
        self,
        dest: Dict[str, Any],
        src: Dict[str, Any],
        prefix: str,
        changed_keys: list[str],
    ) -> None:
        for key, value in src.items():
            if key not in dest:
                raise SettingsValidationError(f"Неизвестный ключ настроек: {prefix}{key}")
            current_value = dest[key]
            full_key = f"{prefix}{key}"
            if isinstance(current_value, dict) and isinstance(value, dict):
                self._merge_dict(current_value, value, f"{full_key}.", changed_keys)
                continue
            if current_value != value:
                dest[key] = value
                changed_keys.append(full_key)

    def _validate_paths(self, settings: Dict[str, Any]) -> None:
        paths = settings.get("paths")
        if not isinstance(paths, dict):
            return
        data_dir = paths.get("data_dir")
        if isinstance(data_dir, str):
            paths["data_dir"] = self._validate_relative_dir(data_dir, "paths.data_dir")

    def _validate_relative_dir(self, value: str, field_name: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise SettingsValidationError(f"{field_name}: путь не может быть пустым")
        if cleaned.startswith("\\\\") or cleaned.startswith("//"):
            raise SettingsValidationError(f"{field_name}: UNC пути запрещены")
        if re.match(r"^[A-Za-z]:", cleaned):
            raise SettingsValidationError(f"{field_name}: абсолютные пути запрещены")

        path_obj = Path(cleaned)
        if path_obj.is_absolute():
            raise SettingsValidationError(f"{field_name}: абсолютные пути запрещены")
        if any(part == ".." for part in path_obj.parts):
            raise SettingsValidationError(f"{field_name}: переход к родительской директории запрещен")

        candidate = (self._data_root / path_obj).resolve()
        try:
            candidate.relative_to(self._data_root)
        except ValueError as exc:
            raise SettingsValidationError(
                f"{field_name}: путь выходит за пределы data_root"
            ) from exc
        return cleaned

    async def _apply_token_changes(self, auth_payload: Any) -> bool:
        if auth_payload is None:
            return False
        if not isinstance(auth_payload, dict):
            raise SettingsValidationError("Поле auth должно быть объектом")
        if "token" not in auth_payload:
            return False

        device_id = self._get_device_id()
        token_raw = auth_payload.get("token")
        token = str(token_raw).strip() if token_raw is not None else ""

        if db_manager is None:
            raise SettingsValidationError("База данных не инициализирована, токен нельзя изменить")

        if token:
            ok = await db_manager.save_auth_token(token, device_id)
            if not ok:
                raise SettingsValidationError("Не удалось сохранить токен")
            logger.info("[settings] Обновлен токен для device_id={}...", device_id[:8])
            return True

        await db_manager.clear_auth_token(device_id)
        logger.info("[settings] Токен очищен для device_id={}...", device_id[:8])
        return True

    async def _get_active_token(self, device_id: str) -> Optional[str]:
        try:
            if db_manager is None:
                return None
            return await db_manager.get_auth_token(device_id)
        except Exception as exc:
            logger.warning("[settings] Не удалось получить токен из БД: {}", exc)
            return None

    def _get_device_id(self) -> str:
        identity = IdentityManager()
        data = identity.load_or_create()
        device_id = data.get("uuid")
        if not device_id:
            raise SettingsValidationError("Не удалось определить device_id")
        return str(device_id)

    @staticmethod
    def _mask_token(token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

    async def _check_ws_endpoint(self, ws_url: str) -> Dict[str, Any]:
        parsed = urlparse(ws_url)
        if parsed.scheme not in {"ws", "wss"}:
            return {"ok": False, "message": "Некорректный ws_url (ожидается ws:// или wss://)"}
        host = parsed.hostname
        if not host:
            return {"ok": False, "message": "Некорректный ws_url: нет host"}

        if parsed.port is not None:
            port = parsed.port
        elif parsed.scheme == "wss":
            port = 443
        else:
            port = 80

        try:
            use_ssl = parsed.scheme == "wss"
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=host, port=port, ssl=use_ssl),
                timeout=3,
            )
            writer.close()
            await writer.wait_closed()
            return {"ok": True, "message": f"TCP соединение установлено ({host}:{port})"}
        except Exception as exc:
            return {"ok": False, "message": f"Недоступно ({host}:{port}): {exc}"}

    async def _check_api_endpoint(self, api_url: str) -> Dict[str, Any]:
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"}:
            return {"ok": False, "message": "Некорректный api_url (ожидается http:// или https://)"}
        if not parsed.hostname:
            return {"ok": False, "message": "Некорректный api_url: нет host"}

        base = api_url.rstrip("/")
        candidates = [f"{base}/health"]
        if parsed.path.rstrip("/") == "/api":
            root = f"{parsed.scheme}://{parsed.netloc}"
            candidates.insert(0, f"{root}/health")

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            last_error = "Не удалось подключиться"
            for url in candidates:
                try:
                    async with session.get(url) as resp:
                        if resp.status < 500:
                            return {"ok": True, "message": f"HTTP {resp.status} ({url})"}
                        last_error = f"HTTP {resp.status} ({url})"
                except Exception as exc:
                    last_error = f"{url}: {exc}"
            return {"ok": False, "message": last_error}
