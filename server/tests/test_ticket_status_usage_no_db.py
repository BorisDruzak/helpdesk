from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVER_ROOT.parent


ALLOWED_TRIAGED_PATHS = {
    SERVER_ROOT / "tickets" / "statuses.py",
}


def test_triaged_is_not_used_by_server_runtime_surfaces() -> None:
    """Keep legacy triaged out of runtime code except the boundary alias contract."""

    scanned_roots = [
        SERVER_ROOT / "tickets",
        SERVER_ROOT / "web_api",
        SERVER_ROOT / "app" / "db" / "models.py",
        SERVER_ROOT / "admin.js",
        SERVER_ROOT / "admin.css",
        SERVER_ROOT / "support.js",
        SERVER_ROOT / "support.css",
        SERVER_ROOT / "ticket.js",
        SERVER_ROOT / "observer",
        SERVER_ROOT / "tech",
        PROJECT_ROOT / "webapp" / "src",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".js", ".ts", ".tsx", ".css"}:
                continue
            if path in ALLOWED_TRIAGED_PATHS or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "triaged" in text:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []
