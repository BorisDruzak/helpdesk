from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVER_ROOT.parent


ALLOWED_TRIAGED_PATHS = {
    SERVER_ROOT / "tickets" / "statuses.py",
}

TRIAGED_LEGACY_WORDS = (
    "legacy",
    "alias",
    "backfill",
    "input",
    "compat",
    "migration",
    "migrat",
    "never stored",
    "not stored",
    "не хран",
    "миграц",
)


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


def test_triaged_docs_mentions_are_legacy_compatibility_only() -> None:
    """Docs may mention triaged only when explicitly documenting legacy compatibility."""

    docs = [
        SERVER_ROOT / "docs" / "CODEMAP.md",
        SERVER_ROOT / "docs" / "DATABASE.md",
        SERVER_ROOT / "docs" / "RUNBOOK_TICKET_QUEUE_OPERATIONS.md",
        SERVER_ROOT / "docs" / "TICKET_SYSTEM.md",
    ]
    offenders: list[str] = []
    for path in docs:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if "triaged" not in line.lower():
                continue
            lowered = line.lower()
            if not any(word in lowered for word in TRIAGED_LEGACY_WORDS):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}:{line.strip()}")

    assert offenders == []


def test_triaged_occurrences_are_limited_to_legacy_alias_migrations_and_tests() -> None:
    """Repository-level guard for the legacy alias surface."""

    scanned_roots = [
        SERVER_ROOT / "tickets",
        SERVER_ROOT / "web_api",
        SERVER_ROOT / "app" / "db" / "models.py",
        SERVER_ROOT / "app" / "db" / "migrations" / "versions",
        SERVER_ROOT / "docs",
        PROJECT_ROOT / "webapp" / "src",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".py", ".js", ".ts", ".tsx", ".css", ".md"}:
                continue
            rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if "server/app/db/migrations/versions/" in rel:
                continue
            if "/tests/" in rel or rel.startswith("server/tests/"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "triaged" not in line.lower():
                    continue
                lowered = line.lower()
                if path == SERVER_ROOT / "tickets" / "statuses.py":
                    continue
                if path.suffix == ".md" and any(word in lowered for word in TRIAGED_LEGACY_WORDS):
                    continue
                offenders.append(f"{rel}:{lineno}:{line.strip()}")

    assert offenders == []
