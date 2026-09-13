from __future__ import annotations

from aiohttp import web
import pytest

from routes import setup_routes


pytestmark = pytest.mark.no_db


def test_browser_ws_ui_route_remains_while_agent_ws_route_is_absent() -> None:
    app = web.Application()
    setup_routes(app)
    paths = {resource.canonical for resource in app.router.resources()}

    assert "/ws_ui" in paths
    assert "/ws" not in paths
