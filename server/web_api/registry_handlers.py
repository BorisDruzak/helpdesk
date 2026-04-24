from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from auth.middleware import require_auth
from registry.service import RegistryIngestionService, RegistrySnapshotService


def _success(data: dict) -> web.Response:
    return web.json_response({"status": "success", "data": data})


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
