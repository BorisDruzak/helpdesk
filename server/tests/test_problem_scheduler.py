from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemScannerRun, Ticket, TicketReopenEvent
from app.services.problem_candidate_scheduler import ProblemCandidateScheduler

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_problem_scheduler_disabled_does_not_start(test_engine) -> None:
    scheduler = ProblemCandidateScheduler(
        session_maker=async_sessionmaker(test_engine, expire_on_commit=False),
        enabled=False,
        interval_seconds=1,
        initial_delay_seconds=0,
    )
    await scheduler.start()
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_problem_scheduler_run_once_records_completed_run(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for _ in range(2):
            ticket_id = str(uuid.uuid4())
            session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn", closed_at=now))
            session.add(TicketReopenEvent(reopen_id=str(uuid.uuid4()), ticket_id=ticket_id, previous_status="closed", new_status="in_progress", reason_code="problem_returned", service_code="network", offering_code="network.vpn", created_at=now))
        await session.commit()

    scheduler = ProblemCandidateScheduler(session_maker=session_maker, enabled=True, interval_seconds=60, initial_delay_seconds=0)
    result = await scheduler.run_once(triggered_by="manual", actor_id="admin-1", now=now)
    async with session_maker() as session:
        run = (await session.execute(select(ProblemScannerRun))).scalar_one()

    assert result["status"] == "completed"
    assert result["candidates_created"] == 1
    assert run.status == "completed"
    assert run.triggered_by == "manual"
    assert run.candidates_created == 1
    assert run.duration_ms is not None


@pytest.mark.asyncio
async def test_problem_scheduler_prevents_overlapping_runs(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    scheduler = ProblemCandidateScheduler(session_maker=session_maker, enabled=True, interval_seconds=60, initial_delay_seconds=0)

    async def slow_scan(self, *, actor_id, now=None, lookback_hours=168, max_candidates=100, dry_run=False):
        await asyncio.sleep(0.05)
        return {"created": 0, "updated": 0, "skipped": 0, "candidates": []}

    monkeypatch.setattr("problem.candidate_service.ProblemCandidateService.scan", slow_scan)
    first, second = await asyncio.gather(
        scheduler.run_once(triggered_by="manual", actor_id="admin-1"),
        scheduler.run_once(triggered_by="manual", actor_id="admin-1"),
    )

    assert sorted([first["status"], second["status"]]) == ["completed", "skipped_overlap"]
