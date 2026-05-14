from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering, Ticket, TicketQueue


@pytest.mark.asyncio
async def test_reports_summary_includes_service_catalog_dimensions(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    offering_code = f"{service_code}.laptop_broken"
    now = datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Workplace Support", is_active=True)
        session.add(queue)
        await session.flush()
        service = HelpdeskService(
            service_id=str(uuid.uuid4()),
            code=service_code,
            name="Workplace",
            public_title="Рабочее место",
            short_description="Workplace support",
            lifecycle_status="published",
            visibility="public",
            owner_queue_id=queue.id,
            default_queue_id=queue.id,
        )
        offering = HelpdeskServiceOffering(
            offering_id=str(uuid.uuid4()),
            service_id=service.service_id,
            code="laptop_broken",
            full_code=offering_code,
            name="Laptop broken",
            public_title="Сломался ноутбук",
            short_description="Laptop support",
            lifecycle_status="published",
            visibility="public",
            request_type="incident",
        )
        session.add_all([service, offering])
        session.add(
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-report",
                title="Laptop broken",
                description="Laptop does not boot",
                status="closed",
                ticket_type="incident",
                priority="P2",
                requester_id="user:report",
                queue_id=queue.id,
                created_at=now - timedelta(days=1),
                updated_at=now,
                closed_at=now,
                service_code=service_code,
                offering_code=offering_code,
                request_type="incident",
                catalog_service_id=service.service_id,
                catalog_offering_id=offering.offering_id,
                custom_fields={},
                tags=[],
            )
        )
        await session.commit()

    resp = await test_client.get(
        "/api/web/reports/summary?days=7",
        headers={"Authorization": "Bearer test-ui-admin-token"},
    )
    assert resp.status == 200, await resp.text()
    payload = await resp.json()
    data = payload["data"]
    service_row = next(item for item in data["tickets_by_service"] if item["service_code"] == service_code)
    offering_row = next(item for item in data["tickets_by_offering"] if item["offering_code"] == offering_code)
    assert service_row["label"] == "Рабочее место"
    assert service_row["count"] >= 1
    assert offering_row["label"] == "Сломался ноутбук"
    assert offering_row["count"] >= 1
