"""Authlib OIDC code/PKCE BFF. Only opaque existing UiToken authority reaches browsers."""
from datetime import datetime, timedelta, timezone
import hashlib
import math
import secrets
import ssl
import time
from urllib.parse import urlencode, urlsplit

from aiohttp import web
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.common.urls import add_params_to_uri
from authlib.oidc.core import CodeIDToken
from cryptography.fernet import Fernet
import httpx
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jws import JWSRegistry
from sqlalchemy import delete, select

import config
from app.db import get_session
from app.db.models import ConfirmedIdentityBinding, OidcFlow, OidcSession, UiToken
from auth.identity import IdentityError, IdentityService, parse_identity
from auth.middleware import WEB_SESSION_COOKIE_NAME
from auth.rate_limit import check_rate_limit, client_ip

FLOW_COOKIE = "__Host-helpdesk_oidc_flow"
FLOW_TTL = 300
SESSION_TTL = 900
SESSION_MAX_TTL = 8 * 60 * 60


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cipher():
    return Fernet(config.OIDC_TOKEN_ENCRYPTION_KEY.encode("ascii"))


def _tls_context():
    return ssl.create_default_context(cafile=config.OIDC_CA_FILE or None)


def _configured():
    if not config.OIDC_ENABLED or not config.OIDC_CLIENT_ID or not config.OIDC_CLIENT_SECRET:
        raise RuntimeError("oidc_not_configured")
    parse_identity(config.OIDC_ISSUER, "configuration", "00000000-0000-0000-0000-000000000000")
    callback = urlsplit(config.OIDC_REDIRECT_URI)
    if callback.scheme != "https" or not callback.hostname or callback.username or callback.password or callback.query or callback.fragment or callback.path != "/api/web/session/oidc/callback":
        raise RuntimeError("invalid_oidc_redirect_uri")
    if not config.WEB_SESSION_COOKIE_SECURE or not config.WEB_CSRF_SAME_ORIGIN_ENABLED:
        raise RuntimeError("oidc_requires_secure_cookie_and_csrf")
    _cipher()


def _endpoint(url):
    value, issuer = urlsplit(url), urlsplit(config.OIDC_ISSUER)
    if value.scheme != "https" or value.netloc != issuer.netloc or value.username or value.password or value.fragment:
        raise ValueError("untrusted_oidc_endpoint")
    return url


async def _json(url):
    # Bound even trusted provider responses; prohibit redirects and ambient proxy configuration.
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False, verify=_tls_context()) as client:
        async with client.stream("GET", _endpoint(url)) as result:
            result.raise_for_status()
            raw = bytearray()
            async for chunk in result.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > 1024 * 1024:
                    raise ValueError("oidc_response_too_large")
    import json
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid_oidc_metadata")
    return value


