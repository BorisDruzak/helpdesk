from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import ProblemActivityEvent, ProblemCandidate, Ticket, TicketFeedback, TicketReopenEvent
from problem.contracts import clean_text
from problem.problem_service import ProblemService
from problem.serializers import candidate_to_dict


class ProblemCandidateService:
    def __init__(self, session) -> None:
        self.session = session

    async def scan(self, *, actor_id: str | None, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(hours=168)
        created = 0
        updated = 0
        for payload in await self._low_csat_candidates(window_start, now):
            result = await self._upsert_candidate(payload, actor_id=actor_id)
            created += 1 if result == "created" else 0
            updated += 1 if result == "updated" else 0
        for payload in await self._reopen_candidates(window_start, now):
            result = await self._upsert_candidate(payload, actor_id=actor_id)
            created += 1 if result == "created" else 0
            updated += 1 if result == "updated" else 0
        return {"created": created, "updated": updated}

    async def create_manual_candidate(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        title = clean_text(payload.get("title"))
        summary = clean_text(payload.get("summary"))
        if not title or not summary:
            raise ValueError("title and summary are required")
        service_code = clean_text(payload.get("service_code"))
        offering_code = clean_text(payload.get("offering_code"))
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        fingerprint = clean_text(payload.get("fingerprint")) or f"manual:{service_code or 'legacy'}:{offering_code or 'uncategorized'}:{title.lower()}"
        row = ProblemCandidate(
            candidate_id=str(uuid.uuid4()),
            fingerprint=fingerprint,
            status="open",
            signal_type="manual",
            title=title,
            summary=summary,
            service_code=service_code,
            offering_code=offering_code,
            request_type=clean_text(payload.get("request_type")),
            evidence_json=self._redact_evidence(evidence),
            ticket_count=len(evidence.get("ticket_ids") or []),
            confidence_score=payload.get("confidence_score") or 0.5,
        )
        self.session.add(row)
        await self.session.flush()
        await self._activity(candidate_id=row.candidate_id, event_type="candidate_detected", actor_id=actor_id, payload={"signal_type": "manual"})
        return candidate_to_dict(row)

    async def convert_candidate(self, candidate_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self.session.get(ProblemCandidate, candidate_id)
        if row is None:
            raise ValueError("candidate not found")
        problem = await ProblemService(self.session).create_problem(
            {
                "title": row.title,
                "description": row.summary,
                "service_code": row.service_code,
                "offering_code": row.offering_code,
                "request_type": row.request_type,
                "source_kind": row.signal_type,
                "source_ref": row.candidate_id,
                "severity": "high" if (row.low_csat_count or row.reopen_count) >= 3 else "medium",
            },
            actor_id=actor_id,
        )
        for ticket_id in (row.evidence_json or {}).get("ticket_ids", [])[:20]:
            await ProblemService(self.session).link_ticket(problem["problem_id"], ticket_id, link_type="suspected", actor_id=actor_id)
        row.status = "converted"
        row.converted_problem_id = problem["problem_id"]
        row.reviewed_by_actor_id = actor_id
        row.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._activity(candidate_id=row.candidate_id, event_type="candidate_accepted", actor_id=actor_id, payload={"problem_id": problem["problem_id"]})
        return {"candidate": candidate_to_dict(row), "problem": problem}

    async def list_candidates(self, *, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(ProblemCandidate).order_by(ProblemCandidate.created_at.desc())
        if status:
            stmt = stmt.where(ProblemCandidate.status == status)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [candidate_to_dict(row) for row in rows]

    async def _low_csat_candidates(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(TicketFeedback).where(TicketFeedback.submitted_at >= start, TicketFeedback.submitted_at <= end)
            )
        ).scalars().all()
        groups: dict[tuple[str, str], list[TicketFeedback]] = defaultdict(list)
        for row in rows:
            if row.rating <= 3 or row.problem_resolved is False:
                groups[(row.service_code or "legacy", row.offering_code or "uncategorized")].append(row)
        result = []
        for (service, offering), items in groups.items():
            if len(items) < 2:
                continue
            result.append(
                {
                    "fingerprint": f"low_csat:{service}:{offering}:{start.date().isoformat()}",
                    "signal_type": "low_csat_pattern",
                    "title": f"Low CSAT cluster: {service} / {offering}",
                    "summary": f"{len(items)} low CSAT feedback rows in the scan window.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len({item.ticket_id for item in items}),
                    "low_csat_count": len(items),
                    "evidence_json": {
                        "ticket_ids": list({item.ticket_id for item in items})[:20],
                        "low_csat_count": len(items),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.4 + len(items) / 10),
                }
            )
        return result

    async def _reopen_candidates(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(TicketReopenEvent).where(TicketReopenEvent.created_at >= start, TicketReopenEvent.created_at <= end)
            )
        ).scalars().all()
        groups: dict[tuple[str, str, str], list[TicketReopenEvent]] = defaultdict(list)
        for row in rows:
            groups[(row.service_code or "legacy", row.offering_code or "uncategorized", row.reason_code)].append(row)
        result = []
        for (service, offering, reason), items in groups.items():
            if len(items) < 2:
                continue
            result.append(
                {
                    "fingerprint": f"reopen:{service}:{offering}:{reason}:{start.date().isoformat()}",
                    "signal_type": "reopen_pattern",
                    "title": f"Repeated reopens: {service} / {reason}",
                    "summary": f"{len(items)} reopen events with reason {reason}.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len({item.ticket_id for item in items}),
                    "reopen_count": len(items),
                    "evidence_json": {
                        "ticket_ids": list({item.ticket_id for item in items})[:20],
                        "reopen_count": len(items),
                        "top_reopen_reasons": [reason],
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.45 + len(items) / 10),
                }
            )
        return result

    async def _upsert_candidate(self, payload: dict[str, Any], *, actor_id: str | None) -> str:
        row = (
            await self.session.execute(select(ProblemCandidate).where(ProblemCandidate.fingerprint == payload["fingerprint"]))
        ).scalar_one_or_none()
        if row is None:
            row = ProblemCandidate(candidate_id=str(uuid.uuid4()), status="open", **payload)
            row.evidence_json = self._redact_evidence(payload.get("evidence_json") or {})
            self.session.add(row)
            await self.session.flush()
            await self._activity(candidate_id=row.candidate_id, event_type="candidate_detected", actor_id=actor_id, payload={"signal_type": row.signal_type})
            return "created"
        if row.status == "open":
            for key in ("ticket_count", "reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count", "confidence_score"):
                if key in payload:
                    setattr(row, key, payload[key])
            row.evidence_json = self._redact_evidence(payload.get("evidence_json") or {})
            row.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            return "updated"
        return "skipped"

    def _redact_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in evidence.items()
            if key in {"ticket_ids", "ticket_count", "reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count", "top_reopen_reasons", "window_start", "window_end"}
        }

    async def _activity(self, *, candidate_id: str, event_type: str, actor_id: str | None, payload: dict[str, Any]) -> None:
        self.session.add(
            ProblemActivityEvent(
                event_id=str(uuid.uuid4()),
                candidate_id=candidate_id,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload,
            )
        )
        await self.session.flush()
