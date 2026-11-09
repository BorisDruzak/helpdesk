from types import SimpleNamespace
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
import web_api.session_handlers as handlers

pytestmark = [pytest.mark.asyncio, pytest.mark.no_db]


@pytest.mark.parametrize("enabled", [False, True])
async def test_sso_capability_exposes_only_safe_login_policy(monkeypatch, enabled):
    monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", False)
    monkeypatch.setattr(handlers.config_module, "OIDC_ENABLED", enabled)
    response = await handlers.handle_web_session_capabilities(SimpleNamespace())
    assert json.loads(response.body)["data"] == {
        "self_registration_enabled": False, "sso_enabled": enabled,
    }
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("url, expected", [
    ("", None),
    ("https://endpoint.sosnadmin.local/employee", "https://endpoint.sosnadmin.local/employee"),
    ("http://endpoint.sosnadmin.local/employee", None),
    ("https://endpoint.sosnadmin.local.evil.test/employee", None),
    ("https://user:secret@endpoint.sosnadmin.local/employee", None),
    ("https://endpoint.sosnadmin.local/employee?person_id=another", None),
    ("https://endpoint.sosnadmin.local/employee#secret", None),
    ("https://endpoint.sosnadmin.local/employee/other", None),
    ("https://endpoint.sosnadmin.local:444/employee", None),
])
async def test_worktime_navigation_accepts_only_fixed_trusted_portal(monkeypatch, url, expected):
    monkeypatch.setattr(handlers.config_module, "SERVER_PUBLIC_BASE_URL", "https://helpdesk.sosnadmin.local")
    monkeypatch.setattr(handlers.config_module, "WORKTIME_PORTAL_URL", url, raising=False)
    payload = handlers._build_session_payload(user_login="employee", actor_role="user", auth_type="ui_token")
    assert payload.worktime_portal_url == expected


@pytest.mark.parametrize("origin, portal, expected", [
    ("https://helpdesk.sosnadmin.local", "https://endpoint.sosnadmin.local/employee", "https://endpoint.sosnadmin.local/employee"),
    ("https://helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee", "https://endpoint-staging.sosnadmin.local/employee"),
    ("https://helpdesk.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("https://helpdesk-staging.sosnadmin.local", "https://endpoint.sosnadmin.local/employee", None),
    ("", "https://endpoint.sosnadmin.local/employee", None),
    ("https://untrusted.example", "https://endpoint.sosnadmin.local/employee", None),
    ("https://helpdesk-staging.sosnadmin.local.evil.test", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("http://helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("https://helpdesk-staging.sosnadmin.local:444", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("https://helpdesk-staging.sosnadmin.local/path", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("https://user:secret@helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee", None),
    ("https://helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee?person_id=another", None),
    ("https://helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local/employee#secret", None),
    ("https://helpdesk-staging.sosnadmin.local", "https://endpoint-staging.sosnadmin.local:443/employee", None),
    ("https://helpdesk-staging.sosnadmin.local", "https://user:secret@endpoint-staging.sosnadmin.local/employee", None),
])
async def test_worktime_navigation_is_bound_to_configured_helpdesk_origin(monkeypatch, origin, portal, expected):
    monkeypatch.setattr(handlers.config_module, "SERVER_PUBLIC_BASE_URL", origin)
    monkeypatch.setattr(handlers.config_module, "WORKTIME_PORTAL_URL", portal)
    payload = handlers._build_session_payload(user_login="employee", actor_role="user", auth_type="ui_token")
    assert payload.worktime_portal_url == expected


async def test_session_projects_verified_login_method_only(monkeypatch):
    async def build(**kwargs):
        return handlers._build_session_payload(**kwargs)

    monkeypatch.setattr(handlers, "_build_effective_session_payload", build)
    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext(actor_id="employee", actor_role="user", auth_type=AuthType.UI_TOKEN)
        request["ui_login_method"] = "oidc"
        return await handler(request)

    app = web.Application(middlewares=[auth])
    app.router.add_get("/me", handlers.handle_web_session_me)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/me?login_method=password")
        data = (await response.json())["data"]
    assert data["auth_type"] == "ui_token"
    assert data["login_method"] == "oidc"


@pytest.mark.parametrize("endpoint", ["", "https://untrusted.example/logout"])
@pytest.mark.parametrize("accept, expected_status", [("text/html", 303), ("application/json", 200)])
async def test_oidc_logout_returns_browser_to_fixed_login_without_valid_rp(monkeypatch, endpoint, accept, expected_status):
    from auth import oidc
    calls = []

    async def local_logout(request):
        calls.append("local_revoked")
        response = web.json_response({"status": "success", "data": {"cleared": True}})
        response.del_cookie("pc_client_web_session", path="/")
        return response

    monkeypatch.setattr(handlers, "handle_web_session_logout", local_logout)
    monkeypatch.setattr(oidc.config, "OIDC_ENABLED", True)
    monkeypatch.setattr(oidc.config, "OIDC_ISSUER", "https://sso.example/realm")
    monkeypatch.setattr(oidc.config, "OIDC_REDIRECT_URI", "https://helpdesk.example/api/web/session/oidc/callback")
    monkeypatch.setattr(oidc.config, "OIDC_POST_LOGOUT_REDIRECT_URI", "https://helpdesk.example/app/login")
    monkeypatch.setattr(oidc.config, "OIDC_END_SESSION_ENDPOINT", endpoint)
    app = web.Application()
    app.router.add_post("/logout", oidc.handle_oidc_logout)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/logout?next=https://untrusted.example", headers={"Accept": accept}, allow_redirects=False)
        assert response.status == expected_status
        assert "Max-Age=0" in response.headers["Set-Cookie"]
        if accept == "text/html":
            assert response.headers["Location"] == "/app/login"
        else:
            assert "Location" not in response.headers
    assert calls == ["local_revoked"]
