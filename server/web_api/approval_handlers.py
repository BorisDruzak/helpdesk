from __future__ import annotations

from aiohttp import web
from loguru import logger

from approvals.service import ApprovalConsentCenterService, ApprovalConsentQuery
from app.db import get_session
from auth.middleware import require_auth
from web_api.dto.approvals import ApprovalConsentCenterPayload
from web_api.dto.common import SuccessResponse, json_model_response


def _int_query(value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _optional_int_query(value: str | None, *, minimum: int, maximum: int) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _int_query(value, default=minimum, minimum=minimum, maximum=maximum)


@require_auth("admin", "support")
async def handle_web_support_approvals(request: web.Request) -> web.Response:
    query = ApprovalConsentQuery(
        scope=(request.query.get("scope") or "team").strip(),
        kind=(request.query.get("kind") or None),
        status=(request.query.get("status") or "pending").strip(),
        risk=(request.query.get("risk") or None),
        object_type=(request.query.get("object_type") or None),
        queue=(request.query.get("queue") or None),
        assignee=(request.query.get("assignee") or None),
        due_window_hours=_optional_int_query(request.query.get("due_window_hours"), minimum=1, maximum=24 * 30),
        limit=_int_query(request.query.get("limit"), default=50, minimum=1, maximum=200),
        offset=_int_query(request.query.get("offset"), default=0, minimum=0, maximum=10000),
    )
    try:
        async with get_session() as session:
            payload = await ApprovalConsentCenterService(session).build_payload(
                auth_context=request["auth_context"],
                query=query,
            )
    except Exception as exc:
        logger.exception(f"[approval_center] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить центр согласований",
                "error_code": "APPROVAL_CENTER_FAILED",
            },
            status=500,
        )

    return json_model_response(SuccessResponse[ApprovalConsentCenterPayload](data=payload))
