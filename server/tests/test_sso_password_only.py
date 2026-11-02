"""Password-only AD assurance never replaces identity or upstream-session checks."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

from aiohttp.test_utils import make_mocked_request
from cryptography.fernet import Fernet
import pytest

import auth.oidc as oidc
import config
from app.db.models import OidcSession, UiToken

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.fixture
def authority(monkeypatch):
    monkeypatch.setattr(config, "OIDC_ENABLED", True)
    monkeypatch.setattr(config, "OIDC_ISSUER", "https://sso.example")
    monkeypatch.setattr(config, "OIDC_PRIVILEGED_ACR", "urn:org:loa:2")
    monkeypatch.setattr(config, "OIDC_AD_GUID_CLAIM", "ad_object_guid")
    monkeypatch.setattr(config, "OIDC_REDIRECT_URI", "https://helpdesk.example/api/web/session/oidc/callback")
    monkeypatch.setattr(config, "OIDC_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(oidc, "_configured", lambda: None)
    monkeypatch.setattr(oidc, "check_rate_limit", lambda *a, **kw: True)
    monkeypatch.setattr(oidc, "metadata", AsyncMock(return_value={
        "authorization_endpoint": "https://sso.example/auth",
        "token_endpoint": "https://sso.example/token", "jwks_uri": "https://sso.example/keys"}))
    monkeypatch.setattr(oidc, "_json", AsyncMock(return_value={}))
    binding = SimpleNamespace(binding_id="binding", issuer="https://sso.example", subject="subject",
                              ad_object_guid="guid", user_login="employee")
    user = SimpleNamespace(user_login="employee", actor_role="user")
    identity = SimpleNamespace(_active=AsyncMock(return_value=(None, user)),
                               resolve_binding=AsyncMock(return_value=binding), _audit=lambda *a: None)
    monkeypatch.setattr(oidc, "IdentityService", lambda session: identity)
    claims = dict(iss=binding.issuer, sub=binding.subject, ad_object_guid=binding.ad_object_guid,
                  sid="session", exp=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
    monkeypatch.setattr(oidc, "validate_id_token", lambda *a: claims)
    introspect = AsyncMock(return_value=True)
    monkeypatch.setattr(oidc, "_introspect", introspect)
    flow = SimpleNamespace(nonce="nonce", verifier_encrypted=oidc._cipher().encrypt(b"verifier").decode())
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: flow)),
                              commit=AsyncMock(), flush=AsyncMock(), add=lambda row: rows.append(row))
    rows = []
    @asynccontextmanager
    async def sessions():
        yield session
    monkeypatch.setattr(oidc, "get_session", sessions)
    return SimpleNamespace(binding=binding, user=user, identity=identity, claims=claims, session=session,
                           rows=rows, introspect=introspect)


async def test_login_does_not_request_mfa_even_with_legacy_acr_config(authority):
    # Use the real pinned Authlib URL builder, including PKCE and state.
    response = await oidc.handle_oidc_login(make_mocked_request("GET", "/api/web/session/oidc/login"))
    assert response.status == 302
    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert "acr_values" not in query and "claims" not in query
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] and query["nonce"]
    assert response.cookies[oidc.FLOW_COOKIE]["httponly"]


@pytest.mark.parametrize("role", ["user", "support", "admin", "auditor"])
async def test_callback_accepts_domain_password_for_every_role(authority, monkeypatch, role):
    authority.user.actor_role = role
    client = SimpleNamespace(fetch_token=AsyncMock(return_value={"access_token": "access", "id_token": "signed",
        "expires_at": authority.claims["exp"], "refresh_token": "refresh"}))
    @asynccontextmanager
    async def oauth(**kwargs):
        yield client
    monkeypatch.setattr(oidc, "oauth_client", oauth)
    request = make_mocked_request("GET", "/api/web/session/oidc/callback?state=state&code=code",
                                 headers={"Cookie": oidc.FLOW_COOKIE + "=browser"})
    response = await oidc.handle_oidc_callback(request)
    assert response.status == 302
    assert response.headers["Location"] == "/app"
    token = next(row for row in authority.rows if isinstance(row, UiToken))
    assert token.actor_role == role and token.auth_method == "oidc"
    assert any(isinstance(row, OidcSession) and row.acr is None for row in authority.rows)
    authority.identity.resolve_binding.assert_awaited_once_with("https://sso.example", "subject", "guid")
    authority.introspect.assert_awaited_once()


@pytest.mark.parametrize("role", ["user", "support", "admin", "auditor"])
@pytest.mark.parametrize("refresh", [False, True])
async def test_session_and_refresh_do_not_require_mfa(authority, monkeypatch, role, refresh):
    authority.user.actor_role = role
    now = datetime.now(timezone.utc)
    encrypted = oidc._cipher().encrypt(b"access").decode()
    record = SimpleNamespace(max_expires_at=now + timedelta(hours=1),
        expires_at=now + timedelta(seconds=-1 if refresh else 180), binding_id="binding",
        refresh_token_encrypted=encrypted, upstream_token_encrypted=encrypted,
        nonce="nonce", upstream_sid="session", acr=None)
    authority.session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: record)
    authority.session.get = AsyncMock(return_value=authority.binding)
    client = SimpleNamespace(refresh_token=AsyncMock(return_value={"access_token": "renewed", "id_token": "signed",
                                                                   "expires_at": authority.claims["exp"]}))
    @asynccontextmanager
    async def oauth(**kwargs):
        yield client
    monkeypatch.setattr(oidc, "oauth_client", oauth)
    assert await oidc.validate_oidc_session(authority.session, SimpleNamespace(token_hash="hash"), authority.user)
    authority.introspect.assert_awaited_once()
    assert client.refresh_token.await_count == int(refresh)


async def test_password_only_session_still_rejects_revoked_upstream(authority):
    now = datetime.now(timezone.utc)
    record = SimpleNamespace(max_expires_at=now + timedelta(hours=1), expires_at=now + timedelta(minutes=3),
        binding_id="binding", upstream_token_encrypted=oidc._cipher().encrypt(b"access").decode(),
        upstream_sid="session", acr=None)
    authority.session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: record)
    authority.session.get = AsyncMock(return_value=authority.binding)
    authority.user.actor_role = "admin"
    authority.introspect.return_value = False
    assert not await oidc.validate_oidc_session(authority.session, SimpleNamespace(token_hash="hash"), authority.user)
    authority.introspect.assert_awaited_once()
