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


def test_legacy_agent_and_remote_assist_routes_are_not_registered():
    """Endpoint-only Helpdesk retains browser UI transport, never agent transport."""
    routes = (ROOT / "server" / "routes.py").read_text(encoding="utf-8")

    assert "web.get('/ws', websocket_handler)" not in routes
    assert "web.get('/ws/remote-assist/{session_id}'" not in routes
    assert "/remote-assist/" not in routes


def test_remote_assist_runtime_and_configuration_are_removed():
    remote_assist_source = ROOT / "server" / "remote_assist"
    assert list(remote_assist_source.glob("*.py")) == []

    config_source = (ROOT / "server" / "config.py").read_text(encoding="utf-8")
    assert "REMOTE_ASSIST_" not in config_source


def test_helpdesk_does_not_ship_agent_runtime_sources():
    assert list((ROOT / "server" / "agents").glob("*.py")) == []
    assert list((ROOT / "pc_agent").rglob("*.py")) == []


def test_server_lifecycle_does_not_start_device_outbox_runtime():
    source = (ROOT / "server" / "server.py").read_text(encoding="utf-8")

    assert "DeviceOutboxSender" not in source
    assert "recover_pending_commands" not in source


def test_endpoint_diagnostic_canary_runbook_preserves_forward_only_rollback_guards():
    runbook = (ROOT / "docs" / "runbooks" / "ENDPOINT_DIAGNOSTIC_CANARY.md").read_text(
        encoding="utf-8"
    )
    assert "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=endpoint" in runbook
    assert "Do not perform database downgrade" in runbook
    assert "duplicate evidence" in runbook.lower()
