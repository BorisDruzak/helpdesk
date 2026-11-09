"""Browser SSO failure recovery never reflects provider or return-target input."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

import auth.oidc as oidc
from auth.identity import IdentityError
from auth.middleware import WEB_SESSION_COOKIE_NAME

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.mark.parametrize("accept", ["text/html", "application/json"])
@pytest.mark.parametrize("failure,expected", [
    ("identity_unknown", "identity_unlinked"),
    ("identity_unconfirmed", "identity_unlinked"),
    ("identity_conflict", "identity_unlinked"),
    ("identity_inactive", "identity_unavailable"),
    ("identity_revoked", "identity_unavailable"),
    ("provider-private-message", "oidc_authentication_failed"),
])
async def test_callback_identity_failure_has_fixed_browser_recovery(monkeypatch, accept, failure, expected):
    monkeypatch.setattr(oidc.config, "OIDC_ENABLED", True)
    monkeypatch.setattr(oidc, "check_rate_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(oidc, "_configured", lambda: None)
    flow = SimpleNamespace(verifier_encrypted="encrypted", nonce="nonce")

    class Session:
        async def execute(self, statement):
            return SimpleNamespace(scalar_one_or_none=lambda: flow)

        async def commit(self):
            pass

    @asynccontextmanager
    async def sessions():
        yield Session()

    @asynccontextmanager
    async def oauth(**kwargs):
        async def fetch_token(*args, **kwargs):
            return dict(access_token="private-access", id_token="private-id", expires_at=oidc.time.time() + 60)
        yield SimpleNamespace(fetch_token=fetch_token)

    async def metadata():
        return dict(token_endpoint="https://issuer.test/token", jwks_uri="https://issuer.test/jwks")

    async def jwks(url):
        return {}

    async def resolve(self, *args):
        raise IdentityError(failure, 409)

    monkeypatch.setattr(oidc, "get_session", sessions)
    monkeypatch.setattr(oidc, "oauth_client", oauth)
    monkeypatch.setattr(oidc, "metadata", metadata)
    monkeypatch.setattr(oidc, "_json", jwks)
    monkeypatch.setattr(oidc, "_cipher", lambda: SimpleNamespace(decrypt=lambda value: b"verifier"))
    monkeypatch.setattr(oidc, "validate_id_token", lambda *args: dict(
        iss="https://issuer.test", sub="subject", exp=oidc.time.time() + 60,
        **{oidc.config.OIDC_AD_GUID_CLAIM: "guid"}))
    monkeypatch.setattr(oidc.IdentityService, "resolve_binding", resolve)
    app = web.Application()
    app.router.add_get("/callback", oidc.handle_oidc_callback)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/callback?state=state&code=private-code&next=https://evil.test&error_description=provider-private-message",
            headers={"Accept": accept, "Cookie": oidc.FLOW_COOKIE + "=browser"}, allow_redirects=False)
        assert WEB_SESSION_COOKIE_NAME not in response.cookies
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        if accept == "text/html":
            assert response.status == 302
            assert response.headers["Location"] == "/app/login?sso_error=" + expected
            assert response.cookies[oidc.FLOW_COOKIE]["max-age"] == "0"
            assert "private" not in await response.text()
        else:
            assert response.status == 409
            assert await response.json() == {"error": failure}


@pytest.mark.parametrize("route,enabled,limited,expected", [
    ("login", False, False, "oidc_disabled"),
    ("login", True, True, "rate_limited"),
    ("login", True, False, "oidc_unavailable"),
    ("callback", True, False, "oidc_authentication_failed"),
])
async def test_browser_early_failures_return_to_login(monkeypatch, route, enabled, limited, expected):
    monkeypatch.setattr(oidc.config, "OIDC_ENABLED", enabled)
    monkeypatch.setattr(oidc, "check_rate_limit", lambda *args, **kwargs: not limited)

    async def unavailable():
        raise RuntimeError("private-provider-response")

    monkeypatch.setattr(oidc, "metadata", unavailable)
    app = web.Application()
    app.router.add_get("/login", oidc.handle_oidc_login)
    app.router.add_get("/callback", oidc.handle_oidc_callback)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/" + route + "?error=access_denied&error_description=private-provider-response&next=//evil.test",
            headers={"Accept": "text/html"}, allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == "/app/login?sso_error=" + expected
        assert WEB_SESSION_COOKIE_NAME not in response.cookies
