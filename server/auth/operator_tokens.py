"""Expiring operator grants for a closed subset of Helpdesk HTTP routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.ui_users_repo import UiUsersRepo
from auth.context import AuthContext, AuthType
from auth.service import AuthService


TOKEN_PREFIX = "hdo_"
TOKEN_PATTERN = re.compile(r"hdo_[A-Za-z0-9_-]{43}", re.ASCII)
ROUTE_SCOPES = {
    ("GET", "operator_ticket_detail"): "tickets.read",
    ("GET", "operator_ticket_events"): "tickets.read",
    ("GET", "operator_ticket_attachment"): "tickets.read",
    ("POST", "operator_ticket_reply"): "tickets.reply",
    ("POST", "operator_ticket_status"): "tickets.transition",
    ("GET", "operator_ticket_tool_catalog"): "diagnostics.read",
    ("GET", "operator_ticket_tool_result"): "diagnostics.read",
    ("POST", "operator_ticket_tool_run"): "diagnostics.run",
    ("POST", "operator_ticket_device"): "diagnostics.run",
}
SCOPES = frozenset(ROUTE_SCOPES.values())
MAX_GRANTS_BYTES = 64 * 1024


def _grant_for_token(token: str, *, now: datetime) -> dict | None:
    path = os.environ.get("HELPDESK_OPERATOR_GRANTS_FILE")
    if not path or not TOKEN_PATTERN.fullmatch(token):
        return None
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_GRANTS_BYTES + 1)
        if len(raw) > MAX_GRANTS_BYTES:
            raise ValueError("operator grants file too large")
        grants = json.loads(raw)
        if not isinstance(grants, list):
            raise ValueError("operator grants must be a list")
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        matched = None
        for grant in grants:
            if not isinstance(grant, dict):
                raise ValueError("invalid operator grant")
            token_hash = grant.get("sha256")
            if not isinstance(token_hash, str) or re.fullmatch(r"[a-f0-9]{64}", token_hash) is None:
                raise ValueError("invalid operator grant hash")
            if not hmac.compare_digest(token_hash, digest):
                continue
            if matched is not None:
                raise ValueError("duplicate operator grant")
            matched = grant
        if matched is None:
            return None
        expires_at = datetime.fromisoformat(matched["expires_at"])
        scopes = matched["scopes"]
        actor = matched["operator"]
        if expires_at.tzinfo is None or expires_at <= now:
            return None
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 255:
            raise ValueError("invalid operator identity")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(item, str) or item not in SCOPES for item in scopes):
            raise ValueError("invalid operator scopes")
        return matched
    except (OSError, ValueError, TypeError, KeyError):
        logger.warning("[OperatorAuth] Operator grants could not be validated")
        return None


async def authenticate_operator(request: web.Request, token: str) -> AuthContext | None:
    scheme, _, presented = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or presented.strip() != token:
        return None
    required_scope = ROUTE_SCOPES.get((request.method, request.match_info.route.name))
    if required_scope is None:
        return None
    grant = _grant_for_token(token, now=datetime.now(timezone.utc))
    if grant is None or required_scope not in grant["scopes"]:
        return None

    async with get_session() as session:
        user = await UiUsersRepo(session).get_by_login(grant["operator"])
        if user is None or not user.is_active or user.actor_role not in {"admin", "support"}:
            return None
        if await AuthService._registry_person_block_for_ui_user(session, user.user_login):
            return None
        return AuthContext(
            actor_id=user.user_login, actor_role=user.actor_role, auth_type=AuthType.OPERATOR_TOKEN,
            operator_scopes=frozenset(grant["scopes"]),
        )
