"""Single, non-secret remote deployment profile for Helpdesk."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_REMOTE = "osn_admin@192.168.100.19"
DEFAULT_ROOT = "/opt/helpdesk/current"
DEFAULT_SSH_KEY = Path(r"C:\Users\admin-2\.ssh\id_ed25519_osn_192.168.100.19")


def _value(environment: Mapping[str, str], name: str, default: str) -> str:
    return str(environment.get(name) or default).strip() or default


def _optional_value(environment: Mapping[str, str], name: str, default: str | None) -> str | None:
    if name not in environment:
        return default
    value = str(environment[name]).strip()
    return value or None


@dataclass(frozen=True)
class RemoteProfile:
    remote: str
    root: str
    server_python: str
    ssh_key: Path
    environment_file: str
    migrate_service: str
    server_service: str
    control_service: str | None
    release_venv_path: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "RemoteProfile":
        values = os.environ if environment is None else environment
        root = _value(values, "HELPDESK_REMOTE_ROOT", DEFAULT_ROOT).rstrip("/")
        return cls(
            remote=_value(values, "HELPDESK_REMOTE", DEFAULT_REMOTE),
            root=root,
            server_python=_value(values, "HELPDESK_REMOTE_SERVER_PYTHON", f"{root}/server/venv/bin/python"),
            ssh_key=Path(_value(values, "HELPDESK_SSH_KEY", str(DEFAULT_SSH_KEY))),
            environment_file=_value(values, "HELPDESK_ENV_FILE", "/etc/helpdesk/helpdesk.env"),
            migrate_service=_value(values, "HELPDESK_MIGRATE_SERVICE", "helpdesk-migrate.service"),
            server_service=_value(values, "HELPDESK_SERVER_SERVICE", "helpdesk-server.service"),
            control_service=_optional_value(values, "HELPDESK_CONTROL_SERVICE", "helpdesk-control.service"),
            release_venv_path=_value(values, "HELPDESK_RELEASE_VENV_PATH", "server/venv").strip("/"),
        )
