from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiohttp import web
from loguru import logger
from sqlalchemy import text

from app.db import get_session
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from auth.middleware import require_auth
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    build_request_kind_title_map,
    humanize_request_kind,
    resolve_ticket_form_pack,
)
from tickets.statuses import status_label_ru
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.reports import (
    WebReportsAgingBucketItem,
    WebReportsBacklogPriorityItem,
    WebReportsFilterOption,
    WebReportsFilters,
    WebReportsPayload,
    WebReportsPeriod,
    WebReportsRecentTicketItem,
    WebReportsRequestKindItem,
    WebReportsServiceCatalogItem,
    WebReportsStatusAgeItem,
    WebReportsSummary,
    WebReportsTopQueueItem,
    WebReportsTopRequesterItem,
    WebReportsTrendPoint,
)


_PRIORITY_LABELS = {
    "P1": "Критический",
    "P2": "Высокий",
    "P3": "Средний",
    "P4": "Низкий",
}

def _normalize_days(value: str | None) -> int:
    try:
        days = int(value or 7)
    except (TypeError, ValueError):
        return 7
    return max(1, min(days, 90))


def _normalize_queue_id(value: str | None) -> int | None:
    if value in {None, "", "all"}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _priority_label(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    return _PRIORITY_LABELS.get(normalized, normalized or "Без приоритета")


def _status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return status_label_ru(normalized) if normalized else "Неизвестно"


def _request_kind_label(value: str | None, *, label_map: dict[str, str] | None = None) -> str:
    return humanize_request_kind(value, label_map=label_map)


def _compliance_percent(breached_rate: float | None) -> float | None:
    if breached_rate is None:
        return None
    return round(max(0.0, 1.0 - breached_rate) * 100, 1)


def _rate_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, value) * 100, 1)


def _empty_reports_payload(*, days: int, queue_id: int | None, start_at: datetime, end_at: datetime) -> WebReportsPayload:
    return WebReportsPayload(
        period=WebReportsPeriod(
            days=days,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            queue_id=queue_id,
        ),
        filters=WebReportsFilters(queue_options=[]),
        summary=WebReportsSummary(
            open_backlog_count=0,
            closed_in_period_count=0,
            avg_resolution_minutes=None,
            first_response_compliance_percent=None,
            resolution_compliance_percent=None,
            reopen_rate_percent=None,
        ),
        daily_trend=[],
        backlog_by_priority=[],
        aging_buckets=[],
        status_age=[],
        top_queues=[],
        top_requesters=[],
        request_kinds=[],
        tickets_by_service=[],
        tickets_by_offering=[],
        recent_tickets=[],
    )


async def _fetch_daily_trend(
    repo: TicketEventsRepo,
    *,
    period_start: datetime,
    period_end: datetime,
    queue_id: int | None,
) -> list[WebReportsTrendPoint]:
    stmt = text(
        """
        WITH series AS (
            SELECT generate_series(
                date_trunc('day', CAST(:start AS timestamptz)),
                date_trunc('day', (CAST(:end AS timestamptz) - interval '1 second')),
                interval '1 day'
            ) AS day
        ),
        created AS (
            SELECT date_trunc('day', created_at) AS day, count(*)::int AS created_count
            FROM tickets
            WHERE created_at >= :start
              AND created_at < :end
              AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY 1
        ),
        closed AS (
            SELECT date_trunc('day', closed_at) AS day, count(*)::int AS closed_count
            FROM tickets
            WHERE closed_at >= :start
              AND closed_at < :end
              AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY 1
        )
        SELECT
            to_char(series.day AT TIME ZONE 'UTC', 'DD.MM') AS day_label,
            COALESCE(created.created_count, 0)::int AS created_count,
            COALESCE(closed.closed_count, 0)::int AS closed_count
        FROM series
        LEFT JOIN created ON created.day = series.day
        LEFT JOIN closed ON closed.day = series.day
        ORDER BY series.day ASC
        """
    )
    result = await repo.session.execute(
        stmt,
        {
            "start": period_start,
            "end": period_end,
            "qid": queue_id,
        },
    )
    return [
        WebReportsTrendPoint(
            day=str(row[0]),
            created_count=int(row[1] or 0),
            closed_count=int(row[2] or 0),
        )
        for row in result.all()
    ]


async def _fetch_request_kinds(
    repo: TicketEventsRepo,
    *,
    period_start: datetime,
    period_end: datetime,
    queue_id: int | None,
    label_map: dict[str, str] | None = None,
) -> list[WebReportsRequestKindItem]:
    stmt = text(
        """
        SELECT
            COALESCE(NULLIF(custom_fields->>'request_kind', ''), NULLIF(ticket_type, ''), 'request') AS request_kind,
            count(*)::int AS count
        FROM tickets
        WHERE created_at >= :start
          AND created_at < :end
          AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        GROUP BY 1
        ORDER BY count DESC, request_kind ASC
        LIMIT 8
        """
    )
    result = await repo.session.execute(
        stmt,
        {
            "start": period_start,
            "end": period_end,
            "qid": queue_id,
        },
    )
    return [
        WebReportsRequestKindItem(
            key=str(row[0]),
            label=_request_kind_label(row[0], label_map=label_map),
            count=int(row[1] or 0),
        )
        for row in result.all()
    ]


