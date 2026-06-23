from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketReopenEvent

pytestmark = pytest.mark.db_cleanup("full")


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


def _user_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-user:alice"}


@pytest.mark.asyncio
async def test_problem_scanner_status_and_manual_run_api(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for _ in range(2):
            ticket_id = str(uuid.uuid4())
            session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn", closed_at=now))
            session.add(TicketReopenEvent(reopen_id=str(uuid.uuid4()), ticket_id=ticket_id, previous_status="closed", new_status="in_progress", reason_code="problem_returned", service_code="network", offering_code="network.vpn", created_at=now))
        await session.commit()

    status_before = await test_client.get("/api/web/problem-scanner/status", headers=_support_headers())
    run = await test_client.post("/api/web/problem-scanner/run", headers=_admin_headers(), json={"lookback_hours": 168})
    runs = await test_client.get("/api/web/problem-scanner/runs", headers=_support_headers())

    assert status_before.status == 200, await status_before.text()
    assert run.status == 200, await run.text()
    assert (await run.json())["run"]["status"] == "completed"
    assert (await run.json())["run"]["candidates_created"] == 1
    assert runs.status == 200, await runs.text()
    assert (await runs.json())["runs"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_problem_scanner_api_rbac(test_client) -> None:
    requester_status = await test_client.get("/api/web/problem-scanner/status", headers=_user_headers())
    auditor_run = await test_client.post("/api/web/problem-scanner/run", headers=_auditor_headers(), json={})
    auditor_status = await test_client.get("/api/web/problem-scanner/status", headers=_auditor_headers())

    assert requester_status.status == 403
    assert auditor_run.status == 403
    assert auditor_status.status == 200, await auditor_status.text()