async def metadata():
    _configured()
    data = await _json(config.OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration")
    if data.get("issuer") != config.OIDC_ISSUER or "S256" not in data.get("code_challenge_methods_supported", []):
        raise ValueError("oidc_metadata_mismatch")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri", "introspection_endpoint"):
        _endpoint(data[name])
    return data


def oauth_client(**kwargs):
    return AsyncOAuth2Client(config.OIDC_CLIENT_ID, config.OIDC_CLIENT_SECRET,
        redirect_uri=config.OIDC_REDIRECT_URI, scope="openid", code_challenge_method="S256",
        token_endpoint_auth_method="client_secret_basic", timeout=8, follow_redirects=False,
        trust_env=False, verify=_tls_context(), **kwargs)


def validate_id_token(encoded, jwks, nonce, access_token):
    decoded = jwt.decode(encoded, KeySet.import_key_set(jwks), registry=JWSRegistry(algorithms=["RS256"], strict_check_header=False))
    claims = CodeIDToken(decoded.claims, decoded.header,
        options={"iss": {"essential": True, "value": config.OIDC_ISSUER},
                 "aud": {"essential": True, "value": config.OIDC_CLIENT_ID}},
        params={"nonce": nonce, "client_id": config.OIDC_CLIENT_ID, "access_token": access_token})
    claims.validate(leeway=0)
    parse_identity(claims["iss"], claims["sub"], claims.get(config.OIDC_AD_GUID_CLAIM))
    return claims


async def _introspect(meta, token, binding, sid):
    async with oauth_client() as client:
        result = await client.introspect_token(meta["introspection_endpoint"], token=token, token_type_hint="access_token")
        result.raise_for_status()
        if len(result.content) > 1024 * 1024:
            return False
        value = result.json()
    if not isinstance(value, dict):
        return False
    expiry = value.get("exp")
    return bool(value.get("active") is True and value.get("sub") == binding.subject
        and value.get("iss") == binding.issuer and value.get("client_id") == config.OIDC_CLIENT_ID
        and isinstance(expiry, (int, float)) and not isinstance(expiry, bool) and math.isfinite(expiry) and expiry > time.time()
        and (not sid or value.get("sid") == sid))


async def validate_oidc_session(session, token_record, user):
    """No stale-positive cache: issuer outage/revocation denies the current operation."""
    try:
        # Serialize refresh token rotation across app workers; no refresh replay race.
        record = (await session.execute(select(OidcSession).where(OidcSession.token_hash == token_record.token_hash)
            .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not record or record.max_expires_at <= now:
            return False
        binding = await session.get(ConfirmedIdentityBinding, record.binding_id)
        if not binding or binding.user_login != user.user_login or binding.issuer != config.OIDC_ISSUER:
            return False
        await IdentityService(session)._active(binding)
        meta = await metadata()
        if record.expires_at <= now + timedelta(seconds=30):
            if not record.refresh_token_encrypted:
                return False
            refresh = _cipher().decrypt(record.refresh_token_encrypted.encode()).decode()
            async with oauth_client() as client:
                renewed = await client.refresh_token(meta["token_endpoint"], refresh_token=refresh)
            claims = validate_id_token(renewed["id_token"], await _json(meta["jwks_uri"]), record.nonce, renewed["access_token"])
            if (claims["iss"], claims["sub"], claims[config.OIDC_AD_GUID_CLAIM]) != (binding.issuer, binding.subject, binding.ad_object_guid):
                return False
            if claims.get("sid") != record.upstream_sid:
                return False
            next_expiry = min(float(claims["exp"]), float(renewed["expires_at"]), record.max_expires_at.timestamp())
            if not math.isfinite(next_expiry) or next_expiry <= time.time():
                return False
            # Rotation replaces the only server-side copy; retain an unrotated token
            # only when the provider's standard response intentionally omits it.
            record.refresh_token_encrypted = _cipher().encrypt(renewed.get("refresh_token", refresh).encode()).decode()
            record.upstream_token_encrypted = _cipher().encrypt(renewed["access_token"].encode()).decode()
            record.expires_at = datetime.fromtimestamp(next_expiry, timezone.utc)
            record.acr = claims.get("acr")
            await session.flush()
        upstream = _cipher().decrypt(record.upstream_token_encrypted.encode()).decode()
        return await _introspect(meta, upstream, binding, record.upstream_sid)
    except Exception:
        # Provider messages may include credentials; never interpolate exceptions.
        return False


def _error(code, status, *, request=None):
    if request is not None and "text/html" in request.headers.get("Accept", "").lower():
        # Browser navigation needs a document. Only local constants may enter
        # this fixed URL; provider messages and return targets never do.
        browser_code = {
            "identity_unknown": "identity_unlinked",
            "identity_unconfirmed": "identity_unlinked",
            "identity_conflict": "identity_unlinked",
            "verified_ui_login_required": "identity_unlinked",
            "identity_inactive": "identity_unavailable",
            "identity_revoked": "identity_unavailable",
            "rate_limited": "rate_limited",
            "oidc_disabled": "oidc_disabled",
            "oidc_unavailable": "oidc_unavailable",
        }.get(code, "oidc_authentication_failed")
        response = web.HTTPFound("/app/login?" + urlencode({"sso_error": browser_code}),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.del_cookie(FLOW_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
        return response
    return web.json_response({"error": code}, status=status, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


async def handle_oidc_login(request):
    if not config.OIDC_ENABLED:
        return _error("oidc_disabled", 404, request=request)
    if not check_rate_limit("oidc_login", client_ip(request), limit=10, window_seconds=60):
        return _error("rate_limited", 429, request=request)
    try:
        meta = await metadata()
        nonce, verifier, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        async with oauth_client() as client:
            options = {"nonce": nonce, "response_mode": "query"}
            url, state = client.create_authorization_url(meta["authorization_endpoint"], code_verifier=verifier, **options)
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            await session.execute(delete(OidcFlow).where(OidcFlow.expires_at <= now))
            session.add(OidcFlow(state_hash=digest(state), browser_hash=digest(browser), nonce=nonce,
                verifier_encrypted=_cipher().encrypt(verifier.encode()).decode(), expires_at=now + timedelta(seconds=FLOW_TTL)))
            await session.commit()
        response = web.HTTPFound(url, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.set_cookie(FLOW_COOKIE, browser, secure=True, httponly=True, samesite="Lax", path="/", max_age=FLOW_TTL)
        return response
    except Exception:
        return _error("oidc_unavailable", 503, request=request)


async def handle_oidc_callback(request):
    if not config.OIDC_ENABLED:
        return _error("oidc_disabled", 404, request=request)
    if not check_rate_limit("oidc_callback", client_ip(request), limit=20, window_seconds=60):
        return _error("rate_limited", 429, request=request)
    # Reject duplicated/malformed parameters before any provider request.
    if any(len(request.query.getall(k, [])) != 1 for k in ("state", "code")) or request.query.get("error"):
        return _error("invalid_oidc_callback", 400, request=request)
    state, code, browser = request.query["state"], request.query["code"], request.cookies.get(FLOW_COOKIE, "")
    if not state or len(state) > 256 or not code or len(code) > 4096 or not browser or len(browser) > 256:
        return _error("invalid_oidc_callback", 400, request=request)
    try:
        _configured()
        async with get_session() as session:
            # DELETE RETURNING consumes the flow atomically across workers before token exchange.
            flow = (await session.execute(delete(OidcFlow).where(OidcFlow.state_hash == digest(state),
                OidcFlow.browser_hash == digest(browser), OidcFlow.expires_at > datetime.now(timezone.utc)).returning(OidcFlow))).scalar_one_or_none()
            await session.commit()
        if flow is None:
            return _error("invalid_or_replayed_oidc_state", 400, request=request)
        meta = await metadata()
        async with oauth_client(state=state) as client:
            token = await client.fetch_token(meta["token_endpoint"], authorization_response=config.OIDC_REDIRECT_URI + "?" + urlencode({"state": state, "code": code}),
                code_verifier=_cipher().decrypt(flow.verifier_encrypted.encode()).decode())
        access_token = token["access_token"]
        claims = validate_id_token(token["id_token"], await _json(meta["jwks_uri"]), flow.nonce, access_token)
        expires_at = min(float(claims["exp"]), float(token["expires_at"]), time.time() + SESSION_TTL)
        if not math.isfinite(expires_at) or expires_at <= time.time():
            return _error("oidc_token_expired", 401, request=request)
        async with get_session() as session:
            service = IdentityService(session)
            binding = await service.resolve_binding(claims["iss"], claims["sub"], claims[config.OIDC_AD_GUID_CLAIM])
            # Capture existing authority for issuance; every subsequent operation rechecks it.
            _, user = await service._active(binding)
            acr = claims.get("acr")
            sid = claims.get("sid")
            if sid is not None and (not isinstance(sid, str) or len(sid) > 255):
                return _error("invalid_oidc_sid", 401, request=request)
            if not await _introspect(meta, access_token, binding, sid):
                return _error("oidc_session_inactive", 401, request=request)
            # Persist both records in one transaction: bypass every dev/memory fallback.
            raw = secrets.token_hex(32)
            expiry = datetime.fromtimestamp(expires_at, timezone.utc)
            max_expiry = datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_TTL) if token.get("refresh_token") else expiry
            session.add(UiToken(token_hash=digest(raw), token_prefix=raw[:8], user_login=user.user_login,
                actor_role=user.actor_role, auth_method="oidc", expires_at=max_expiry))
            await session.flush()
            session.add(OidcSession(token_hash=digest(raw), binding_id=binding.binding_id, upstream_sid=sid,
                upstream_token_encrypted=_cipher().encrypt(access_token.encode()).decode(),
                refresh_token_encrypted=_cipher().encrypt(token["refresh_token"].encode()).decode() if token.get("refresh_token") else None,
                nonce=flow.nonce, expires_at=expiry, max_expires_at=max_expiry, acr=acr))
            service._audit(binding, "sso_login_succeeded", user.user_login)
            await session.commit()
        response = web.HTTPFound("/app", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.set_cookie(WEB_SESSION_COOKIE_NAME, raw, secure=True, httponly=True, samesite="Lax", path="/", max_age=max(1, int(max_expiry.timestamp() - time.time())))
        response.del_cookie(FLOW_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
        return response
    except IdentityError as exc:
        return _error(exc.code, exc.status, request=request)
    except Exception:
        return _error("oidc_authentication_failed", 503, request=request)


async def handle_oidc_logout(request):
    """Always finish local logout before an optional fixed provider logout redirect."""
    from web_api.session_handlers import handle_web_session_logout
    response = await handle_web_session_logout(request)
    if "text/html" in request.headers.get("Accept", "").lower():
        # Native browser POSTs need a document after local logout even when RP
        # logout is absent or rejected. Never accept a request-supplied target.
        response.set_status(303)
        response.headers["Location"] = "/app/login"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    if not config.OIDC_ENABLED or not config.OIDC_END_SESSION_ENDPOINT or not config.OIDC_POST_LOGOUT_REDIRECT_URI:
        return response
    try:
        endpoint = _endpoint(config.OIDC_END_SESSION_ENDPOINT)
        target, callback = urlsplit(config.OIDC_POST_LOGOUT_REDIRECT_URI), urlsplit(config.OIDC_REDIRECT_URI)
        if target.scheme != "https" or target.netloc != callback.netloc or target.username or target.password or target.query or target.fragment:
            return response
        # Client ID + exact registered redirect avoid putting any ID/access token
        # in a browser URL. The provider may display its own logout confirmation.
        response.set_status(303)
        response.headers["Location"] = add_params_to_uri(endpoint, [
            ("client_id", config.OIDC_CLIENT_ID), ("post_logout_redirect_uri", config.OIDC_POST_LOGOUT_REDIRECT_URI)])
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    except Exception:
        pass  # Fixed-provider configuration must never prevent local credential deletion.
    return response
