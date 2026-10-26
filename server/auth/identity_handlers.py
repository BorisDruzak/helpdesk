"""Narrow integration authority and explicit administrator migration operations."""
import secrets

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import config
from app.db import get_session
from auth.identity import IdentityError, IdentityService, parse_identity
from auth.middleware import require_auth
from auth.rate_limit import check_rate_limit, client_ip


class ResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    issuer: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=255)
    ad_object_guid: str = Field(min_length=36, max_length=36)


def response(data, status=200):
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


async def read_bounded(request):
    if request.content_length is not None and request.content_length > 4096:
        raise ValueError("request_too_large")
    raw = bytearray()
    async for chunk in request.content.iter_chunked(4097):
        raw.extend(chunk)
        if len(raw) > 4096:
            raise ValueError("request_too_large")
    import json
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid_request")
    return data


async def handle_identity_resolve(request):
    expected = config.IDENTITY_RESOLVE_SERVICE_TOKEN
    supplied = request.headers.get("Authorization", "")
    if not expected or len(expected) < 32 or len(supplied) > 1024 or not secrets.compare_digest(supplied.encode(), ("Bearer " + expected).encode()):
        return response({"error": "service_authority_required"}, 401)
    if not check_rate_limit("identity_resolve", client_ip(request), limit=config.IDENTITY_RESOLVE_RATE_LIMIT_PER_MINUTE, window_seconds=60):
        return response({"error": "rate_limited"}, 429)
    if not config.OIDC_ISSUER:
        return response({"error": "identity_authority_unavailable"}, 503)
    try:
        data = ResolveInput.model_validate(await read_bounded(request))
        parse_identity(data.issuer, data.subject, data.ad_object_guid)
        if data.issuer != config.OIDC_ISSUER:
            return response({"error": "issuer_not_allowed"}, 400)
        async with get_session() as session:
            result = await IdentityService(session).resolve(data.issuer, data.subject, data.ad_object_guid)
        return response(result)
    except (ValueError, ValidationError):
        return response({"error": "invalid_identity_request"}, 400)
    except IdentityError as exc:
        return response({"error": exc.code}, exc.status)
    except Exception:
        return response({"error": "identity_authority_unavailable"}, 503)


@require_auth("admin")
async def handle_identity_admin(request):
    actor = request["auth_context"].actor_id
    action = request.match_info["action"]
    try:
        data = await read_bounded(request)
        async with get_session() as session:
            service = IdentityService(session)
            if action == "propose":
                if set(data) != {"person_id", "user_login", "issuer", "subject", "ad_object_guid"} or data["issuer"] != config.OIDC_ISSUER:
                    raise ValueError("invalid_candidate")
                candidate = await service.propose(**data, actor_id=actor)
                return response({"candidate_id": candidate.candidate_id, "state": candidate.state}, 201)
            if action == "confirm":
                if set(data) != {"candidate_id", "verification_reference"}:
                    raise ValueError("invalid_confirmation")
                binding = await service.confirm(**data, actor_id=actor)
                return response({"binding_id": binding.binding_id, "state": "confirmed"})
            if action == "revoke":
                if set(data) != {"binding_id"}:
                    raise ValueError("invalid_revocation")
                await service.revoke(**data, actor_id=actor)
                return response({"state": "revoked"})
            if action == "migrate-password":
                if set(data) != {"binding_id", "verification_reference"}:
                    raise ValueError("invalid_migration")
                await service.migrate_password(**data, actor_id=actor)
                return response({"password_login_enabled": False})
        return response({"error": "unknown_identity_action"}, 404)
    except (ValueError, TypeError):
        return response({"error": "invalid_identity_request"}, 400)
    except IdentityError as exc:
        return response({"error": exc.code}, exc.status)
    except Exception:
        return response({"error": "identity_authority_unavailable"}, 503)
