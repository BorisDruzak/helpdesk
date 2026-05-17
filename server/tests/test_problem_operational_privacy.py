from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemCandidate
from problem.candidate_service import ProblemCandidateService


@pytest.mark.asyncio
async def test_candidate_list_evidence_is_redacted_for_operational_views(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            ProblemCandidate(
                candidate_id=str(uuid.uuid4()),
                fingerprint="privacy-fp",
                status="open",
                signal_type="low_csat_pattern",
                title="Privacy candidate",
                summary="Should redact PII",
                evidence_json={
                    "ticket_ids": ["ticket-1"],
                    "low_csat_count": 2,
                    "requester_id": "secret-requester",
                    "comment": "raw requester comment",
                    "internal_notes": "internal evidence",
                },
                ticket_count=1,
                low_csat_count=2,
            )
        )
        await session.commit()
        candidates = await ProblemCandidateService(session).list_candidates()

    assert candidates[0]["evidence"]["ticket_ids"] == ["ticket-1"]
    assert "secret-requester" not in repr(candidates)
    assert "raw requester comment" not in repr(candidates)
    assert "internal evidence" not in repr(candidates)
