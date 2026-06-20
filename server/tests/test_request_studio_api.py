from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ClosurePolicy,
    HelpdeskService,
    RequestStudioPublishToken,
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
        headers=_admin_headers(),
        json=payload,
    )
    assert preview_resp.status == 200, await preview_resp.text()
    preview = (await preview_resp.json())["data"]
    assert preview["validation"]["can_publish"] is True
    assert preview["confirmation_token"].startswith("rs1.")
    assert preview["expires_at"]
    assert preview["summary"]["creates"] >= 2
    assert {item["object_type"] for item in preview["diffs"]} >= {"form_schema", "request_template", "offering", "service"}

    preview_resp_2 = await test_client.post(
        "/api/web/admin/request-studio/publish-preview",
        headers=_admin_headers(),
        json=payload,
    )
    assert preview_resp_2.status == 200, await preview_resp_2.text()
    preview_2 = (await preview_resp_2.json())["data"]
    assert preview_2["confirmation_token"].startswith("rs1.")
    assert preview_2["confirmation_token"] != preview["confirmation_token"]

    blocked_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json=payload,
    )
    assert blocked_resp.status == 400

    publish_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": preview_2["confirmation_token"]},
    )
    assert publish_resp.status == 200, await publish_resp.text()
    result = (await publish_resp.json())["data"]
    assert result["request_template"]["template_code"] == f"studio_access_{suffix}"
    assert result["offering"]["lifecycle_status"] == "published"
    assert result["offering"]["request_template_key"] == f"studio_access_{suffix}"

    requester_forms_resp = await test_client.get("/public_api/ticket_forms/current?pack_key=request_forms")
    assert requester_forms_resp.status == 200, await requester_forms_resp.text()
    requester_forms = await requester_forms_resp.json()
    published_forms = {
        form["key"]: form
        for form in requester_forms["pack"]["forms"]
    }
    assert published_forms[f"studio_access_{suffix}"]["request_template_key"] == f"studio_access_{suffix}"
    assert published_forms[f"studio_access_{suffix}"]["fields"][0]["key"] == "summary"

    requester_catalog_resp = await test_client.get("/api/service-catalog/current")
    assert requester_catalog_resp.status == 200, await requester_catalog_resp.text()
    requester_catalog = await requester_catalog_resp.json()
    requester_offerings = {
        offering["request_template_key"]: offering
        for service in requester_catalog["services"]
        for offering in service.get("offerings", [])
    }
    assert requester_offerings[f"studio_access_{suffix}"]["full_code"] == f"studio_service_{suffix}.grant_access"
    assert requester_offerings[f"studio_access_{suffix}"]["title"] == "Доступ к системе"

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == f"studio_access_{suffix}"))
        token_rows = list((await session.execute(select(RequestStudioPublishToken))).scalars().all())
    assert template is not None
    assert template.routing_policy_code == policies["routing"]
    used_rows = [row for row in token_rows if row.used_at is not None]
    assert len(token_rows) >= 2
    assert len(used_rows) == 1
    assert used_rows[0].token_hash != preview_2["confirmation_token"]
    assert len(used_rows[0].token_hash) == 64

    reused_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": preview_2["confirmation_token"]},
    )
    assert reused_resp.status == 409
    assert (await reused_resp.json())["error_code"] == "CONFIRMATION_TOKEN_USED"


@pytest.mark.asyncio
async def test_request_studio_publish_rejects_invalid_mutated_and_expired_tokens(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    policies = await _seed_ready_context(test_engine, suffix)
    payload = _payload(
        suffix,
        routing_code=policies["routing"],
        sla_code=policies["sla"],
        closure_code=policies["closure"],
        visibility_code=policies["visibility"],
    )

    invalid_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": "not-a-token"},
    )
    assert invalid_resp.status == 400
    assert (await invalid_resp.json())["error_code"] == "CONFIRMATION_TOKEN_MALFORMED"

    preview_resp = await test_client.post(
        "/api/web/admin/request-studio/publish-preview",
        headers=_admin_headers(),
        json=payload,
    )
    assert preview_resp.status == 200, await preview_resp.text()
    token = (await preview_resp.json())["data"]["confirmation_token"]

    mutated_payload = {**payload, "form": {**payload["form"], "title": "Mutated title"}, "confirmation_token": token}
    mutated_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json=mutated_payload,
    )
    assert mutated_resp.status == 409
    assert (await mutated_resp.json())["error_code"] == "CONFIRMATION_TOKEN_DRAFT_MISMATCH"

    preview_resp_2 = await test_client.post(
        "/api/web/admin/request-studio/publish-preview",
        headers=_admin_headers(),
        json=payload,
    )
    assert preview_resp_2.status == 200, await preview_resp_2.text()
    expired_token = (await preview_resp_2.json())["data"]["confirmation_token"]
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        row = (
            await session.execute(
                select(RequestStudioPublishToken).where(RequestStudioPublishToken.used_at.is_(None)).order_by(RequestStudioPublishToken.id.desc())
            )
        ).scalars().first()
        assert row is not None
        row.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        await session.commit()

    expired_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": expired_token},
    )
    assert expired_resp.status == 409
    assert (await expired_resp.json())["error_code"] == "CONFIRMATION_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_request_studio_preview_diff_updates_existing_objects(test_client, test_engine) -> None:
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
        headers=_admin_headers(),
        json=payload,
    )
    assert preview_resp.status == 200, await preview_resp.text()
    token = (await preview_resp.json())["data"]["confirmation_token"]
    publish_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_admin_headers(),
        json={**payload, "confirmation_token": token},
    )
    assert publish_resp.status == 200, await publish_resp.text()

    updated = {
        **payload,
        "form": {
            **payload["form"],
            "title": "Updated access title",
            "fields": [
                {**payload["form"]["fields"][0], "label": "Updated summary"},
                {"key": "business_reason", "label": "Business reason", "type": "textarea", "required": False, "options": []},
            ],
        },
        "offering": {**payload["offering"], "public_title": "Updated access title"},
    }
    update_preview_resp = await test_client.post(
        "/api/web/admin/request-studio/publish-preview",
        headers=_admin_headers(),
        json=updated,
    )
    assert update_preview_resp.status == 200, await update_preview_resp.text()
    preview = (await update_preview_resp.json())["data"]
    assert preview["summary"]["updates"] >= 3
    form_diff = next(item for item in preview["diffs"] if item["object_type"] == "form_schema")
    assert form_diff["action"] == "update"
    assert {change["path"] for change in form_diff["changes"]} >= {"title", "fields.business_reason"}


@pytest.mark.asyncio
async def test_request_studio_auditor_can_preview_but_not_publish(test_client, test_engine) -> None:
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
    token = (await preview_resp.json())["data"]["confirmation_token"]

    publish_resp = await test_client.post(
        "/api/web/admin/request-studio/publish",
        headers=_auditor_headers(),
        json={**payload, "confirmation_token": token},
    )
    assert publish_resp.status == 403
