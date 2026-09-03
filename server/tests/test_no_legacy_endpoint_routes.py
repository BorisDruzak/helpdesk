from __future__ import annotations

from pathlib import Path

from aiohttp import web
import pytest

from routes import setup_routes


pytestmark = pytest.mark.no_db


def _registered_paths() -> set[str]:
    app = web.Application()
    setup_routes(app)
    return {resource.canonical for resource in app.router.resources()}


def test_legacy_agent_control_routes_are_not_registered() -> None:
    paths = _registered_paths()

    forbidden = {
        "/ws",
        "/api/login",
        "/api/connection_request",
        "/api/connection_request/status",
        "/api/admin/connection_policy",
        "/api/admin/connection_requests",
        "/api/admin/connection_requests/{device_id}/approve",
        "/api/admin/connection_requests/{device_id}/reject",
        "/api/devices/{device_id}/tokens",
        "/api/devices/{device_id}/tokens/revoke",
        "/api/tools/run",
        "/api/web/support/tickets/{ticket_id}/tools/run",
        "/api/chat_start",
        "/api/chat_send",
        "/api/active_chats",
        "/api/job_events",
        "/test_simple",
        "/api/start_job",
        "/api/modules",
        "/api/modules/ping",
        "/api/install_module_package",
        "/api/web/admin/modules",
        "/api/web/admin/inventory/bulk-refresh",
        "/api/web/admin/devices/{device_id}/inventory/collect",
        "/api/web/admin/devices/{device_id}/presence/collect",
        "/api/registry/agent/account-state",
        "/api/registry/agent/browser-pairings",
        "/api/registry/profile",
        "/api/registry/agent/profile",
        "/api/registry/agent/registration-form",
        "/api/registry/agent/registration-status",
        "/api/registry/agent/claims/{claim_id}/confirm",
        "/api/web/registry/browser-pairings/lookup",
        "/api/web/admin/registry/account-sessions",
        "/api/web/admin/registry/bulk/account-sessions/revoke",
        "/api/web/admin/registry/bulk/devices/revoke-account-sessions",
        "/api/web/admin/registry/devices/{device_id}/account-sessions",
        "/api/web/admin/registry/account-sessions/{session_id}/timeline",
        "/api/web/admin/registry/account-sessions/{session_id}/revoke",
        "/api/web/admin/registry/account-login-requests",
        "/api/web/admin/registry/account-login-requests/{request_id}/approve",
        "/api/web/admin/registry/account-login-requests/{request_id}/reject",
        "/api/web/admin/registry/devices/{device_id}/account-events",
        "/api/web/admin/registry/identity/session/{session_id}/explain",
    }

    assert paths.isdisjoint(forbidden)
    assert all("remote-assist" not in path for path in paths)


def test_endpoint_operation_routes_remain_but_module_authority_is_absent() -> None:
    paths = _registered_paths()

    assert "/api/web/support/operations/{operation_id}/cancel" in paths
    assert all("endpoint-modules" not in path for path in paths)


def test_legacy_account_session_admin_client_is_removed() -> None:
    client_source = (
        Path(__file__).resolve().parents[2]
        / "webapp"
        / "src"
        / "features"
        / "admin"
        / "api.ts"
    ).read_text(encoding="utf-8")

    assert "account-sessions" not in client_source
    assert "revoke_account_sessions" not in client_source


def test_registry_snapshot_does_not_load_account_session_runtime() -> None:
    server_root = Path(__file__).resolve().parents[1]
    snapshot_source = (server_root / "registry" / "service.py").read_text(encoding="utf-8")

    assert "AccountSessionService" not in snapshot_source
    assert "account_sessions" not in snapshot_source
    assert "account_login_requests" not in snapshot_source


def test_retired_account_session_runtime_files_are_absent() -> None:
    server_root = Path(__file__).resolve().parents[1]

    assert not (server_root / "registry" / "account_session_service.py").exists()
    assert not (server_root / "app" / "repos" / "account_session_repo.py").exists()


def test_retired_agent_telemetry_ingest_repository_is_absent() -> None:
    server_root = Path(__file__).resolve().parents[1]

    assert not (server_root / "app" / "repos" / "agent_observer_events_repo.py").exists()


def test_retired_agent_command_test_page_is_absent() -> None:
    server_root = Path(__file__).resolve().parents[1]

    assert not (server_root / "test_web_simple.html").exists()
