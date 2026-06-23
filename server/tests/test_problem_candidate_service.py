from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering, ProblemCandidate, Ticket, TicketFeedback, TicketReopenEvent
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


def _ticket(ticket_id: str, *, title: str = "VPN issue") -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"device-{ticket_id[:8]}",
        title=title,
        description=title,
        status="closed",
        requester_id=f"requester-{ticket_id[:6]}",
        service_code="network",
        offering_code="network.vpn_issue",
        request_type="incident",
        resolved_at=now - timedelta(hours=1),
        closed_at=now,
    )


@pytest.mark.asyncio
async def test_candidate_scan_creates_idempotent_low_csat_and_reopen_candidates(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        ticket_ids = [str(uuid.uuid4()) for _ in range(3)]
        for idx, ticket_id in enumerate(ticket_ids):
            session.add(_ticket(ticket_id))
            session.add(
                TicketFeedback(
                    feedback_id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    requester_id=f"secret-requester-{idx}",
                    actor_role="requester",
                    rating=2,
                    sentiment="negative",
                    problem_resolved=False,
                    reason_codes=["problem_returned"],
                    comment="raw requester comment must not leak",
                    visibility="requester_visible",
                    source_surface="requester_portal",
                    service_code="network",
                    offering_code="network.vpn_issue",
                    submitted_at=now,
                    is_latest=True,
                )
            )
            session.add(
                TicketReopenEvent(
                    reopen_id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    reopened_by_actor_id=f"secret-requester-{idx}",
                    reopened_by_role="requester",
                    previous_status="closed",
                    new_status="in_progress",
                    reason_code="problem_returned",
                    service_code="network",
                    offering_code="network.vpn_issue",
                    created_at=now,
                )
            )
        await session.commit()

        first = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        second = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate))).scalars().all()

    assert first["created"] >= 2
    assert second["created"] == 0
    assert len(rows) >= 2
    assert any(row.signal_type == "low_csat_pattern" and row.low_csat_count == 3 for row in rows)
    assert any(row.signal_type == "reopen_pattern" and row.reopen_count == 3 for row in rows)
    assert "secret-requester" not in repr(first)
    assert "raw requester comment" not in repr(first)


@pytest.mark.asyncio
async def test_candidate_convert_creates_problem_and_links_sample_tickets(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        service_id = str(uuid.uuid4())
        session.add(HelpdeskService(service_id=service_id, code="network", name="Network", public_title="Network", lifecycle_status="published", visibility="public"))
        session.add(
            HelpdeskServiceOffering(
                offering_id=str(uuid.uuid4()),
                service_id=service_id,
                code="vpn_issue",
                full_code="network.vpn_issue",
                name="VPN issue",
                public_title="VPN issue",
                lifecycle_status="published",
                visibility="public",
            )
        )
        ticket_ids = [str(uuid.uuid4()) for _ in range(2)]
        for ticket_id in ticket_ids:
            session.add(_ticket(ticket_id))
        await session.commit()

        service = ProblemCandidateService(session)
        candidate = await service.create_manual_candidate(
            {
                "title": "Repeated VPN disconnects",
                "summary": "Support observed the same symptom twice.",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "evidence": {"ticket_ids": ticket_ids, "window_start": (now - timedelta(days=7)).isoformat()},
            },
            actor_id="support-1",
        )
        converted = await service.convert_candidate(candidate["candidate_id"], actor_id="support-1")
        await session.commit()

    assert converted["candidate"]["status"] == "converted"
    assert converted["problem"]["problem_key"].startswith("PRB-")
    assert converted["problem"]["service_code"] == "network"


@pytest.mark.asyncio
async def test_repeated_incident_scan_dedupes_across_lookback_windows(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket_ids = [str(uuid.uuid4()) for _ in range(5)]
        for ticket_id in ticket_ids:
            session.add(_ticket(ticket_id, title="Legacy VPN issue"))
        await session.commit()

        now = datetime.now(timezone.utc)
        service = ProblemCandidateService(session)
        first = await service.scan(actor_id="support-1", now=now, lookback_hours=168)
        second = await service.scan(actor_id="support-1", now=now, lookback_hours=1)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.signal_type == "repeated_incident_pattern"))).scalars().all()

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 1
    assert len(rows) == 1
    assert rows[0].ticket_count == 5


@pytest.mark.asyncio
async def test_candidate_convert_maps_legacy_sentinels_to_empty_catalog_fields(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service_id = str(uuid.uuid4())
        session.add(HelpdeskService(service_id=service_id, code="network", name="Network", public_title="Network", lifecycle_status="published", visibility="public"))
        session.add(
            HelpdeskServiceOffering(
                offering_id=str(uuid.uuid4()),
                service_id=service_id,
                code="vpn_issue",
                full_code="network.vpn_issue",
                name="VPN issue",
                public_title="VPN issue",
                lifecycle_status="published",
                visibility="public",
            )
        )
        ticket_ids = [str(uuid.uuid4()) for _ in range(2)]
        for ticket_id in ticket_ids:
            session.add(_ticket(ticket_id, title="Legacy uncategorized issue"))
        await session.commit()

        service = ProblemCandidateService(session)
        candidate = await service.create_manual_candidate(
            {
                "title": "Repeated legacy incidents",
                "summary": "Tickets do not carry catalog fields yet.",
                "service_code": "legacy",
                "offering_code": "uncategorized",
                "evidence": {"ticket_ids": ticket_ids},
            },
            actor_id="support-1",
        )
        converted = await service.convert_candidate(candidate["candidate_id"], actor_id="support-1")
        await session.commit()

    assert converted["candidate"]["status"] == "converted"
    assert converted["problem"]["service_code"] is None
    assert converted["problem"]["offering_code"] is None
