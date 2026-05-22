from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.db.models import Device
from auth.middleware import require_auth
from app.repos.registry_repo import RegistryRepo
from registry.registration_service import RegistrationConflictError, RegistrationService, RegistrationValidationError
from registry.service import RegistryIngestionService, RegistrySnapshotService

import uuid


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _option(value: object, label: object) -> dict[str, str]:
    return {"value": str(value or "").strip(), "label": str(label or value or "").strip()}


def _compact_options(items: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        value = str(item.get("value") or "").strip()
        label = str(item.get("label") or value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append({"value": value, "label": label})
    return result


def _validate_uuid_device_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except ValueError as exc:
        raise RegistrationValidationError("device_id must be a valid UUID") from exc


async def _device_exists(session, device_id: str) -> bool:
    return await session.get(Device, device_id) is not None


def _forbidden(message: str = "forbidden") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": "FORBIDDEN"}, status=403)


async def _resolve_submit_device_id(request: web.Request, data: dict, *, legacy: bool = False) -> str | web.Response:
    auth_context = request["auth_context"]
    body_device_id = str(data.get("device_id") or "").strip()
    role = auth_context.actor_role
    if role == "user":
        return _forbidden("user cannot submit registration profile for arbitrary device")
    if role == "agent":
        actor_device_id = _validate_uuid_device_id(auth_context.actor_id)
        if not actor_device_id:
            return web.json_response({"status": "error", "error": "agent device_id required", "error_code": "VALIDATION_ERROR"}, status=400)
        if body_device_id and _validate_uuid_device_id(body_device_id) != actor_device_id:
            return _forbidden("forbidden device_id")
        return actor_device_id
    if role in {"admin", "support"}:
        device_id = _validate_uuid_device_id(body_device_id)
        if not device_id:
            return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
        return device_id
    return _forbidden()


@require_auth("admin")
async def handle_web_admin_registry(_request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            payload = await RegistrySnapshotService(session).build_snapshot()
    except Exception as exc:
        logger.warning(f"[registry] failed to build admin registry snapshot: {exc}")
        payload = {
            "summary": {
                "assets_count": 0,
                "people_count": 0,
                "locations_count": 0,
                "services_count": 0,
                "vendors_count": 0,
                "data_quality_issue_count": 0,
                "suggestions_count": 0,
            },
            "assets": [],
            "people": [],
            "locations": [],
            "departments": [],
            "services": [],
            "vendors": [],
            "data_quality": [],
            "suggestions": [],
        }
    return _success(payload)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_options(_request: web.Request) -> web.Response:
    async with get_session() as session:
        repo = RegistryRepo(session)
        assets = await repo.list_assets(limit=500)
        people = await repo.list_people(limit=500)
        locations = await repo.list_locations(limit=500)
        departments = await repo.list_departments()
        services = await repo.list_services()

    return _success(
        {
            "devices": _compact_options(
                [
                    _option(
                        asset.device_id or asset.asset_id,
                        asset.hostname or asset.name or asset.device_id or asset.asset_id,
                    )
                    for asset in assets
                ]
            ),
            "users": _compact_options(
                [
                    _option(
                        person.person_id,
                        person.display_name or person.full_name or person.person_id,
                    )
                    for person in people
                ]
            ),
            "locations": _compact_options(
                [
                    _option(
                        location.location_id,
                        " / ".join(
                            str(part).strip()
                            for part in (location.building, location.room)
                            if str(part or "").strip()
                        )
                        or location.display_name
                        or location.location_id,
                    )
                    for location in locations
                ]
            ),
            "departments": _compact_options(
                [
                    _option(department.department_id, department.name or department.code)
                    for department in departments
                ]
            ),
            "services": _compact_options(
                [
                    _option(service.service_id, service.name or service.code)
                    for service in services
                ]
            ),
        }
    )


@require_auth("admin", "support", "agent")
async def handle_registry_profile_upsert(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json()
    try:
        resolved_device_id = await _resolve_submit_device_id(request, data, legacy=True)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    requester_id = str(data.get("requester_id") or auth_context.actor_id or "").strip() or None
    display_name = str(data.get("display_name") or "").strip() or None
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}

    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        service = RegistryIngestionService(session)
        result = await service.ingest_requester_profile(
            device_id=device_id,
            requester_id=requester_id,
            display_name=display_name,
            profile=profile,
        )
        repo = service.repo
        person = await repo.get_person(result.person_id)
        location = await repo.get_location(result.location_id)
        asset = await repo.get_asset(result.asset_id)
        await session.commit()

    return _success(
        {
            "person": {
                "person_id": person.person_id if person else None,
                "display_name": person.display_name if person else None,
                "status": person.status if person else None,
            },
            "location": {
                "location_id": location.location_id if location else None,
                "building": location.building if location else None,
                "room": location.room if location else None,
                "status": location.status if location else None,
            },
            "asset": {
                "asset_id": asset.asset_id if asset else None,
                "device_id": asset.device_id if asset else None,
                "name": asset.name if asset else None,
            },
            "registration": result.registration,
        }
    )


@require_auth("admin", "support", "agent")
async def handle_registry_agent_profile(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json()
    try:
        resolved_device_id = await _resolve_submit_device_id(request, data)
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    if isinstance(resolved_device_id, web.Response):
        return resolved_device_id
    device_id = resolved_device_id
    requester_id = str(data.get("requester_id") or auth_context.actor_id or "").strip() or None
    display_name = str(data.get("display_name") or "").strip() or None
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    if data.get("user_confirmed") is not None:
        profile = {**profile, "user_confirmed": bool(data.get("user_confirmed"))}
    try:
        async with get_session() as session:
            if not await _device_exists(session, device_id):
                return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
            result = await RegistrationService(session).submit_agent_profile_claim(
                device_id=device_id,
                requester_id=requester_id,
                display_name=display_name,
                profile=profile,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
            )
            await session.commit()
    except (ValueError, RegistrationValidationError) as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(result)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_agent_registration_status(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    device_id = str(request.query.get("device_id") or auth_context.actor_id or "").strip()
    if auth_context.actor_role == "agent" and device_id != auth_context.actor_id:
        return web.json_response({"status": "error", "error": "forbidden device_id", "error_code": "FORBIDDEN"}, status=403)
    if auth_context.actor_role == "user":
        return web.json_response({"status": "error", "error": "forbidden device_id", "error_code": "FORBIDDEN"}, status=403)
    try:
        device_id = _validate_uuid_device_id(device_id) or ""
    except RegistrationValidationError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        if not await _device_exists(session, device_id):
            return web.json_response({"status": "error", "error": "device not found", "error_code": "DEVICE_NOT_FOUND"}, status=404)
        payload = await RegistrationService(session).get_device_registration_status(device_id)
    return _success(payload)


@require_auth("admin", "support", "user", "agent")
async def handle_registry_agent_claim_confirm(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    async with get_session() as session:
        service = RegistrationService(session)
        claim = await service.repo.get_claim(claim_id)
        if claim is None:
            return web.json_response({"status": "error", "error": "claim not found", "error_code": "NOT_FOUND"}, status=404)
        if not await service.can_confirm_claim_for_actor(claim, auth_context):
            return web.json_response({"status": "error", "error": "forbidden claim", "error_code": "FORBIDDEN"}, status=403)
        payload = await service.confirm_claim_by_user(claim_id, actor_id=auth_context.actor_id)
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_registrations(request: web.Request) -> web.Response:
    status = str(request.query.get("status") or "").strip() or None
    device_id = str(request.query.get("device_id") or "").strip() or None
    person_id = str(request.query.get("person_id") or "").strip() or None
    try:
        limit = int(request.query.get("limit") or "100")
    except ValueError:
        limit = 100
    async with get_session() as session:
        items = await RegistrationService(session).list_registration_claims(
            status=status,
            device_id=device_id,
            person_id=person_id,
            limit=limit,
        )
    return _success({"items": items})


@require_auth("admin")
async def handle_web_admin_registry_registration_approve(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).approve_claim(
                claim_id,
                reviewed_by=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                replace_existing=bool(data.get("replace_existing")),
                admin_override_user_confirmation=bool(data.get("admin_override_user_confirmation") or data.get("force")),
                override_reason=str(data.get("reason") or "").strip() or None,
            )
            await session.commit()
    except RegistrationConflictError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "REGISTRATION_CONFLICT"}, status=409)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_registration_reject(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    claim_id = str(request.match_info.get("claim_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    reason = str(data.get("reason") or "").strip() or "rejected"
    try:
        async with get_session() as session:
            payload = await RegistrationService(session).reject_claim(claim_id, reviewed_by=auth_context.actor_id, reason=reason)
            await session.commit()
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_binding_revoke(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    binding_id = str(request.match_info.get("binding_id") or "").strip()
    data = await request.json() if request.can_read_body else {}
    async with get_session() as session:
        payload = await RegistrationService(session).revoke_binding(
            binding_id,
            revoked_by=auth_context.actor_id,
            reason=str(data.get("reason") or "").strip() or None,
        )
        await session.commit()
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_registry_device_timeline(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or "").strip()
    async with get_session() as session:
        items = await RegistrationService(session).get_timeline(device_id)
    return _success({"device_id": device_id, "items": items})
