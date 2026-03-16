"""
Stage 10.2: Публичное API очереди без авторизации.
Stage 10.3.1: Валидация limit/offset/days — при невалидных значениях 400 validation_error (не 500).

GET /public_api/queues
GET /public_api/queue/tickets?queue_id=...&limit=...&offset=...&ticket_code=...
GET /public_api/queue/stats?days=7&queue_id=...

Только безопасные поля. ETag/304 для tickets и stats. Limit 1..200, offset 0..10000, days 1..90.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from typing import Optional

from aiohttp import web
from loguru import logger

try:
    from app.db import get_session
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    get_session = None

from app.repos import TicketEventsRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from tickets.queue_position_service import QueuePositionService
from tickets.metrics_service import TicketMetricsService

PUBLIC_API_MAX_LIMIT = 200


def _validation_error_response(details: str) -> web.Response:
    """Единый формат 400 при невалидных query-параметрах."""
    return web.json_response(
        {"status": "error", "error": "validation_error", "details": details},
        status=400,
    )


def _parse_positive_int(value: Optional[str], default: int, min_val: int, max_val: int) -> tuple[int | None, str | None]:
    """Парсит целое в [min_val, max_val]. Возвращает (value, None) или (None, error_details)."""
    if value is None or value == "":
        return default, None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None, f"must be integer in [{min_val}, {max_val}]"
    if n < min_val or n > max_val:
        return None, f"must be in range [{min_val}, {max_val}]"
    return n, None


def _etag_from_body(body: bytes) -> str:
    return '"' + sha256(body).hexdigest()[:32] + '"'


def _parse_include_empty(request: web.Request) -> bool:
    """include_empty: default False. true|false в query."""
    raw = (request.query.get("include_empty") or "").strip().lower()
    return raw in ("1", "true", "yes")


async def handle_public_queues(request: web.Request) -> web.Response:
    """GET /public_api/queues — список очередей с open_count. Без auth.
    По умолчанию только очереди с open_count > 0. include_empty=true — все активные.
    Сортировка: open_count desc, затем queue_code asc."""
    if not DB_AVAILABLE or get_session is None:
        return web.json_response({"status": "error", "error": "service_unavailable"}, status=503)
    include_empty = _parse_include_empty(request)
    try:
        async with get_session() as session:
            admin_repo = TicketAdminConfigRepo(session)
            queues = await admin_repo.list_queues(include_inactive=False)
            items = []
            for q in queues:
                open_count = await admin_repo.count_open_tickets_in_queue(q.id)
                items.append({
                    "queue_id": q.id,
                    "queue_code": q.code,
                    "queue_name": q.name,
                    "open_count": open_count,
                })
            if not include_empty:
                items = [x for x in items if (x.get("open_count") or 0) > 0]
            items.sort(key=lambda x: (-(x.get("open_count") or 0), (x.get("queue_code") or "")))
        body = json.dumps({"queues": items}).encode("utf-8")
        return web.Response(
            body=body,
            content_type="application/json",
            headers={"Cache-Control": "public, max-age=15"},
        )
    except Exception as e:
        logger.error(f"[public_api/queues] {e}", exc_info=True)
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_public_queue_tickets(request: web.Request) -> web.Response:
    """GET /public_api/queue/tickets — тикеты очереди. ETag/304. Limit max 200."""
    if not DB_AVAILABLE or get_session is None:
        return web.json_response({"status": "error", "error": "service_unavailable"}, status=503)
    queue_id_param = request.query.get("queue_id")
    if not queue_id_param:
        return web.json_response(
            {"status": "error", "error": "validation_error", "details": "queue_id required"},
            status=400,
        )
    try:
        queue_id = int(queue_id_param)
    except (TypeError, ValueError):
        return _validation_error_response("invalid queue_id")
    limit, err = _parse_positive_int(
        request.query.get("limit"), 100, 1, PUBLIC_API_MAX_LIMIT
    )
    if err is not None:
        return _validation_error_response("limit " + err)
    offset, err = _parse_positive_int(request.query.get("offset"), 0, 0, 10000)
    if err is not None:
        return _validation_error_response("offset " + err)
    ticket_code_filter = (request.query.get("ticket_code") or "").strip() or None

    try:
        async with get_session() as session:
            ticket_repo = TicketEventsRepo(session)
            pos_svc = QueuePositionService(ticket_repo)
            rows = await pos_svc.list_queue_positions(queue_id, include_terminal=False)
            queue_code = None
            admin_repo = TicketAdminConfigRepo(session)
            q = await admin_repo.get_queue(queue_id)
            if q:
                queue_code = q.code
            if ticket_code_filter:
                ticket_code_filter_upper = ticket_code_filter.upper()
                rows = [r for r in rows if (r.get("ticket_code") or "").upper().find(ticket_code_filter_upper) >= 0]
            total = len(rows)
            rows = rows[offset : offset + limit]
            out = [
                {
                    "ticket_id": r["ticket_id"],
                    "ticket_code": r["ticket_code"],
                    "status": r["status"],
                    "priority": r["priority"],
                    "urgency": r.get("urgency"),
                    "importance": r.get("importance"),
                    "requester_id": r.get("requester_id"),
                    "requester_display_name": r.get("requester_display_name"),
                    "position": r["position"],
                    "wait_seconds": r["wait_seconds"],
                    "queue_code": queue_code,
                    "updated_at": r.get("updated_at"),
                }
                for r in rows
            ]
            data = {"tickets": out, "total": total, "limit": limit, "offset": offset}
        body = json.dumps(data).encode("utf-8")
        etag = _etag_from_body(body)
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag})
        return web.Response(
            body=body,
            content_type="application/json",
            headers={"ETag": etag, "Cache-Control": "public, max-age=15"},
        )
    except Exception as e:
        logger.error(f"[public_api/queue/tickets] {e}", exc_info=True)
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_public_queue_stats(request: web.Request) -> web.Response:
    """GET /public_api/queue/stats?days=7&queue_id=... — KPI. ETag/304."""
    if not DB_AVAILABLE or get_session is None:
        return web.json_response({"status": "error", "error": "service_unavailable"}, status=503)
    days, err = _parse_positive_int(request.query.get("days"), 7, 1, 90)
    if err is not None:
        return _validation_error_response("days " + err)
    queue_id = request.query.get("queue_id")
    if queue_id is not None:
        try:
            queue_id = int(queue_id)
        except (TypeError, ValueError):
            return _validation_error_response("invalid queue_id")
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)
    today_start = period_end.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        async with get_session() as session:
            ticket_repo = TicketEventsRepo(session)
            metrics_svc = TicketMetricsService(default_days=7, max_days=365)
            sla_data = await ticket_repo.get_metrics_sla(period_start, period_end, queue_id=queue_id)
            backlog_rows = await ticket_repo.get_metrics_backlog(queue_id=queue_id)
            backlog_open = sum(r["count"] for r in backlog_rows)
            closed_today = await ticket_repo.get_metrics_closed_count(
                today_start, period_end, queue_id=queue_id
            )
            avg_res = await ticket_repo.get_metrics_avg_resolution_minutes(
                period_start, period_end, queue_id=queue_id
            )
            fr_rate = sla_data.get("fr_breached_rate")
            res_rate = sla_data.get("resolution_breached_rate")
            sla_fr_compliance_pct = round(100 * (1 - fr_rate), 1) if fr_rate is not None else None
            sla_res_compliance_pct = round(100 * (1 - res_rate), 1) if res_rate is not None else None
            top_queue_load = None
            if queue_id is None:
                top_list = await ticket_repo.get_top_queue_load(10)
                admin_repo = TicketAdminConfigRepo(session)
                load_with_names = []
                for item in top_list:
                    q = await admin_repo.get_queue(item["queue_id"])
                    load_with_names.append({
                        "queue_id": item["queue_id"],
                        "queue_code": q.code if q else None,
                        "queue_name": q.name if q else None,
                        "open_count": item["open_count"],
                    })
                top_queue_load = load_with_names
            data = {
                "backlog_open": backlog_open,
                "sla_fr_compliance_pct": sla_fr_compliance_pct,
                "sla_res_compliance_pct": sla_res_compliance_pct,
                "avg_resolution_minutes": round(avg_res, 1) if avg_res is not None else None,
                "closed_today": closed_today,
                "top_queue_load": top_queue_load,
                "days": days,
                "queue_id": queue_id,
            }
        body = json.dumps(data).encode("utf-8")
        etag = _etag_from_body(body)
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag})
        return web.Response(
            body=body,
            content_type="application/json",
            headers={"ETag": etag, "Cache-Control": "public, max-age=15"},
        )
    except Exception as e:
        logger.error(f"[public_api/queue/stats] {e}", exc_info=True)
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)