async def _fetch_recent_tickets(
    repo: TicketEventsRepo,
    *,
    queue_label_map: dict[int, str],
    queue_id: int | None,
) -> list[WebReportsRecentTicketItem]:
    tickets = await repo.list_tickets(
        filters={
            "exclude_archived": True,
            **({"queue_id": queue_id} if queue_id is not None else {}),
        },
        order_by="updated_at",
        order_direction="desc",
        limit=6,
        offset=0,
    )
    return [
        WebReportsRecentTicketItem(
            ticket_id=ticket.ticket_id,
            ticket_code=ticket.ticket_code,
            title=ticket.title,
            status=ticket.status,
            status_label=_status_label(ticket.status),
            queue_label=queue_label_map.get(getattr(ticket, "queue_id", None) or -1, "Без очереди"),
            requester_id=ticket.requester_id,
            created_at=ticket.created_at.isoformat() if ticket.created_at else None,
            updated_at=ticket.updated_at.isoformat() if ticket.updated_at else None,
        )
        for ticket in tickets
    ]


async def _fetch_service_catalog_aggregates(
    repo: TicketEventsRepo,
    *,
    period_start: datetime,
    period_end: datetime,
    queue_id: int | None,
    dimension: str,
) -> list[WebReportsServiceCatalogItem]:
    if dimension not in {"service", "offering"}:
        raise ValueError("unsupported report dimension")
    if dimension == "service":
        code_expr = "NULLIF(t.service_code, '')"
        title_expr = "COALESCE(hs.public_title, hs.name, NULLIF(t.service_code, ''), 'Без каталога / Legacy')"
        join_sql = "LEFT JOIN helpdesk_services hs ON hs.code = NULLIF(t.service_code, '')"
        service_select = "NULLIF(t.service_code, '')"
        offering_select = "NULL::text"
        group_expr = "NULLIF(t.service_code, ''), label"
    else:
        code_expr = "NULLIF(t.offering_code, '')"
        title_expr = "COALESCE(hso.public_title, hso.name, NULLIF(t.offering_code, ''), 'Без каталога / Legacy')"
        join_sql = "LEFT JOIN helpdesk_service_offerings hso ON hso.full_code = NULLIF(t.offering_code, '')"
        service_select = "NULLIF(t.service_code, '')"
        offering_select = "NULLIF(t.offering_code, '')"
        group_expr = "NULLIF(t.service_code, ''), NULLIF(t.offering_code, ''), label"
    stmt = text(
        f"""
        SELECT
            {service_select} AS service_code,
            {offering_select} AS offering_code,
            {title_expr} AS label,
            count(*)::int AS total_count,
            count(*) FILTER (WHERE t.status NOT IN ('resolved', 'closed', 'canceled'))::int AS open_count,
            count(*) FILTER (
                WHERE t.first_response_breached_at IS NOT NULL
                   OR t.resolution_breached_at IS NOT NULL
            )::int AS breached_sla_count,
            avg(EXTRACT(EPOCH FROM (COALESCE(t.resolution_at, t.closed_at) - t.created_at)) / 60.0)
                FILTER (WHERE COALESCE(t.resolution_at, t.closed_at) IS NOT NULL) AS avg_resolution_minutes
        FROM tickets t
        {join_sql}
        WHERE t.created_at >= :start
          AND t.created_at < :end
          AND (CAST(:qid AS bigint) IS NULL OR t.queue_id = :qid)
        GROUP BY {group_expr}
        ORDER BY total_count DESC, label ASC
        LIMIT 12
        """
    )
    result = await repo.session.execute(stmt, {"start": period_start, "end": period_end, "qid": queue_id})
    rows = []
    for row in result.all():
        avg_value = row[6]
        rows.append(
            WebReportsServiceCatalogItem(
                service_code=str(row[0]) if row[0] else None,
                offering_code=str(row[1]) if row[1] else None,
                label=str(row[2] or "Без каталога / Legacy"),
                count=int(row[3] or 0),
                open_count=int(row[4] or 0),
                breached_sla_count=int(row[5] or 0),
                avg_resolution_minutes=round(float(avg_value), 1) if avg_value is not None else None,
            )
        )
    return rows


