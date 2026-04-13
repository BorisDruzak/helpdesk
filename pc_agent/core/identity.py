from __future__ import annotations

import json
import platform
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from pc_agent.core.machine_identity import resolve_machine_identity


def _default_identity_file() -> Path:
    try:
        from pc_agent.config.config_loader import get_config, get_config_base

        base = get_config_base()
        cfg = get_config()
        if base is not None:
            return (base / "identity.json").resolve()
        configured = Path(cfg.paths.identity_file)
        if configured.is_absolute():
            return configured
    except Exception as exc:
        logger.warning("Identity config unavailable, using default path: {}", exc)
    return Path("data/identity.json").resolve()


class IdentityManager:
    """
    Agent runtime identity.

    Canonical model:
    - machine_id is the stable server-facing device identity
    - install_id is per-install and used only as secondary metadata
    - identity.json keeps uuid=machine_id for backward-compatible readers
    """

    def __init__(self, identity_file: Optional[str] = None):
        self.identity_file = Path(identity_file).expanduser().resolve() if identity_file else _default_identity_file()
        self.uuid: Optional[str] = None
        self.machine_id: Optional[str] = None
        self.install_id: Optional[str] = None
        self.legacy_uuid: Optional[str] = None
        self.machine_id_source: Optional[str] = None
        self.token: Optional[str] = None

    @staticmethod
    def is_valid_uuid(value: Any) -> bool:
        if value is None or not isinstance(value, str):
            return False
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            return False
        return str(parsed) == value.lower()

    @property
    def device_id(self) -> Optional[str]:
        return self.machine_id or self.uuid

    def _build_payload(
        self,
        *,
        install_id: str,
        machine_id: str,
        machine_id_source: str,
        previous_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "version": 2,
            "uuid": machine_id,
            "machine_id": machine_id,
            "install_id": install_id,
            "machine_id_source": machine_id_source,
            "token": None,
        }
        previous_data = previous_data or {}
        legacy_uuid = previous_data.get("uuid")
        if self.is_valid_uuid(legacy_uuid) and legacy_uuid not in {machine_id, install_id}:
            payload["legacy_uuid"] = legacy_uuid
        return payload

    def load_or_create(self) -> Dict[str, Any]:
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)
        machine_id, machine_id_source = resolve_machine_identity()

        previous_data: Dict[str, Any] = {}
        if self.identity_file.exists():
            try:
                previous_data = json.loads(self.identity_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning("Invalid identity.json, recreating it: {}", exc)
            except OSError as exc:
                logger.warning("Failed to read identity.json, recreating it: {}", exc)

        install_id = previous_data.get("install_id")
        if not self.is_valid_uuid(install_id):
            legacy_uuid = previous_data.get("uuid")
            if self.is_valid_uuid(legacy_uuid) and legacy_uuid != machine_id:
                install_id = legacy_uuid
        if not self.is_valid_uuid(install_id):
            install_id = str(uuid.uuid4())

        self.machine_id = machine_id
        self.uuid = machine_id
        self.install_id = install_id
        legacy_uuid = previous_data.get("legacy_uuid")
        self.legacy_uuid = legacy_uuid if self.is_valid_uuid(legacy_uuid) else None
        self.machine_id_source = machine_id_source
        self.token = None

        payload = self._build_payload(
            install_id=install_id,
            machine_id=machine_id,
            machine_id_source=machine_id_source,
            previous_data=previous_data,
        )
        if previous_data != payload:
            self._save_to_file(payload)

        logger.info(
            "Identity loaded: machine_id={} install_id={} source={}",
            machine_id[:8],
            install_id[:8],
            machine_id_source,
        )
        return payload

    def save_token(self, token: str) -> None:
        self.token = token
        logger.info("[IdentityManager] Token loaded into memory: {}...", token[:8])

    def get_handshake_data(self) -> Dict[str, Any]:
        hostname = socket.gethostname()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
        except Exception:
            ip = "127.0.0.1"

        return {
            "uuid": self.device_id,
            "machine_id": self.device_id,
            "install_id": self.install_id,
            "machine_id_source": self.machine_id_source,
            "token": self.token,
            "hostname": hostname,
            "ip": ip,
            "os": platform.system(),
            "os_version": platform.release(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
        }

    def get_identity_metadata(self) -> Dict[str, Any]:
        return {
            "machine_id": self.device_id,
            "install_id": self.install_id,
            "machine_id_source": self.machine_id_source,
            "identity_scheme": "machine_id_v1",
        }

    def auth_lookup_ids(self) -> list[str]:
        """
        Candidate device IDs for local auth token lookup.

        During migration from legacy install-based identity to canonical
        machine_id identity, existing local tokens may still be stored under
        install_id (former device_id). We look up those IDs as fallbacks so the
        runtime can reuse the token and let the server perform controlled
        rebinding on first successful handshake.
        """
        candidates = [
            self.device_id,
            self.install_id,
            self.legacy_uuid,
            self.uuid,
        ]
        result: list[str] = []
        for item in candidates:
            if not self.is_valid_uuid(item):
                continue
            normalized = str(item).lower()
            if normalized not in result:
                result.append(normalized)
        return result

    def clear_token(self) -> None:
        self.token = None
        logger.info("Token cleared from memory")

    def _save_to_file(self, data: Dict[str, Any]) -> None:
        try:
            self.identity_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.debug("Identity saved to {}", self.identity_file)
        except OSError as exc:
            logger.error("Failed to save identity data: {}", exc)

    @property
    def has_token(self) -> bool:
        try:
            from core.database import db_manager

            if db_manager:
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        return bool(self.token)
                    token = loop.run_until_complete(db_manager.get_auth_token(self.device_id))
                    if token:
                        self.token = token
                        return True
                except RuntimeError:
                    token = asyncio.run(db_manager.get_auth_token(self.device_id))
                    if token:
                        self.token = token
                        return True
        except Exception as exc:
            logger.debug("[IdentityManager] Failed to check token in DB: {}", exc)
        return bool(self.token)

    def validate_device_id(self) -> bool:
        return self.is_valid_uuid(self.device_id)
