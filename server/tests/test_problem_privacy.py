from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Problem, ProblemRCARecord, Ticket

pytestmark = pytest.mark.db_cleanup("full")


def _user_headers(login: str = "alice") -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{login}"}


@pytest.mark.asyncio
async def test_requester_ticket_detail_does_not_expose_internal_problem_or_rca(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    problem_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-problem-privacy",
                title="VPN",
                description="VPN",
                status="closed",
                requester_id="alice",
                resolved_at=datetime.now(timezone.utc),
                closed_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            Problem(
                problem_id=problem_id,
                problem_key="PRB-999999",
                title="Internal VPN defect",
                description="Internal RCA evidence",
                status="investigating",
                severity="high",
                priority="high",
                source_kind="manual",
                created_by="support-1",
                updated_by="support-1",
            )
        )
        session.add(
            ProblemRCARecord(
                rca_id=str(uuid.uuid4()),
                problem_id=problem_id,
                version_number=1,
                status="draft",
                methodology="five_whys",
                problem_statement="Internal problem statement",
                root_cause="secret internal root cause",
                root_cause_category="configuration",
                created_by="support-1",
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/tickets/{ticket_id}", headers=_user_headers())

    assert response.status == 200, await response.text()
    text = repr(await response.json())
    assert "PRB-999999" not in text
    assert "secret internal root cause" not in text
    assert "Internal RCA evidence" not in text


@pytest.mark.asyncio
async def test_problem_analytics_response_has_no_pii_or_comments(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Problem(
                problem_id=str(uuid.uuid4()),
                problem_key="PRB-000123",
                title="Repeated VPN issue",
                description="Aggregate-only analytics",
                status="investigating",
                severity="high",
                priority="high",
                service_code="network",
                offering_code="network.vpn_issue",
                source_kind="csat_pattern",
                metadata_json={"requester_id": "secret-requester", "comment": "raw requester comment"},
                created_by="support-1",
                updated_by="support-1",
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/problems/metrics/summary", headers={"Authorization": "Bearer test-ui-support-token"})

    assert response.status == 200, await response.text()
    text = repr(await response.json())
    assert "secret-requester" not in text
    assert "raw requester comment" not in text
