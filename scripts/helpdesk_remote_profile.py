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


@dataclass(frozen=True)
class RemoteProfile:
    remote: str
    root: str
    server_python: str
    ssh_key: Path

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "RemoteProfile":
        values = os.environ if environment is None else environment
        root = _value(values, "HELPDESK_REMOTE_ROOT", DEFAULT_ROOT).rstrip("/")
        return cls(
            remote=_value(values, "HELPDESK_REMOTE", DEFAULT_REMOTE),
            root=root,
            server_python=_value(values, "HELPDESK_REMOTE_SERVER_PYTHON", f"{root}/server/venv/bin/python"),
            ssh_key=Path(_value(values, "HELPDESK_SSH_KEY", str(DEFAULT_SSH_KEY))),
        )
