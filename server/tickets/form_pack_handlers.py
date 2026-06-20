"""HTTP handlers for ticket form pack registry and current catalog."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from aiohttp import web

from app.db import get_session
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    next_form_pack_version,
    pack_summary,
    requester_safe_form_pack,
    resolve_ticket_form_pack,
    validate_form_pack_schema,
)
from tickets.request_template_submission import _find_registry_form_schema, _registry_pack_from_template

logger = logging.getLogger(__name__)


def _json_ok(**payload: Any) -> web.Response:
    return web.json_response({"status": "ok", **payload})


def _json_error(error: str, *, status: int = 400, **payload: Any) -> web.Response:
    return web.json_response({"status": "error", "error": error, **payload}, status=status)


def _auth(request: web.Request):
    auth_context = request.get("auth_context")
    if not auth_context:
        raise web.HTTPUnauthorized()
    return auth_context


def _admin_only(request: web.Request):
    auth_context = _auth(request)
    if auth_context.actor_role != "admin":
        raise web.HTTPForbidden(text='{"status":"error","error":"forbidden"}', content_type="application/json")
    return auth_context


async def _merge_registry_requester_forms(session, pack: dict[str, Any]) -> dict[str, Any]:
    if str(pack.get("pack_key") or "") != DEFAULT_TICKET_FORM_PACK_KEY:
        return pack
    result = deepcopy(pack)
    forms = list(result.get("forms") or [])
    seen_keys = {str(form.get("key") or "") for form in forms if isinstance(form, dict)}
    seen_templates = {str(form.get("request_template_key") or form.get("key") or "") for form in forms if isinstance(form, dict)}
    policy_repo = HelpdeskPolicyRepo(session)
    schemas = await policy_repo.list_form_schemas(include_inactive=False)
    added = 0
    for template in await policy_repo.list_request_templates(include_inactive=False):
        template_code = str(template.get("template_code") or "").strip()
        if not template_code or template_code in seen_templates or template_code in seen_keys:
            continue
        form_schema = _find_registry_form_schema(
            schemas,
            template_code=template_code,
            requested_form_key=template_code,
            preferred_schema_id=template.get("form_schema_id"),
        )
        if not form_schema:
            continue
        effective_template = await policy_repo.resolve_effective_request_template(
            template_code=template_code,
            raise_if_missing=False,
        )
        try:
            registry_pack = _registry_pack_from_template(
                effective_template=effective_template,
                form_schema=form_schema,
                form_key=template_code,
            )
        except ValueError as exc:
            logger.warning(
                "Skipping requester registry template %s while building public form pack: %s",
                template_code,
                exc,
            )
            continue
        for form in registry_pack.get("forms") or []:
            key = str(form.get("key") or "")
            request_template_key = str(form.get("request_template_key") or key)
            if not key or key in seen_keys or request_template_key in seen_templates:
                continue
            forms.append(form)
            seen_keys.add(key)
            seen_templates.add(request_template_key)
            added += 1
    if not added:
        return pack
    result["forms"] = forms
    base_version = str(result.get("version") or "current")
    result["version"] = f"{base_version}+registry.{added}"
    return result


async def handle_ticket_form_packs_list(request: web.Request) -> web.Response:
    _admin_only(request)
    pack_key = str(request.query.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        packs = await repo.list_packs(pack_key=pack_key)
        preferred = await repo.get_preferred(pack_key)
        current = await resolve_ticket_form_pack(repo, pack_key=pack_key)
        payload = []
        for pack in packs:
            schema_json = validate_form_pack_schema(pack.schema_json or {})
            payload.append(
                {
                    **pack_summary(schema_json),
                    "created_at": pack.created_at.isoformat() if pack.created_at else None,
                    "created_by": pack.created_by,
                    "notes": pack.notes,
                    "is_preferred": bool(preferred and preferred.get("version") == pack.version),
                }
            )
        if not payload and current:
            payload.append({**pack_summary(current), "created_at": None, "created_by": "builtin_default", "notes": "", "is_preferred": True})
    return _json_ok(pack_key=pack_key, current=pack_summary(current), preferred=preferred, packs=payload)


async def handle_ticket_form_pack_detail(request: web.Request) -> web.Response:
    _admin_only(request)
    pack_key = str(request.match_info.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    version = str(request.match_info.get("version") or "").strip()
    if not version:
        return _json_error("version_required", status=400)
    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        pack = await resolve_ticket_form_pack(repo, pack_key=pack_key, version=version)
    return _json_ok(pack=pack)


async def handle_ticket_form_pack_current(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None and request.path.startswith("/api/"):
        raise web.HTTPUnauthorized()
    pack_key = str(request.query.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    current_version = str(request.query.get("current_version") or "").strip() or None
    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        pack = await resolve_ticket_form_pack(repo, pack_key=pack_key)
        if request.path.startswith("/public_api/"):
            pack = await _merge_registry_requester_forms(session, pack)
            pack = requester_safe_form_pack(pack)
        has_update = bool(current_version and current_version != pack.get("version"))
    return _json_ok(pack=pack, has_update=has_update, current_version=pack.get("version"))


async def handle_ticket_form_pack_save(request: web.Request) -> web.Response:
    auth_context = _admin_only(request)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid_json", status=400)
    if not isinstance(data, dict):
        return _json_error("invalid_payload", status=400)

    raw_pack = data.get("pack") if isinstance(data.get("pack"), dict) else data
    notes = str(data.get("notes") or raw_pack.get("description") or "").strip()
    try:
        normalized_pack = validate_form_pack_schema(raw_pack, require_version=False)
    except ValueError as exc:
        return _json_error("validation_error", status=400, details=exc.args[0] if exc.args else "invalid pack")

    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        current = await resolve_ticket_form_pack(repo, pack_key=normalized_pack["pack_key"])
        next_version = next_form_pack_version(current.get("version") if isinstance(current, dict) else None)
        while await repo.get_pack(normalized_pack["pack_key"], next_version) is not None:
            next_version = next_form_pack_version(next_version)
        normalized_pack["version"] = next_version
        pack = await repo.upsert_pack(
            pack_key=normalized_pack["pack_key"],
            version=normalized_pack["version"],
            schema_json=normalized_pack,
            created_by=auth_context.actor_id,
            notes=notes,
        )
        preferred = await repo.set_preferred(
            pack_key=normalized_pack["pack_key"],
            version=normalized_pack["version"],
            updated_by=auth_context.actor_id,
        )
        await session.commit()
    return _json_ok(
        pack={**pack_summary(normalized_pack), "created_at": pack.created_at.isoformat() if pack.created_at else None, "created_by": pack.created_by, "notes": pack.notes},
        preferred=preferred,
    )


async def handle_ticket_form_pack_set_preferred(request: web.Request) -> web.Response:
    auth_context = _admin_only(request)
    pack_key = str(request.match_info.get("pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    version = str(request.match_info.get("version") or "").strip()
    if not version:
        return _json_error("version_required", status=400)
    async with get_session() as session:
        repo = TicketFormPacksRepo(session)
        pack = await repo.get_pack(pack_key, version)
        if pack is None:
            return _json_error("not_found", status=404)
        preferred = await repo.set_preferred(
            pack_key=pack_key,
            version=version,
            updated_by=auth_context.actor_id,
        )
        await session.commit()
    return _json_ok(preferred=preferred)
