from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORT_PREFIXES = (
    "websocket.protocol",
    "websocket.agent_handler",
    "websocket.state_manager",
    "state_manager",
    "app.repos.device_outbox_repo",
    "tools.service",
    "pc_agent",
    "auth.agent",
    "auth.token",
    "agent_auth",
    "agent_tokens",
    "remote_assist",
)
GUARDED_PATHS = (
    ROOT / "server" / "endpoint_adapter",
    ROOT / "server" / "diagnostics" / "providers" / "endpoint_platform.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def test_endpoint_cutover_surface_has_no_legacy_agent_runtime_imports():
    files = []
    for path in GUARDED_PATHS:
        files.extend(path.rglob("*.py") if path.is_dir() else [path])
    files.extend((ROOT / "server" / "app" / "services").glob("endpoint_*.py"))

    violations = {
        path.relative_to(ROOT).as_posix(): sorted(
            imported
            for forbidden in FORBIDDEN_IMPORT_PREFIXES
            for imported in _imports(path)
            if imported == forbidden or imported.startswith(f"{forbidden}.")
        )
        for path in files
    }
    assert {path: values for path, values in violations.items() if values} == {}


def test_ws_ui_route_registration_remains_present():
    routes = (ROOT / "server" / "routes.py").read_text(encoding="utf-8")
    assert "web.get('/ws_ui', websocket_ui_handler)" in routes
