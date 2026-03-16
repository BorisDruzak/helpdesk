"""
HTTP обработчики для Playbook Engine (Этап 4 MVP, Этап 6 deferred + idempotency).
"""
from datetime import datetime, timezone
from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.playbook_repo import PlaybookRepo
from app.services.playbook_engine import start_run


def _parse_scheduled_at(value) -> "datetime | None":
    """Парсит scheduled_at (UTC ISO) или возвращает None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


async def handle_start_playbook_run(request: web.Request) -> web.Response:
    """
    POST /api/playbooks/runs

    Body: playbook_version_id (int), device_id (str) [, trigger_type, context_json,
          scheduled_at (UTC ISO), idempotency_key (str), dry_run (bool) ].
    Returns: 202 { playbook_run_id, status } при создании;
             200 при idempotency (существующий run).
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"[Playbook] Invalid JSON: {e}")
        return web.json_response(
            {"status": "error", "error": "Invalid JSON"},
            status=400,
        )
    playbook_version_id = body.get("playbook_version_id")
    device_id = body.get("device_id")
    if playbook_version_id is None or not device_id:
        return web.json_response(
            {"status": "error", "error": "playbook_version_id and device_id required"},
            status=400,
        )
    try:
        playbook_version_id = int(playbook_version_id)
    except (TypeError, ValueError):
        return web.json_response(
            {"status": "error", "error": "playbook_version_id must be integer"},
            status=400,
        )
    trigger_type = body.get("trigger_type")
    context_json = body.get("context_json")
    if context_json is not None and not isinstance(context_json, dict):
        return web.json_response(
            {"status": "error", "error": "context_json must be object"},
            status=400,
        )
    scheduled_at = _parse_scheduled_at(body.get("scheduled_at"))
    idempotency_key = body.get("idempotency_key")
    if idempotency_key is not None and not isinstance(idempotency_key, str):
        idempotency_key = None
    dry_run = body.get("dry_run") is True

    if dry_run:
        async with get_session() as session:
            repo = PlaybookRepo(session)
            version_and_steps = await repo.get_version_with_steps(playbook_version_id)
            if not version_and_steps:
                return web.json_response(
                    {"status": "error", "error": "Playbook version not found"},
                    status=404,
                )
            version, steps = version_and_steps
            return web.json_response(
                {
                    "valid": True,
                    "playbook_version_id": playbook_version_id,
                    "steps_count": len(steps),
                    "version_status": version.status,
                },
                status=200,
            )

    # Idempotency: при повторном запросе с тем же ключом возвращаем существующий run (200)
    if idempotency_key:
        async with get_session() as session:
            repo = PlaybookRepo(session)
            existing = await repo.get_run_by_idempotency_key(idempotency_key)
            if existing:
                return web.json_response(
                    {"playbook_run_id": existing.id, "status": existing.status},
                    status=200,
                )

    state = request.app["state"]
    async with get_session() as session:
        try:
            run_id, _ = await start_run(
                session=session,
                state=state,
                playbook_version_id=playbook_version_id,
                device_id=device_id,
                trigger_type=trigger_type,
                context_json=context_json,
                scheduled_at=scheduled_at,
                idempotency_key=idempotency_key,
            )
            await session.commit()
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=404,
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
            )
    now = datetime.now(timezone.utc)
    status = "pending" if scheduled_at and scheduled_at > now else "running"
    return web.json_response(
        {"playbook_run_id": run_id, "status": status},
        status=202,
    )
