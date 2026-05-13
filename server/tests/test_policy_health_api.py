from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, RoutingPolicy, SlaPolicy, Ticket, VisibilityPolicy


@pytest.mark.asyncio
async def test_policy_health_api_rbac_and_schema(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    template_code = f"printer_repair_{suffix}"
    routing_code = f"printer_route_{suffix}"
    sla_code = f"standard_sla_{suffix}"
    visibility_code = f"safe_visibility_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Printer repair",
                ticket_type="incident",
                routing_policy_code=routing_code,
                sla_policy_code=sla_code,
                visibility_policy_code=visibility_code,
                config_json={"default_queue_code": "support"},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.add(RoutingPolicy(code=routing_code, version="1", title="Printer route", config_json={"rules": []}, is_active=True))
        session.add(SlaPolicy(code=sla_code, version="1", title="Standard SLA", config_json={}, is_active=True))
        session.add(VisibilityPolicy(code=visibility_code, version="1", title="Safe visibility", config_json={"public_fields": ["ticket_code"]}, is_active=True))
        await session.commit()

    admin_resp = await test_client.get(
        "/api/web/admin/helpdesk/policy-health",
        headers={"Authorization": "Bearer test-ui-admin-token"},
    )
    assert admin_resp.status == 200
    admin_payload = await admin_resp.json()
    assert admin_payload["status"] == "ok"
    item = next(template for template in admin_payload["templates"] if template["template_code"] == template_code)
    assert "routing" in item["checks"]

    auditor_resp = await test_client.get(
        f"/api/web/admin/helpdesk/policy-health/{template_code}",
        headers={"Authorization": "Bearer test-ui-auditor-token"},
    )
    assert auditor_resp.status == 200
    detail = await auditor_resp.json()
    assert detail["template_code"] == template_code

    support_resp = await test_client.get(
        "/api/web/admin/helpdesk/policy-health",
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert support_resp.status == 403


@pytest.mark.asyncio
async def test_policy_health_simulate_is_dry_run(test_client, test_engine) -> None:
    template_code = f"printer_repair_dry_run_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Printer repair",
                ticket_type="incident",
                config_json={"default_queue_code": "support", "no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        before = await session.scalar(select(func.count()).select_from(Ticket))

    resp = await test_client.post(
        "/api/web/admin/helpdesk/policy-health/simulate",
        headers={"Authorization": "Bearer test-ui-admin-token"},
        json={"template_code": template_code, "request_form_data": {"summary": "Paper jam"}},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["would_create_ticket"] is False
    assert payload["template_code"] == template_code

    async with session_maker() as session:
        after = await session.scalar(select(func.count()).select_from(Ticket))
    assert after == before
