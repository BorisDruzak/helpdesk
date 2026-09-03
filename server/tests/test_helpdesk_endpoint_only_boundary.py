from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


ROOT = Path(__file__).resolve().parents[2]
ENDPOINT_BFF_SOURCES = (
    ROOT / "server" / "web_api" / "endpoint_operation_handlers.py",
    ROOT / "server" / "diagnostics" / "providers" / "endpoint_platform.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "websocket.protocol",
    "websocket.agent_handler",
    "app.repos.device_outbox_repo",
    "tools.service",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return {
        name
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module
            else []
        )
    }


def test_endpoint_bff_never_imports_legacy_dispatch_runtime() -> None:
    violations = {
        path.relative_to(ROOT).as_posix(): sorted(
            imported
            for imported in _imports(path)
            if any(imported == forbidden or imported.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_IMPORT_PREFIXES)
        )
        for path in ENDPOINT_BFF_SOURCES
    }

    assert {path: imports for path, imports in violations.items() if imports} == {}


def test_endpoint_execution_mode_has_no_legacy_fallback() -> None:
    config = (ROOT / "server" / "config.py").read_text(encoding="utf-8")

    assert "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy" not in config


def test_helpdesk_ships_only_browser_ui_websocket_transport() -> None:
    websocket_dir = ROOT / "server" / "websocket"
    legacy_sources = {
        path.name
        for path in websocket_dir.glob("*.py")
        if path.name not in {"__init__.py", "subscription_registry.py", "ui_handler.py", "ui_publisher.py"}
    }

    assert legacy_sources == {}
