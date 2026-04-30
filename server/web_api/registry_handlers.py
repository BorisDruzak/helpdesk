from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from auth.middleware import require_auth
from registry.service import RegistryIngestionService, RegistrySnapshotService


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
        snapshot = await RegistrySnapshotService(session).build_snapshot()

    assets = snapshot.get("assets") if isinstance(snapshot.get("assets"), list) else []
    people = snapshot.get("people") if isinstance(snapshot.get("people"), list) else []
    locations = snapshot.get("locations") if isinstance(snapshot.get("locations"), list) else []
    departments = snapshot.get("departments") if isinstance(snapshot.get("departments"), list) else []
    services = snapshot.get("services") if isinstance(snapshot.get("services"), list) else []

    return _success(
        {
            "devices": _compact_options(
                [
                    _option(
                        item.get("device_id") or item.get("asset_id") or item.get("id"),
                        item.get("hostname") or item.get("name") or item.get("device_id") or item.get("asset_id"),
                    )
                    for item in assets
                    if isinstance(item, dict)
                ]
            ),
            "users": _compact_options(
                [
                    _option(
                        item.get("person_id") or item.get("id"),
                        item.get("display_name") or item.get("full_name") or item.get("person_id"),
                    )
                    for item in people
                    if isinstance(item, dict)
                ]
            ),
            "locations": _compact_options(
                [
                    _option(
                        item.get("location_id") or item.get("id"),
                        " / ".join(
                            str(part).strip()
                            for part in (item.get("building"), item.get("room"))
                            if str(part or "").strip()
                        )
                        or item.get("display_name")
                        or item.get("location_id"),
                    )
                    for item in locations
                    if isinstance(item, dict)
                ]
            ),
            "departments": _compact_options(
                [
                    _option(item.get("department_id") or item.get("id"), item.get("name") or item.get("code"))
                    for item in departments
                    if isinstance(item, dict)
                ]
            ),
            "services": _compact_options(
                [
                    _option(item.get("service_id") or item.get("id"), item.get("name") or item.get("code"))
                    for item in services
                    if isinstance(item, dict)
                ]
            ),
        }
    )


@require_auth("admin", "support", "user", "agent")
async def handle_registry_profile_upsert(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    data = await request.json()
    device_id = str(data.get("device_id") or auth_context.actor_id or "").strip() or None
    requester_id = str(data.get("requester_id") or auth_context.actor_id or "").strip() or None
    display_name = str(data.get("display_name") or "").strip() or None
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}

    async with get_session() as session:
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
        }
    )
