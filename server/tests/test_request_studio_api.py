from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ClosurePolicy,
    HelpdeskService,
    RequestTemplate,
    RoutingPolicy,
    SlaPolicy,
    TicketQueue,
    VisibilityPolicy,
)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


def _payload(suffix: str, *, routing_code: str = "", sla_code: str = "", closure_code: str = "", visibility_code: str = "") -> dict:
    template_code = f"studio_access_{suffix}"
    return {
        "form": {
            "key": template_code,
            "request_kind": template_code,
            "ticket_type": "service_request",
            "title": "Доступ к системе",
            "description": "Запрос доступа из Studio",
            "routing_policy_ref": routing_code or None,
            "sla_policy_ref": sla_code or None,
            "closure_policy_ref": closure_code or None,
            "visibility_policy_ref": visibility_code or None,
            "fields": [
                {
                    "key": "summary",
                    "label": "Что нужно",
                    "type": "textarea",
                    "required": True,
                    "options": [],
                }
            ],
        },
        "offering": {
            "service_code": f"studio_service_{suffix}",
            "code": "grant_access",
            "public_title": "Доступ к системе",
            "short_description": "Запрос доступа",
            "lifecycle_status": "draft",
            "visibility": "public",
            "request_type": "service_request",
            "request_template_key": template_code,
            "routing_policy_code": routing_code or None,
            "sla_policy_code": sla_code or None,
            "closure_policy_code": closure_code or None,
            "visibility_policy_code": visibility_code or None,
        },
    }


async def _seed_ready_context(test_engine, suffix: str) -> dict[str, str]:
    queue_code = f"studio_queue_{suffix}"
    routing_code = f"studio_route_{suffix}"
    sla_code = f"studio_sla_{suffix}"
    closure_code = f"studio_closure_{suffix}"
    visibility_code = f"studio_visibility_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=queue_code, name="Studio Service Desk", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            HelpdeskService(
                service_id=str(uuid.uuid4()),
                code=f"studio_service_{suffix}",
                name="Studio service",
                public_title="Studio service",
                short_description="Studio service",
                lifecycle_status="published",
                visibility="public",
                owner_queue_id=queue.id,
                default_queue_id=queue.id,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            RoutingPolicy(
                code=routing_code,
                version="1",
                title="Studio route",
                config_json={"rules": [{"when": {}, "then": {"queue_code": queue_code}}]},
                is_active=True,
            )
        )
        session.add(SlaPolicy(code=sla_code, version="1", title="Studio SLA", config_json={"targets": {}}, is_active=True))
        session.add(ClosurePolicy(code=closure_code, version="1", title="Studio closure", config_json={"require_resolution_note": True}, is_active=True))
        session.add(VisibilityPolicy(code=visibility_code, version="1", title="Studio visibility", config_json={"public_fields": ["ticket_code", "public_status"]}, is_active=True))
        await session.commit()
    return {
        "routing": routing_code,
        "sla": sla_code,
        "closure": closure_code,
        "visibility": visibility_code,
    }


@pytest.mark.asyncio
async def test_request_studio_validate_blocks_missing_required_blocks(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    await _seed_ready_context(test_engine, suffix)

    response = await test_client.post(
        "/api/web/admin/request-studio/validate-draft",
        headers=_admin_headers(),
        json=_payload(suffix),
    )

    assert response.status == 200, await response.text()
    result = (await response.json())["data"]
    assert result["can_publish"] is False
    assert {issue["code"] for issue in result["issues"]} >= {"routing_missing", "sla_missing", "closure_missing", "visibility_missing"}

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        assert await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == f"studio_access_{suffix}")) is None


@pytest.mark.asyncio
async def test_request_studio_preview_and_publish_use_confirmation_token(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    policies = await _seed_ready_context(test_engine, suffix)
    payload = _payload(
        suffix,
        routing_code=policies["routing"],
        sla_code=policies["sla"],
        closure_code=policies["closure"],
        visibility_code=policies["visibility"],
    )

    preview_resp = await test_client.post(
        "/api/web/admin/request-studio/publish-preview",
        headers=_auditor_headers(),
        json=payload,
    )
    assert preview_resp.status == 200, await preview_resp.text()
    preview = (await preview_resp.json())["data"]
    assert preview["validation"]["can_publish"] is True
    assert preview["confirmation_token"]

    blocked_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json=payload,
    )
    assert blocked_resp.status == 400

    publish_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": preview["confirmation_token"]},
    )
    assert publish_resp.status == 200, await publish_resp.text()
    result = (await publish_resp.json())["data"]
    assert result["request_template"]["template_code"] == f"studio_access_{suffix}"
    assert result["offering"]["lifecycle_status"] == "published"
    assert result["offering"]["request_template_key"] == f"studio_access_{suffix}"

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == f"studio_access_{suffix}"))
    assert template is not None
    assert template.routing_policy_code == policies["routing"]