@require_auth("admin", "support")
async def handle_web_reports_summary(request: web.Request) -> web.Response:
    days = _normalize_days(request.query.get("days"))
    queue_id = _normalize_queue_id(request.query.get("queue_id"))
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    try:
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            config_repo = TicketAdminConfigRepo(session)

            queues = await config_repo.list_queues(include_inactive=True)
            queue_label_map = {queue.id: queue.name for queue in queues}
            queue_options = [
                WebReportsFilterOption(value=str(queue.id), label=queue.name)
                for queue in queues
            ]
            form_pack = await resolve_ticket_form_pack(
                TicketFormPacksRepo(session),
                pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
            )
            request_kind_labels = build_request_kind_title_map(form_pack)

            backlog_rows = await repo.get_metrics_backlog(queue_id=queue_id)
            aging_rows = await repo.get_metrics_aging(queue_id=queue_id)
            sla = await repo.get_metrics_sla(period_start, period_end, queue_id=queue_id)
            reopen = await repo.get_metrics_reopen_rate(period_start, period_end, queue_id=queue_id)
            top = await repo.get_metrics_top(period_start, period_end, queue_id=queue_id)
            status_age_rows = await repo.get_metrics_status_age(queue_id=queue_id)
            closed_count = await repo.get_metrics_closed_count(period_start, period_end, queue_id=queue_id)
            avg_resolution = await repo.get_metrics_avg_resolution_minutes(period_start, period_end, queue_id=queue_id)
            daily_trend = await _fetch_daily_trend(
                repo,
                period_start=period_start,
                period_end=period_end,
                queue_id=queue_id,
            )
            request_kinds = await _fetch_request_kinds(
                repo,
                period_start=period_start,
                period_end=period_end,
                queue_id=queue_id,
                label_map=request_kind_labels,
            )
            tickets_by_service = await _fetch_service_catalog_aggregates(
                repo,
                period_start=period_start,
                period_end=period_end,
                queue_id=queue_id,
                dimension="service",
            )
            tickets_by_offering = await _fetch_service_catalog_aggregates(
                repo,
                period_start=period_start,
                period_end=period_end,
                queue_id=queue_id,
                dimension="offering",
            )
            recent_tickets = await _fetch_recent_tickets(
                repo,
                queue_label_map=queue_label_map,
                queue_id=queue_id,
            )
            await session.commit()
    except Exception as exc:
        logger.warning(f"[web_reports] failed to build reports summary: {exc}")
        payload = _empty_reports_payload(
            days=days,
            queue_id=queue_id,
            start_at=period_start,
            end_at=period_end,
        )
        return json_model_response(SuccessResponse[WebReportsPayload](data=payload))

    backlog_by_priority_map: dict[str, int] = {}
    queue_open_map: dict[int | None, int] = {}
    for row in backlog_rows:
        priority = str(row.get("priority") or "").strip().upper() or "P3"
        count = int(row.get("count") or 0)
        backlog_by_priority_map[priority] = backlog_by_priority_map.get(priority, 0) + count
        row_queue_id = row.get("queue_id")
        queue_open_map[row_queue_id] = queue_open_map.get(row_queue_id, 0) + count

    top_queues = sorted(
        queue_open_map.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:6]

    payload = WebReportsPayload(
        period=WebReportsPeriod(
            days=days,
            start_at=period_start.isoformat(),
            end_at=period_end.isoformat(),
            queue_id=queue_id,
        ),
        filters=WebReportsFilters(queue_options=queue_options),
        summary=WebReportsSummary(
            open_backlog_count=sum(int(row.get("count") or 0) for row in backlog_rows),
            closed_in_period_count=int(closed_count or 0),
            avg_resolution_minutes=round(avg_resolution, 1) if avg_resolution is not None else None,
            first_response_compliance_percent=_compliance_percent(sla.get("fr_breached_rate")),
            resolution_compliance_percent=_compliance_percent(sla.get("resolution_breached_rate")),
            reopen_rate_percent=_rate_percent(reopen.get("reopen_rate")),
        ),
        daily_trend=daily_trend,
        backlog_by_priority=[
            WebReportsBacklogPriorityItem(
                priority=priority,
                priority_label=_priority_label(priority),
                count=count,
            )
            for priority, count in sorted(
                backlog_by_priority_map.items(),
                key=lambda item: item[0],
            )
        ],
        aging_buckets=[
            WebReportsAgingBucketItem(
                bucket=str(row.get("bucket") or ""),
                count=int(row.get("count") or 0),
            )
            for row in aging_rows
        ],
        status_age=[
            WebReportsStatusAgeItem(
                status=str(row.get("status") or ""),
                status_label=_status_label(row.get("status")),
                count=int(row.get("count") or 0),
                avg_age_seconds=int(row.get("avg_age_seconds") or 0),
            )
            for row in status_age_rows
        ],
        top_queues=[
            WebReportsTopQueueItem(
                queue_id=row_queue_id,
                queue_label=queue_label_map.get(row_queue_id or -1, "Без очереди"),
                open_count=count,
            )
            for row_queue_id, count in top_queues
        ],
        top_requesters=[
            WebReportsTopRequesterItem(
                requester_id=str(row.get("requester_id") or "anonymous"),
                count=int(row.get("count") or 0),
            )
            for row in top.get("top_requesters", [])
        ],
        request_kinds=request_kinds,
        tickets_by_service=tickets_by_service,
        tickets_by_offering=tickets_by_offering,
        recent_tickets=recent_tickets,
    )
    return json_model_response(SuccessResponse[WebReportsPayload](data=payload))
