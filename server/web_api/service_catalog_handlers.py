from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.service_catalog_repo import ServiceCatalogRepo
from auth.middleware import require_auth
from tickets.service_catalog_publication import ServiceCatalogPublicationService
from tickets.service_catalog_preview import ServiceCatalogPreviewError, build_requester_service_catalog_preview
from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver


def _actor(request: web.Request) -> tuple[str | None, str | None]:
    auth = request.get("auth_context") or request.get("auth")
    return (
        str(getattr(auth, "actor_id", "") or "") or None,
        str(getattr(auth, "actor_role", "") or "") or None,
    )


async def _json_payload(request: web.Request) -> dict:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog(request: web.Request) -> web.Response:
    async with get_session() as session:
        repo = ServiceCatalogRepo(session)
        services = await repo.list_services(include_retired=True)
        offerings = await repo.list_offerings()
    return web.json_response({"status": "ok", "services": services, "offerings": offerings})


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_service(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    async with get_session() as session:
        repo = ServiceCatalogRepo(session)
        service = await repo.get_service_by_code(code)
        if service is None:
            return web.json_response({"status": "error", "error": "not_found"}, status=404)
        offerings = await repo.list_offerings(service_code=code)
    return web.json_response({"status": "ok", "service": service, "offerings": offerings})


@require_auth("admin")
async def handle_web_admin_service_catalog_save_service(request: web.Request) -> web.Response:
    try:
        payload = await _json_payload(request)
        actor_id, actor_role = _actor(request)
        async with get_session() as session:
            service = await ServiceCatalogRepo(session).upsert_service_draft(
                payload,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            await session.commit()
        return web.json_response({"status": "ok", "service": service})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[service_catalog] failed to save service")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_validate_service(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    try:
        async with get_session() as session:
            result = await ServiceCatalogPublicationService(session).validate_service(code)
        return web.json_response({"status": "ok", "validation": result})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin")
async def handle_web_admin_service_catalog_publish_service(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            publication = ServiceCatalogPublicationService(session)
            validation = await publication.validate_service(code)
            if validation["blocking"]:
                return web.json_response({"status": "error", "error": "publication_blocked", "validation": validation}, status=409)
            service = await ServiceCatalogRepo(session).publish_service(code, actor_id=actor_id, actor_role=actor_role)
            await session.commit()
        return web.json_response({"status": "ok", "service": service, "validation": validation})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin")
async def handle_web_admin_service_catalog_retire_service(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            service = await ServiceCatalogRepo(session).retire_service(code, actor_id=actor_id, actor_role=actor_role)
            await session.commit()
        return web.json_response({"status": "ok", "service": service})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_service_offerings(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    async with get_session() as session:
        offerings = await ServiceCatalogRepo(session).list_offerings(service_code=code)
    return web.json_response({"status": "ok", "offerings": offerings})


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_offering(request: web.Request) -> web.Response:
    full_code = str(request.match_info.get("full_code") or "")
    async with get_session() as session:
        offering = await ServiceCatalogRepo(session).get_offering_by_full_code(full_code)
    if offering is None:
        return web.json_response({"status": "error", "error": "not_found"}, status=404)
    return web.json_response({"status": "ok", "offering": offering})


@require_auth("admin")
async def handle_web_admin_service_catalog_save_offering(request: web.Request) -> web.Response:
    try:
        payload = await _json_payload(request)
        actor_id, actor_role = _actor(request)
        async with get_session() as session:
            offering = await ServiceCatalogRepo(session).upsert_offering_draft(
                payload,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            await session.commit()
        return web.json_response({"status": "ok", "offering": offering})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[service_catalog] failed to save offering")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_validate_offering(request: web.Request) -> web.Response:
    full_code = str(request.match_info.get("full_code") or "")
    try:
        async with get_session() as session:
            result = await ServiceCatalogPublicationService(session).validate_offering(full_code)
        return web.json_response({"status": "ok", "validation": result})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin")
async def handle_web_admin_service_catalog_publish_offering(request: web.Request) -> web.Response:
    full_code = str(request.match_info.get("full_code") or "")
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            publication = ServiceCatalogPublicationService(session)
            validation = await publication.validate_offering(full_code)
            if validation["blocking"]:
                return web.json_response({"status": "error", "error": "publication_blocked", "validation": validation}, status=409)
            offering = await ServiceCatalogRepo(session).publish_offering(full_code, actor_id=actor_id, actor_role=actor_role)
            await session.commit()
        return web.json_response({"status": "ok", "offering": offering, "validation": validation})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin")
async def handle_web_admin_service_catalog_retire_offering(request: web.Request) -> web.Response:
    full_code = str(request.match_info.get("full_code") or "")
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            offering = await ServiceCatalogRepo(session).retire_offering(full_code, actor_id=actor_id, actor_role=actor_role)
            await session.commit()
        return web.json_response({"status": "ok", "offering": offering})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin", "auditor")
async def handle_web_admin_service_catalog_simulate(request: web.Request) -> web.Response:
    try:
        from tickets.policy_health_service import PolicyHealthService

        payload = await _json_payload(request)
        async with get_session() as session:
            result = await PolicyHealthService(session).simulate(payload)
        return web.json_response(result)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[service_catalog] failed to simulate")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_service_catalog_current(request: web.Request) -> web.Response:
    async with get_session() as session:
        payload = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()
    return web.json_response({"status": "ok", **payload})


async def handle_service_catalog_preview(request: web.Request) -> web.Response:
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            preview = await build_requester_service_catalog_preview(session, payload)
        return web.json_response({"status": "ok", **preview})
    except ServiceCatalogPreviewError as exc:
        return web.json_response(
            {"status": "error", "error": "validation_error", "details": exc.details},
            status=400,
        )
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": "validation_error", "details": str(exc)},
            status=400,
        )
    except Exception:
        logger.exception("[service_catalog] requester preview failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_service_catalog_service(request: web.Request) -> web.Response:
    code = str(request.match_info.get("service_code") or "")
    async with get_session() as session:
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()
    for service in catalog.get("services", []):
        if service.get("service_code") == code:
            return web.json_response({"status": "ok", "service": service})
    return web.json_response({"status": "error", "error": "not_found"}, status=404)


async def handle_service_catalog_offering(request: web.Request) -> web.Response:
    full_code = str(request.match_info.get("full_code") or "")
    async with get_session() as session:
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()
    for service in catalog.get("services", []):
        for offering in service.get("offerings", []):
            if offering.get("full_code") == full_code:
                return web.json_response({"status": "ok", "offering": offering})
    return web.json_response({"status": "error", "error": "not_found"}, status=404)
