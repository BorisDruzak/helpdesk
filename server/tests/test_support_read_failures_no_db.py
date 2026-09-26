from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from web_api import support_handlers as handlers

pytestmark = pytest.mark.no_db


class Request(dict):
    def __init__(self, query=None):
        super().__init__(auth_context=SimpleNamespace(actor_id="test-support", actor_role="support"))
        self.query = query or {}
        self.path = "/api/web/support/test"


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [handlers.handle_web_support_command_center, handlers.handle_web_support_workspace_summary])
async def test_support_read_dependency_failure_is_explicit(monkeypatch, handler):
    @asynccontextmanager
    async def unavailable():
        raise RuntimeError("private database details")
        yield

    monkeypatch.setattr(handlers, "get_session", unavailable)
    response = await handler(Request())
    assert response.status == 503
    body = json.loads(response.text)
    assert body["status"] == "error" and body["error_code"] == "DB_UNAVAILABLE"
    assert "private database details" not in response.text
    assert "data" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [handlers.handle_web_support_queue, handlers.handle_web_support_workspace_summary])
@pytest.mark.parametrize("limit", ["abc", "1.5"])
async def test_support_read_invalid_limit_returns_400_before_query(monkeypatch, handler, limit):
    session = Mock(side_effect=AssertionError("invalid limit must not query the database"))
    monkeypatch.setattr(handlers, "get_session", session)
    response = await handler(Request({"limit": limit}))
    assert response.status == 400
    body = json.loads(response.text)
    assert body["error_code"] == "VALIDATION_ERROR"
    session.assert_not_called()
