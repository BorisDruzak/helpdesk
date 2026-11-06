"""Synthetic notification transport for local browser acceptance only."""
from aiohttp import web


def state(request):
    return request.app.setdefault("notification_fixture", {"notifications": [], "shown": [], "subscribed": False})


async def control(request):
    if request.method == "POST":
        request.app["notification_fixture"] = {"notifications": (await request.json()).get("notifications", []), "shown": [], "subscribed": False}
    return web.json_response(state(request))


async def notifications(request):
    return web.json_response({"status": "ok", "notifications": state(request)["notifications"]})


async def unread(request):
    return web.json_response({"status": "ok", "unread_count": sum(not row["is_read"] for row in state(request)["notifications"])})


async def read(request):
    for row in state(request)["notifications"]:
        if request.match_info.get("id") in (None, str(row["id"])):
            row["is_read"] = True
    return web.json_response({"status": "ok"})


async def push(request):
    action = request.match_info["action"]
    current = state(request)
    if action == "config":
        # Public P-256 generator point; no private key or external transport.
        return web.json_response({"status": "ok", "enabled": True, "public_key": "BGsX0fLhLEJH-Lzm5WOkQPJ3A32BLeszoPShOUXYmMKWT-NC4v4af5uO5-tKfA-eFivOM1drMV7Oy7ZAaDe_UfU"})
    if action in {"subscribe", "unsubscribe"}:
        current["subscribed"] = action == "subscribe"
    if action == "acknowledge":
        current["shown"].extend((await request.json())["notification_ids"])
    if action == "messages":
        # Preserve rows to prove the worker also deduplicates independently.
        return web.json_response({"status": "ok", "actor_id": "support", "notifications": current["notifications"] if current["subscribed"] else []})
    return web.json_response({"status": "ok", "subscribed": current["subscribed"]})


def install(app):
    app.router.add_routes([
        web.get("/__fixtures/notifications", control), web.post("/__fixtures/notifications", control),
        web.get("/api/web/notifications/unread_count", unread),
        web.post("/api/web/notifications/read_all", read),
        web.post("/api/web/notifications/{id}/read", read),
        web.get("/api/web/notifications/push/{action}", push),
        web.post("/api/web/notifications/push/{action}", push),
    ])
