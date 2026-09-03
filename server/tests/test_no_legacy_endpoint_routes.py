from __future__ import annotations

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
        "/api/tools/run",
        "/api/chat_start",
        "/api/chat_send",
        "/api/active_chats",
        "/api/job_events",
        "/api/start_job",
        "/api/modules",
        "/api/modules/ping",
        "/api/install_module_package",
        "/api/web/admin/modules",
    }

    assert paths.isdisjoint(forbidden)
    assert all("remote-assist" not in path for path in paths)


def test_endpoint_operation_and_module_bff_routes_remain_registered() -> None:
    paths = _registered_paths()

    assert "/api/web/support/operations/{operation_id}/cancel" in paths
    assert "/api/web/support/tickets/{ticket_id}/endpoint-modules/{module_key}/{version}/run" in paths
