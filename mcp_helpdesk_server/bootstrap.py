from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_DB_STARTED = False


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def server_root() -> Path:
    return repo_root() / "server"


def configure_paths() -> tuple[Path, Path]:
    root = repo_root()
    srv = server_root()
    for path in (str(root), str(srv)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return root, srv


async def ensure_db_started() -> dict[str, Any]:
    global _DB_STARTED
    configure_paths()
    if _DB_STARTED:
        return {"started": False, "already_started": True}
    import config
    from app.db import init_db

    await init_db(config.DATABASE_URL)
    _DB_STARTED = True
    return {"started": True, "already_started": False}


async def shutdown_db_if_started() -> None:
    global _DB_STARTED
    if not _DB_STARTED:
        return
    configure_paths()
    from app.db import shutdown_db

    await shutdown_db()
    _DB_STARTED = False


def db_started() -> bool:
    return _DB_STARTED
