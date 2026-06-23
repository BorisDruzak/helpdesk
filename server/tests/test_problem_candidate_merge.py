from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemActivityEvent, ProblemCandidate
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_candidate_merge_combines_evidence_and_records_activity(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        target = ProblemCandidate(
            candidate_id=str(uuid.uuid4()),
            fingerprint="fp-target",
            status="open",
            signal_type="reopen_pattern",
            title="Target",
            summary="Target",
            service_code="network",
            offering_code="network.vpn",
            ticket_count=1,
            evidence_json={"ticket_ids": ["T1"], "ticket_count": 1},
        )
        source = ProblemCandidate(
            candidate_id=str(uuid.uuid4()),
            fingerprint="fp-source",
            status="open",
            signal_type="sla_breach_pattern",
            title="Source",
            summary="Source",
            service_code="network",
            offering_code="network.vpn",
            ticket_count=2,
            sla_breach_count=2,
            evidence_json={"ticket_ids": ["T2", "T3"], "sla_breach_count": 2},
        )
        session.add_all([target, source])
        await session.commit()

        result = await ProblemCandidateService(session).merge_candidates(source.candidate_id, target.candidate_id, actor_id="support-1", reason="same root pattern")
        await session.commit()
        event = (await session.execute(select(ProblemActivityEvent).where(ProblemActivityEvent.event_type == "candidate_merged"))).scalar_one()

    assert result["source"]["status"] == "merged"
    assert result["source"]["merged_into_candidate_id"] == target.candidate_id
    assert set(result["target"]["evidence"]["ticket_ids"]) == {"T1", "T2", "T3"}
    assert result["target"]["sla_breach_count"] == 2
    assert event.payload_json["target_candidate_id"] == target.candidate_id
