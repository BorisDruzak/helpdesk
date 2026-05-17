from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _user_headers(login: str = "alice") -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{login}"}


@pytest.mark.asyncio
async def test_problem_web_api_create_link_transition_and_metrics(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-problem-api",
                title="VPN issue",
                description="VPN",
                status="closed",
                requester_id="alice",
                service_code="network",
                offering_code="network.vpn_issue",
                resolved_at=datetime.now(timezone.utc),
                closed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    created = await test_client.post(
        "/api/web/problems",
        headers=_support_headers(),
        json={
            "title": "Repeated VPN outage",
            "description": "Multiple tickets share the same failure.",
            "severity": "high",
            "service_code": "network",
            "offering_code": "network.vpn_issue",
        },
    )
    assert created.status == 200, await created.text()
    problem = (await created.json())["problem"]

    linked = await test_client.post(
        f"/api/web/problems/{problem['problem_id']}/link-ticket",
        headers=_support_headers(),
        json={"ticket_id": ticket_id, "link_type": "confirmed", "evidence_summary": "Same symptom"},
    )
    transitioned = await test_client.post(
        f"/api/web/problems/{problem['problem_id']}/transition",
        headers=_support_headers(),
        json={"status": "investigating"},
    )
    ticket_links = await test_client.get(f"/api/web/problems?ticket_id={ticket_id}", headers=_support_headers())
    problem_detail = await test_client.get(f"/api/web/problems/{problem['problem_id']}", headers=_support_headers())
    summary = await test_client.get("/api/web/problems/metrics/summary", headers=_admin_headers())

    assert linked.status == 200, await linked.text()
    assert transitioned.status == 200, await transitioned.text()
    assert ticket_links.status == 200, await ticket_links.text()
    assert problem_detail.status == 200, await problem_detail.text()
    assert (await ticket_links.json())["items"][0]["problem"]["problem_id"] == problem["problem_id"]
    assert (await problem_detail.json())["ticket_links"][0]["ticket_id"] == ticket_id
    assert summary.status == 200, await summary.text()
    payload = await summary.json()
    assert payload["summary"]["open_problem_count"] >= 1
    assert payload["summary"]["problems_by_service"]["network"] >= 1


@pytest.mark.asyncio
async def test_problem_web_api_denies_requester_and_auditor_mutation(test_client) -> None:
    denied_user = await test_client.get("/api/web/problems", headers=_user_headers())
    denied_auditor_create = await test_client.post(
        "/api/web/problems",
        headers={"Authorization": "Bearer test-ui-auditor-token"},
        json={"title": "Nope", "description": "Nope"},
    )
    auditor_read = await test_client.get("/api/web/problems", headers={"Authorization": "Bearer test-ui-auditor-token"})

    assert denied_user.status == 403
    assert denied_auditor_create.status == 403
    assert auditor_read.status == 200, await auditor_read.text()
