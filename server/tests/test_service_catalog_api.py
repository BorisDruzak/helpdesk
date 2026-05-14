from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, TicketQueue


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _forbidden_keys(payload):
    forbidden = {
        "queue_id",
        "default_queue_id",
        "owner_queue_id",
        "raw_policy_json",
        "policy_refs",
        "approval_policy",
        "approver_ids",
        "requester_id",
        "device_id",
        "custom_fields",
        "trace_id",
        "operation_id",
    }
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden:
                    found.add(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found


@pytest.mark.asyncio
async def test_service_catalog_api_admin_crud_and_public_safe_projection(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    offering_code = "laptop_broken"
    template_code = f"laptop_incident_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Sensitive Internal Department", is_active=True)
        session.add(queue)
        await session.flush()
        queue_id = queue.id
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop incident",
                ticket_type="incident",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    service_resp = await test_client.post(
        "/api/web/admin/service-catalog/services/save-draft",
        headers=_admin_headers(),
        json={
            "code": service_code,
            "public_title": "Рабочее место",
            "short_description": "Ноутбук и периферия",
            "visibility": "public",
            "owner_queue_id": queue_id,
            "default_queue_id": queue_id,
            "reporting_category": "end_user_computing",
        },
    )
    assert service_resp.status == 200

    offering_resp = await test_client.post(
        "/api/web/admin/service-catalog/offerings/save-draft",
        headers=_admin_headers(),
        json={
            "service_code": service_code,
            "code": offering_code,
            "public_title": "Сломался ноутбук",
            "short_description": "Ноутбук не включается",
            "request_type": "incident",
            "request_template_key": template_code,
            "visibility": "public",
        },
    )
    assert offering_resp.status == 200
    offering = (await offering_resp.json())["offering"]

    assert (await test_client.post(f"/api/web/admin/service-catalog/services/{service_code}/publish", headers=_admin_headers())).status == 200
    assert (await test_client.post(f"/api/web/admin/service-catalog/offerings/{offering['full_code']}/publish", headers=_admin_headers())).status == 200

    public_resp = await test_client.get("/api/service-catalog/current")
    assert public_resp.status == 200
    public_payload = await public_resp.json()
    assert public_payload["status"] == "ok"
    assert not _forbidden_keys(public_payload)
    public_service = next(item for item in public_payload["services"] if item["service_code"] == service_code)
    assert public_service["offerings"][0]["full_code"] == f"{service_code}.{offering_code}"

    support_mutation = await test_client.post(
        "/api/web/admin/service-catalog/services/save-draft",
        headers=_support_headers(),
        json={"code": "forbidden"},
    )
    assert support_mutation.status == 403
