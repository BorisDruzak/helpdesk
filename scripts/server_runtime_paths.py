"""Shared filesystem paths for Helpdesk server lifecycle wrappers."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_run_dir(workspace: Path) -> Path:
    """Return the mutable PID directory for the current server environment."""
    explicit_runtime_dir = os.getenv("HELPDESK_RUNTIME_DIR", "").strip()
    if explicit_runtime_dir:
        return Path(explicit_runtime_dir)

    server_data_root = os.getenv("PC_CLIENT_SERVER_DATA_ROOT", "").strip()
    if server_data_root:
        return Path(server_data_root) / "run"

    return workspace / ".run" if os.name == "nt" else Path("/var/lib/helpdesk/run")
