"""Authenticated same-origin Web Push opt-in and notification retrieval."""
from aiohttp import web

from app.db import get_session
from app.repos.web_push_repo import WebPushRepo
from tickets.browser_notifications import notification_to_dict
from tickets.web_push import load_push_config, validate_endpoint


def _actor(request):
    actor = request.get("auth_context")
    if actor is None or actor.actor_role not in {"user", "support", "admin", "auditor"} or actor.ticket_scope:
        raise web.HTTPForbidden()
    return actor


def _ok(**payload):
    response = web.json_response({"status": "ok", **payload})
    response.headers["Cache-Control"] = "no-store"
    return response


async def _body(request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError()
        validate_endpoint(body.get("endpoint"))
        return body
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text='{"status":"error","error":"Некорректная подписка браузера."}', content_type="application/json") from None


async def handle_push_config(request):
    _actor(request)
    config = load_push_config()
    return _ok(enabled=config is not None, public_key=config.public_key if config else None)


async def handle_push_subscribe(request):
    actor = _actor(request)
    config = load_push_config()
    if config is None:
        return web.json_response({"status": "error", "error": "Браузерные уведомления ещё не настроены на сервере."}, status=503)
    data = await _body(request)
    async with get_session() as session:
        try:
            await WebPushRepo(session).subscribe(data["endpoint"], actor.actor_id, config.public_key)
        except ValueError:
            raise web.HTTPConflict(text='{"status":"error","error":"Достигнут лимит подключённых браузеров."}', content_type="application/json") from None
        await session.commit()
    return _ok(subscribed=True)


async def handle_push_status(request):
    actor = _actor(request)
    data = await _body(request)
    async with get_session() as session:
        subscription = await WebPushRepo(session).get(data["endpoint"], actor.actor_id)
    config = load_push_config()
    return _ok(subscribed=bool(subscription and config and subscription.vapid_public_key == config.public_key))


async def handle_push_unsubscribe(request):
    actor = _actor(request)
    data = await _body(request)
    async with get_session() as session:
        await WebPushRepo(session).unsubscribe(data["endpoint"], actor.actor_id)
        await session.commit()
    return _ok(subscribed=False)


async def handle_push_messages(request):
    actor = _actor(request)
    data = await _body(request)
    async with get_session() as session:
        rows = await WebPushRepo(session).pending(data["endpoint"], actor.actor_id, auth_context=actor)
        await session.commit()
        return _ok(actor_id=actor.actor_id, notifications=[notification_to_dict(row, requester=actor.actor_role == "user") for row in rows])


async def handle_push_acknowledge(request):
    actor = _actor(request)
    data = await _body(request)
    ids = data.get("notification_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 50 or any(type(value) is not int or value <= 0 for value in ids):
        raise web.HTTPBadRequest()
    async with get_session() as session:
        await WebPushRepo(session).acknowledge(data["endpoint"], actor.actor_id, ids)
        await session.commit()
    return _ok()
