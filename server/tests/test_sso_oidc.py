"""Real Authlib PKCE/token parsing with fake provider HTTP; never real pilot evidence."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import time
import uuid

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from authlib.integrations.httpx_client import AsyncOAuth2Client
from cryptography.fernet import Fernet
import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import func, select

import auth.oidc as oidc
import auth.service as auth_service_module
import config
from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser, OidcSession, UiToken
from auth.identity import IdentityService
from auth.middleware import auth_middleware, WEB_SESSION_COOKIE_NAME
from auth.password_service import hash_password
from auth.service import AuthService

pytestmark = pytest.mark.db_cleanup("registry_access")


@pytest.fixture
def oidc_config(monkeypatch):
    for name, value in dict(OIDC_ENABLED=True, OIDC_ISSUER="https://sso.example/realms/org",
        OIDC_CLIENT_ID="helpdesk-web", OIDC_CLIENT_SECRET="test-only-client-secret",
        OIDC_REDIRECT_URI="https://helpdesk.example/api/web/session/oidc/callback",
        OIDC_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(), OIDC_PRIVILEGED_ACR="urn:org:loa:2",
        OIDC_AD_GUID_CLAIM="ad_object_guid", WEB_SESSION_COOKIE_SECURE=True,
        OIDC_CA_FILE="", OIDC_END_SESSION_ENDPOINT="", OIDC_POST_LOGOUT_REDIRECT_URI="",
        WEB_CSRF_SAME_ORIGIN_ENABLED=True, AUTH_UI_CONFIG_FALLBACK_ENABLED=False,
        ALLOW_INSECURE_DEV_DEFAULTS=False).items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0)


@pytest.mark.no_db
@pytest.mark.parametrize("defect", ["issuer", "audience", "nonce", "expired", "missing_guid", "subject_type", "signature"])
def test_authlib_rejects_invalid_id_token(oidc_config, defect):
    key = RSAKey.generate_key(2048, private=True)
    claims = dict(iss=config.OIDC_ISSUER, aud=config.OIDC_CLIENT_ID, sub="CaseSub", nonce="nonce",
                  iat=int(time.time()), exp=int(time.time()) + 60, ad_object_guid=str(uuid.uuid4()))
    if defect == "issuer": claims["iss"] = "https://wrong.example"
    if defect == "audience": claims["aud"] = "endpoint-admin"
    if defect == "nonce": claims["nonce"] = "other-nonce"
    if defect == "expired": claims["exp"] = int(time.time()) - 1
    if defect == "missing_guid": claims.pop("ad_object_guid")
    if defect == "subject_type": claims["sub"] = 123
    signer = RSAKey.generate_key(2048, private=True) if defect == "signature" else key
    encoded = jwt.encode({"alg": "RS256"}, claims, signer)
    with pytest.raises(Exception):
        oidc.validate_id_token(encoded, {"keys": [key.as_dict(private=False)]}, "nonce", "access-token")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["user", "support", "admin", "auditor"])
async def test_bff_pkce_cookie_replay_revocation_migration_and_no_password_bypass(test_engine, monkeypatch, oidc_config, role):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id, guid, login = str(uuid.uuid4()), str(uuid.uuid4()), "sso-" + uuid.uuid4().hex
    issuer, subject, sid = config.OIDC_ISSUER, "CaseSensitive-sub", "provider-session"
    password = "Pilot-only-long-password-726!"
    async with maker() as session:
        password_hash = hash_password(password)
        session.add_all([RegistryPerson(person_id=person_id, display_name="Pilot", status="active", metadata_json={"preserve": "existing-profile"}),
            UiUser(user_login=login, password_hash=password_hash, actor_role=role, is_active=True)])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True))
        await session.commit()
        service = IdentityService(session)
        candidate = await service.propose(person_id=person_id, user_login=login, issuer=issuer, subject=subject, ad_object_guid=guid, actor_id="operator")
        binding = await service.confirm(candidate.candidate_id, actor_id="operator", verification_reference="AD owner independently verified")
        binding_id = binding.binding_id
        baseline_people = await session.scalar(select(func.count()).select_from(RegistryPerson))
        baseline_users = await session.scalar(select(func.count()).select_from(UiUser))

    @asynccontextmanager
    async def sessions():
        async with maker() as session:
            yield session
            await session.commit()
    monkeypatch.setattr(oidc, "get_session", sessions)
    monkeypatch.setattr(auth_service_module, "get_session", sessions)
    key = RSAKey.generate_key(2048, private=True)
    meta = dict(issuer=issuer, authorization_endpoint=issuer + "/auth", token_endpoint=issuer + "/token",
                introspection_endpoint=issuer + "/introspect", jwks_uri=issuer + "/certs")
    provider = {"active": True, "nonce": None, "verifier": None, "down": False,
                "refresh_count": 0, "refresh_reject": False, "access": "provider-access-secret", "refresh": "provider-refresh-secret"}

    async def fake_metadata():
        oidc._configured()
        if provider["down"]:
            raise httpx.ConnectError("provider down")
        return meta

    async def jwks(url):
        return {"keys": [key.as_dict(private=False)]}

    def provider_http(request):
        form = parse_qs(request.content.decode())
        if request.url.path.endswith("/token"):
            if form["grant_type"] == ["refresh_token"]:
                assert form["refresh_token"] == [provider["refresh"]]
                if provider["refresh_reject"]:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                provider["refresh_count"] += 1
                provider["access"] = "rotated-access-" + str(provider["refresh_count"])
                provider["refresh"] = "rotated-refresh-" + str(provider["refresh_count"])
            else:
                assert form["grant_type"] == ["authorization_code"]
                assert form["code"] == ["issued-code"]
                assert form["redirect_uri"] == [config.OIDC_REDIRECT_URI]
                verifier = form["code_verifier"][0]
                from authlib.oauth2.rfc7636 import create_s256_code_challenge
                assert create_s256_code_challenge(verifier) == provider["challenge"]
            encoded = jwt.encode({"alg": "RS256"}, dict(iss=issuer, sub=subject, aud=config.OIDC_CLIENT_ID,
                iat=int(time.time()), exp=int(time.time()) + 600, nonce=provider["nonce"], sid=sid,
                ad_object_guid=guid), key)
            return httpx.Response(200, json={"access_token": provider["access"], "token_type": "Bearer",
                "expires_in": 600, "id_token": encoded, "refresh_token": provider["refresh"]})
        assert request.url.path.endswith("/introspect")
        assert form["token"] == [provider["access"]]
        return httpx.Response(200, json=dict(active=provider["active"], sub=subject, sid=sid,
            iss=issuer, client_id=config.OIDC_CLIENT_ID, exp=int(time.time()) + 600))

    def client(**kwargs):
        return AsyncOAuth2Client(config.OIDC_CLIENT_ID, config.OIDC_CLIENT_SECRET, redirect_uri=config.OIDC_REDIRECT_URI,
            scope="openid", code_challenge_method="S256", transport=httpx.MockTransport(provider_http), **kwargs)
    monkeypatch.setattr(oidc, "metadata", fake_metadata)
    monkeypatch.setattr(oidc, "_json", jwks)
    monkeypatch.setattr(oidc, "oauth_client", client)
    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_get("/api/web/session/oidc/login", oidc.handle_oidc_login)
    app.router.add_get("/api/web/session/oidc/callback", oidc.handle_oidc_callback)
    from web_api.session_handlers import handle_web_session_logout
    import web_api.session_handlers as session_handlers
    logout_audits = []
    async def quiet_observer(*args, **kwargs):
        if kwargs.get("event_type") == "logout_succeeded":
            assert args[0].get("auth_context") is None
            logout_audits.append(kwargs)
    monkeypatch.setattr(session_handlers, "_write_web_session_observer_event", quiet_observer)
    monkeypatch.setattr(session_handlers, "get_session", sessions)
    app.router.add_post("/api/web/session/logout", handle_web_session_logout)
    app.router.add_post("/api/web/session/oidc/logout", oidc.handle_oidc_logout)
    async def protected(request):
        return web.json_response({"actor": request["auth_context"].actor_id})
    app.router.add_get("/api/protected", protected)
    async with TestClient(TestServer(app)) as browser:
        start = await browser.get("/api/web/session/oidc/login", allow_redirects=False)
        assert start.status == 302
        query = parse_qs(urlsplit(start.headers["Location"]).query)
        assert query["code_challenge_method"] == ["S256"]
        assert "acr_values" not in query
        provider["nonce"], provider["challenge"] = query["nonce"][0], query["code_challenge"][0]
        callback = "/api/web/session/oidc/callback?" + "state=" + query["state"][0] + "&code=issued-code"
        cookies = {"Cookie": oidc.FLOW_COOKIE + "=" + start.cookies[oidc.FLOW_COOKIE].value}
        done = await browser.get(callback, headers=cookies, allow_redirects=False)
        assert done.status == 302 and done.headers["Location"] == "/app"
        cookie = done.cookies[WEB_SESSION_COOKIE_NAME]
        assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Lax"
        assert "provider-access-secret" not in done.headers.get("Set-Cookie", "")
        async with maker() as session:
            stored = await session.get(OidcSession, oidc.digest(cookie.value))
            assert stored.binding_id == binding_id and stored.acr is None
            user = await session.get(UiUser, login)
            assert user.actor_role == role and user.password_hash == password_hash and user.password_login_enabled
            person = await session.get(RegistryPerson, person_id)
            assert person.display_name == "Pilot" and person.metadata_json == {"preserve": "existing-profile"}
            alias = (await session.execute(select(RegistryPersonIdentity).where(
                RegistryPersonIdentity.provider == "ui_login", RegistryPersonIdentity.normalized_identifier == login))).scalar_one()
            assert alias.person_id == person_id and alias.verified
            assert await session.scalar(select(func.count()).select_from(RegistryPerson)) == baseline_people
            assert await session.scalar(select(func.count()).select_from(UiUser)) == baseline_users
        replay = await browser.get(callback, headers=cookies, allow_redirects=False)
        assert replay.status == 400
        authority = {"Cookie": WEB_SESSION_COOKIE_NAME + "=" + cookie.value}
        assert (await browser.get("/api/protected", headers=authority)).status == 200
        auth = AuthService(SimpleNamespace(users={login: password}))
        password_token = await auth.generate_ui_token(login, role, expires_hours=1)
        assert await auth.verify_ui_token(password_token) is not None
        async with maker() as session:
            await IdentityService(session).migrate_password(binding_id, actor_id="operator", verification_reference="Live pilot verified")
        assert await auth.authenticate(login, password) == (False, "")
        assert await auth.verify_ui_token(password_token) is None
        raced_password_token = await auth.generate_ui_token(login, role, expires_hours=1)
        assert await auth.verify_ui_token(raced_password_token) is None
        assert (await browser.get("/api/protected", headers=authority)).status == 200
        async with maker() as session:
            stored = await session.get(OidcSession, oidc.digest(cookie.value))
            ceiling = stored.max_expires_at
            assert ceiling <= datetime.now(timezone.utc) + timedelta(hours=8)
            assert oidc._cipher().decrypt(stored.refresh_token_encrypted.encode()).decode() == "provider-refresh-secret"
            stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        assert (await browser.get("/api/protected", headers=authority)).status == 200
        assert provider["refresh_count"] == 1
        async with maker() as session:
            stored = await session.get(OidcSession, oidc.digest(cookie.value))
            assert stored.max_expires_at == ceiling
            assert oidc._cipher().decrypt(stored.refresh_token_encrypted.encode()).decode() == "rotated-refresh-1"
            stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        provider["refresh_reject"] = True
        assert (await browser.get("/api/protected", headers=authority)).status == 401
        provider["refresh_reject"] = False
        assert (await browser.get("/api/protected", headers=authority)).status == 200
        assert provider["refresh_count"] == 2
        async with maker() as session:
            stored = await session.get(OidcSession, oidc.digest(cookie.value))
            stored.max_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        assert (await browser.get("/api/protected", headers=authority)).status == 401
        async with maker() as session:
            stored = await session.get(OidcSession, oidc.digest(cookie.value))
            stored.max_expires_at = ceiling
            await session.commit()
        provider["down"] = True
        assert (await browser.get("/api/protected", headers=authority)).status == 401
        provider["down"], provider["active"] = False, False
        assert (await browser.get("/api/protected", headers=authority)).status == 401
        provider["active"] = True
        provider["down"] = True
        # Cross-origin logout remains rejected, even while the issuer is down.
        assert (await browser.post("/api/web/session/logout", headers={**authority, "Origin": "https://attacker.example"})).status == 403
        assert (await browser.post("/api/web/session/logout", headers=authority)).status == 403
        assert (await browser.post("/api/web/session/logout", headers={"Origin": "https://attacker.example"})).status == 403
        monkeypatch.setattr(config, "OIDC_END_SESSION_ENDPOINT", issuer + "/logout")
        monkeypatch.setattr(config, "OIDC_POST_LOGOUT_REDIRECT_URI", "https://helpdesk.example/app")
        local_logout = await browser.post("/api/web/session/oidc/logout", headers={**authority, "Origin": str(browser.make_url("/")).rstrip("/")}, allow_redirects=False)
        assert local_logout.status == 303
        assert "Max-Age=0" in local_logout.headers["Set-Cookie"]
        assert logout_audits[-1]["actor_id"] == login
        assert logout_audits[-1]["actor_role"] == role
        assert parse_qs(urlsplit(local_logout.headers["Location"]).query) == {"client_id": [config.OIDC_CLIENT_ID], "post_logout_redirect_uri": [config.OIDC_POST_LOGOUT_REDIRECT_URI]}
        async with maker() as session:
            assert (await session.get(UiToken, oidc.digest(cookie.value))).revoked_at is not None
        assert (await browser.get("/api/protected", headers=authority)).status == 401
        repeated_logout = await browser.post("/api/web/session/logout", headers={**authority, "Origin": str(browser.make_url("/")).rstrip("/")})
        assert repeated_logout.status == 200 and "Max-Age=0" in repeated_logout.headers["Set-Cookie"]
        assert logout_audits[-1]["actor_id"] is None
        expired_token = await auth.generate_ui_token(login, role, expires_hours=1)
        async with maker() as session:
            (await session.get(UiToken, oidc.digest(expired_token))).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        expired_logout = await browser.post("/api/web/session/logout", headers={"Cookie": WEB_SESSION_COOKIE_NAME + "=" + expired_token,
            "Origin": str(browser.make_url("/")).rstrip("/")}, json={"actor_id": "forged", "actor_role": "admin"})
        assert expired_logout.status == 200 and "Max-Age=0" in expired_logout.headers["Set-Cookie"]
        assert logout_audits[-1]["actor_id"] is None and logout_audits[-1]["actor_role"] is None
