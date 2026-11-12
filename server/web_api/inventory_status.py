"""Read-only server-to-server status for explicitly linked inventory employees."""

import asyncio
import hashlib
import hmac
import os
import re
from uuid import UUID

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, func, select

from app.db import get_session
from app.db.models import RegistryInventoryLink, RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.ui_users_repo import normalize_user_login
from registry.inventory_binding_refresh import active_inventory_account, verified_inventory_alias

STATUS_PATH = "/api/internal/inventory/v1/helpdesk-account-status"
MAX_REQUEST_BYTES = 16 * 1024


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_person_ids: list[UUID] = Field(min_length=1, max_length=250)


def _reply(payload: dict, *, status: int = 200) -> web.Response:
    return web.json_response(payload, status=status, headers={"Cache-Control": "no-store"})


async def read_helpdesk_account_status(request: web.Request) -> web.Response:
    expected = os.getenv("HELPDESK_INVENTORY_STATUS_TOKEN_HASH", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        return _reply({"error": "Inventory status service unavailable"}, status=503)
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if (scheme.lower() != "bearer" or not 32 <= len(token) <= 4096
            or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected)):
        return _reply({"error": "Inventory status credential required"}, status=401)

    try:
        raw = bytearray()
        async with asyncio.timeout(3):
            async for chunk in request.content.iter_chunked(4096):
                raw.extend(chunk)
                if len(raw) > MAX_REQUEST_BYTES:
                    return _reply({"error": "Inventory status request too large"}, status=413)
        ids = StatusRequest.model_validate_json(raw).inventory_person_ids
    except (ValidationError, TimeoutError):
        return _reply({"error": "Invalid inventory employee IDs"}, status=400)
    if len(ids) != len(set(ids)):
        return _reply({"error": "Duplicate inventory employee IDs"}, status=400)

    link, person, account, alias = RegistryInventoryLink, RegistryPerson, UiUser, RegistryPersonIdentity
    async with get_session() as session:
        rows = await session.execute(
            select(link, person, account, alias)
            .join(person, person.person_id == link.person_id)
            .join(account, account.user_login == link.user_login)
            .join(alias, and_(alias.person_id == person.person_id, alias.provider == "ui_login",
                             alias.normalized_identifier == func.lower(func.trim(account.user_login)),
                             alias.verified.is_(True)))
            .where(link.inventory_person_id.in_([str(value) for value in ids]))
        )
        linked = [
            {"inventory_person_id": row.inventory_person_id, "person_id": row.person_id, "user_login": user.user_login}
            for row, registry_person, user, identity in rows
            if active_inventory_account(registry_person, user)
            and verified_inventory_alias(identity, normalize_user_login(user.user_login))
        ]
    return _reply({"linked": linked})
