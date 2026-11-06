"""Synthetic notification transport for local browser acceptance only."""
from aiohttp import web


def state(request):
    return request.app.setdefault("notification_fixture", {"notifications": [], "shown": [], "subscribed": False})


async def control(request):
    if request.method == "POST":
        data = await request.json()
        request.app["notification_fixture"] = {"notifications": data.get("notifications", []), "shown": [], "subscribed": False, "invalid_read_response": data.get("invalid_read_response", False)}
    return web.json_response(state(request))


async def notifications(request):
    rows = state(request)["notifications"]
    if request.query.get("unread_only") == "true":
        rows = [row for row in rows if not row["is_read"]]
    return web.json_response({"status": "ok", "notifications": rows})


async def unread(request):
    return web.json_response({"status": "ok", "unread_count": sum(not row["is_read"] for row in state(request)["notifications"])})


async def read(request):
    if request.match_info.get("id") and state(request).get("invalid_read_response"):
        return web.Response(text="not-json", content_type="application/json")
    ticket = (await request.json()).get("ticket_id") if request.path.endswith("/read_ticket") else None
    updated = 0
    for row in state(request)["notifications"]:
        if request.match_info.get("id") in (None, str(row["id"])) and (ticket is None or row["ticket_id"] == ticket):
            row["is_read"] = True
            updated += 1
    return web.json_response({"status": "ok", "updated": updated})


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
        web.post("/api/web/notifications/read_ticket", read),
        web.post("/api/web/notifications/{id}/read", read),
        web.get("/api/web/notifications/push/{action}", push),
        web.post("/api/web/notifications/push/{action}", push),
    ])
