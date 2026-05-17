from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Problem, ProblemCandidate, ProblemTicketLink, Ticket
from problem.analytics_service import ProblemAnalyticsService


@pytest.mark.asyncio
async def test_problem_analytics_groups_by_service_without_requester_pii(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    ticket_id = str(uuid.uuid4())
    problem_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-problem-analytics",
                title="VPN",
                description="VPN",
                status="closed",
                requester_id="secret-requester",
                service_code="network",
                offering_code="network.vpn_issue",
                resolved_at=now - timedelta(days=3),
                closed_at=now - timedelta(days=2),
            )
        )
        session.add(
            Problem(
                problem_id=problem_id,
                problem_key="PRB-000001",
                title="Repeated VPN outage",
                description="Aggregate problem",
                status="workaround_available",
                severity="high",
                priority="high",
                service_code="network",
                offering_code="network.vpn_issue",
                source_kind="reopen_pattern",
                opened_at=now - timedelta(days=5),
                workaround_available_at=now - timedelta(days=1),
                metadata_json={"requester_id": "secret-requester"},
                created_by="support-1",
                updated_by="support-1",
            )
        )
        await session.flush()
        session.add(
            ProblemTicketLink(
                link_id=str(uuid.uuid4()),
                problem_id=problem_id,
                ticket_id=ticket_id,
                link_type="confirmed",
                linked_by_actor_id="support-1",
                linked_by="support-1",
            )
        )
        session.add(
            ProblemCandidate(
                candidate_id=str(uuid.uuid4()),
                fingerprint="candidate-network",
                status="open",
                signal_type="low_csat_pattern",
                title="VPN CSAT cluster",
                summary="Low CSAT cluster",
                service_code="network",
                offering_code="network.vpn_issue",
                ticket_count=3,
                low_csat_count=3,
                evidence_json={"ticket_ids": [ticket_id], "requester_id": "secret-requester"},
            )
        )
        await session.commit()

        summary = await ProblemAnalyticsService(session).summary()

    assert summary["open_problem_count"] == 1
    assert summary["problems_by_service"]["network"] == 1
    assert summary["candidate_count"] == 1
    assert summary["linked_ticket_count"] == 1
    assert "secret-requester" not in repr(summary)
