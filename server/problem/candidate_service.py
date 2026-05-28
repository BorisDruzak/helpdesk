from __future__ import annotations

import uuid
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    KnowledgeFeedbackEvent,
    KnowledgeGapFinding,
    ProblemActivityEvent,
    ProblemCandidate,
    ProblemDetectionRule,
    Ticket,
    TicketFeedback,
    TicketQualityReview,
    TicketReopenEvent,
)
from problem.contracts import clean_text
from problem.problem_service import ProblemService
from problem.serializers import candidate_to_dict


class ProblemCandidateService:
    def __init__(self, session) -> None:
        self.session = session

    async def scan(
        self,
        *,
        actor_id: str | None,
        now: datetime | None = None,
        lookback_hours: int = 168,
        max_candidates: int = 100,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(hours=max(1, int(lookback_hours or 168)))
        created = 0
        updated = 0
        skipped = 0
        candidates: list[dict[str, Any]] = []
        rules = await self._rule_thresholds()
        payloads: list[dict[str, Any]] = []
        for builder in (
            self._low_csat_candidates,
            self._reopen_candidates,
            self._sla_breach_candidates,
            self._failed_qa_candidates,
            self._failed_kb_candidates,
            self._knowledge_gap_candidates,
            self._repeated_incident_candidates,
        ):
            payloads.extend(await builder(window_start, now, rules))
        for payload in payloads[: max(1, int(max_candidates or 100))]:
            if dry_run:
                candidates.append({**payload, "evidence_json": self._redact_evidence(payload.get("evidence_json") or {})})
                skipped += 1
                continue
            result, row = await self._upsert_candidate(payload, actor_id=actor_id, now=now)
            created += 1 if result == "created" else 0
            updated += 1 if result == "updated" else 0
            skipped += 1 if result == "skipped" else 0
            if row is not None:
                candidates.append(candidate_to_dict(row))
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "rules_run": sorted({payload.get("rule_code") or payload.get("signal_type") for payload in payloads}),
            "candidates": candidates,
        }

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
            fingerprint_version=1,
            evidence_hash=self._evidence_hash(self._redact_evidence(evidence)),
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
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
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
                "service_code": self._catalog_code_or_none(row.service_code),
                "offering_code": self._catalog_code_or_none(row.offering_code),
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

    async def merge_candidates(self, source_candidate_id: str, target_candidate_id: str, *, actor_id: str | None, reason: str | None = None) -> dict[str, Any]:
        if source_candidate_id == target_candidate_id:
            raise ValueError("source and target candidates must differ")
        source = await self.session.get(ProblemCandidate, source_candidate_id)
        target = await self.session.get(ProblemCandidate, target_candidate_id)
        if source is None or target is None:
            raise ValueError("candidate not found")
        if source.status not in {"open", "dismissed"} or target.status not in {"open", "accepted"}:
            raise ValueError("candidate status does not allow merge")
        target.evidence_json = self._combine_evidence(target.evidence_json or {}, source.evidence_json or {})
        target.ticket_count = len(set(target.evidence_json.get("ticket_ids") or [])) or max(target.ticket_count or 0, source.ticket_count or 0)
        for field in ("reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count"):
            setattr(target, field, max(int(getattr(target, field) or 0), int(getattr(source, field) or 0)))
        target.duplicate_count = int(target.duplicate_count or 0) + int(source.duplicate_count or 0) + 1
        target.evidence_hash = self._evidence_hash(target.evidence_json)
        target.last_seen_at = max(filter(None, [target.last_seen_at, source.last_seen_at, datetime.now(timezone.utc)]))
        target.updated_at = datetime.now(timezone.utc)
        source.status = "merged"
        source.merged_into_candidate_id = target.candidate_id
        source.reviewed_by_actor_id = actor_id
        source.reviewed_at = datetime.now(timezone.utc)
        source.dismissal_reason = clean_text(reason)
        await self.session.flush()
        await self._activity(
            candidate_id=source.candidate_id,
            event_type="candidate_merged",
            actor_id=actor_id,
            payload={"target_candidate_id": target.candidate_id, "reason": reason or ""},
        )
        return {"source": candidate_to_dict(source), "target": candidate_to_dict(target)}

    async def _low_csat_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("low_csat_pattern", rules):
            return []
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
            if len(items) < int(rules["thresholds"].get("min_low_csat_count", 2)):
                continue
            result.append(
                {
                    "fingerprint": self._fingerprint("low_csat_pattern", "low_csat", service, offering, "", start),
                    "rule_code": "low_csat",
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

    async def _reopen_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("reopen_pattern", rules):
            return []
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
            if len(items) < int(rules["thresholds"].get("min_reopen_count", 2)):
                continue
            result.append(
                {
                    "fingerprint": self._fingerprint("reopen_pattern", "reopen", service, offering, reason, start),
                    "rule_code": "reopen",
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

    async def _sla_breach_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("sla_breach_pattern", rules):
            return []
        rows = (
            await self.session.execute(
                select(Ticket).where(
                    ((Ticket.first_response_breached_at >= start) & (Ticket.first_response_breached_at <= end))
                    | ((Ticket.resolution_breached_at >= start) & (Ticket.resolution_breached_at <= end))
                )
            )
        ).scalars().all()
        groups: dict[tuple[str, str], list[Ticket]] = defaultdict(list)
        for row in rows:
            groups[(row.service_code or "legacy", row.offering_code or "uncategorized")].append(row)
        result = []
        for (service, offering), items in groups.items():
            if len(items) < int(rules["thresholds"].get("min_sla_breach_count", 3)):
                continue
            breach_counts = Counter()
            for item in items:
                if item.first_response_breached_at:
                    breach_counts["first_response"] += 1
                if item.resolution_breached_at:
                    breach_counts["resolution"] += 1
            result.append(
                {
                    "fingerprint": self._fingerprint("sla_breach_pattern", "sla_breach", service, offering, ",".join(sorted(breach_counts)), start),
                    "rule_code": "sla_breach",
                    "signal_type": "sla_breach_pattern",
                    "title": f"Repeated SLA breaches: {service} / {offering}",
                    "summary": f"{len(items)} tickets breached SLA in the scan window.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len({item.ticket_id for item in items}),
                    "sla_breach_count": len(items),
                    "evidence_json": {
                        "ticket_ids": list({item.ticket_id for item in items})[:20],
                        "ticket_count": len({item.ticket_id for item in items}),
                        "sla_breach_count": len(items),
                        "breach_type_counts": dict(breach_counts),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.45 + len(items) / 10),
                }
            )
        return result

    async def _failed_qa_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("qa_failed_pattern", rules):
            return []
        rows = (
            await self.session.execute(
                select(TicketQualityReview).where(
                    TicketQualityReview.created_at >= start,
                    TicketQualityReview.created_at <= end,
                    TicketQualityReview.status.in_(["failed", "action_required"]),
                )
            )
        ).scalars().all()
        groups: dict[tuple[str, str, str], list[TicketQualityReview]] = defaultdict(list)
        for row in rows:
            groups[(row.service_code or "legacy", row.offering_code or "uncategorized", row.review_type)].append(row)
        result = []
        for (service, offering, review_type), items in groups.items():
            if len(items) < int(rules["thresholds"].get("min_failed_qa_count", 2)):
                continue
            ticket_ids = [item.ticket_id for item in items if item.ticket_id]
            result.append(
                {
                    "fingerprint": self._fingerprint("qa_failed_pattern", "qa_failed", service, offering, review_type, start),
                    "rule_code": "qa_failed",
                    "signal_type": "qa_failed_pattern",
                    "title": f"Failed QA cluster: {service} / {review_type}",
                    "summary": f"{len(items)} failed/action-required QA reviews in the scan window.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len(set(ticket_ids)),
                    "evidence_json": {
                        "ticket_ids": list(set(ticket_ids))[:20],
                        "review_type_counts": dict(Counter(item.review_type for item in items)),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.5 + len(items) / 10),
                }
            )
        return result

    async def _failed_kb_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("failed_kb_pattern", rules):
            return []
        rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent).where(
                    KnowledgeFeedbackEvent.created_at >= start,
                    KnowledgeFeedbackEvent.created_at <= end,
                    KnowledgeFeedbackEvent.event_type.in_(["not_helpful", "ticket_created_after_view"]),
                )
            )
        ).scalars().all()
        groups: dict[tuple[str, str, str], list[KnowledgeFeedbackEvent]] = defaultdict(list)
        for row in rows:
            groups[(row.service_code or "legacy", row.offering_code or "uncategorized", row.item_id or "unknown")].append(row)
        result = []
        for (service, offering, item_id), items in groups.items():
            if len(items) < int(rules["thresholds"].get("min_failed_kb_count", 2)):
                continue
            ticket_ids = [item.ticket_id for item in items if item.ticket_id]
            result.append(
                {
                    "fingerprint": self._fingerprint("failed_kb_pattern", "failed_kb", service, offering, item_id, start),
                    "rule_code": "failed_kb",
                    "signal_type": "failed_kb_pattern",
                    "title": f"Failed KB pattern: {service} / {offering}",
                    "summary": f"{len(items)} failed knowledge signals in the scan window.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len(set(ticket_ids)),
                    "failed_kb_count": len(items),
                    "evidence_json": {
                        "ticket_ids": list(set(ticket_ids))[:20],
                        "failed_kb_count": len(items),
                        "knowledge_item_ids": [item_id] if item_id != "unknown" else [],
                        "event_type_counts": dict(Counter(item.event_type for item in items)),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.45 + len(items) / 10),
                }
            )
        return result

    async def _knowledge_gap_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("knowledge_gap_pattern", rules):
            return []
        findings = (
            await self.session.execute(
                select(KnowledgeGapFinding).where(
                    KnowledgeGapFinding.status.in_(["open", "accepted"]),
                    KnowledgeGapFinding.created_at <= end,
                )
            )
        ).scalars().all()
        result = []
        for finding in findings:
            service = finding.service_code or "legacy"
            offering = finding.offering_code or "uncategorized"
            tickets = (
                await self.session.execute(
                    select(Ticket).where(
                        Ticket.created_at >= start,
                        Ticket.created_at <= end,
                        Ticket.service_code == finding.service_code,
                        Ticket.offering_code == finding.offering_code,
                    )
                )
            ).scalars().all()
            if len(tickets) < int(rules["thresholds"].get("min_ticket_count", 5)) and len(tickets) < 3:
                continue
            result.append(
                {
                    "fingerprint": self._fingerprint("knowledge_gap_pattern", "knowledge_gap", service, offering, finding.gap_type, start),
                    "rule_code": "knowledge_gap",
                    "signal_type": "knowledge_gap_pattern",
                    "title": f"Knowledge gap pattern: {service} / {offering}",
                    "summary": f"Open knowledge gap {finding.gap_type} with repeated tickets.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len(tickets),
                    "failed_kb_count": 1,
                    "evidence_json": {
                        "ticket_ids": [item.ticket_id for item in tickets[:20]],
                        "ticket_count": len(tickets),
                        "failed_kb_count": 1,
                        "gap_finding_ids": [finding.finding_id],
                        "gap_type_counts": {finding.gap_type: 1},
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.4 + len(tickets) / 10),
                }
            )
        return result

    async def _repeated_incident_candidates(self, start: datetime, end: datetime, rules: dict[str, Any]) -> list[dict[str, Any]]:
        if self._disabled("repeated_incident_pattern", rules):
            return []
        rows = (
            await self.session.execute(
                select(Ticket).where(Ticket.created_at >= start, Ticket.created_at <= end, Ticket.ticket_type.in_(["incident", "request"]))
            )
        ).scalars().all()
        groups: dict[tuple[str, str], list[Ticket]] = defaultdict(list)
        for row in rows:
            groups[(row.service_code or "legacy", row.offering_code or "uncategorized")].append(row)
        result = []
        for (service, offering), items in groups.items():
            if len(items) < int(rules["thresholds"].get("min_ticket_count", 5)):
                continue
            result.append(
                {
                    "fingerprint": self._fingerprint("repeated_incident_pattern", "repeated_incident", service, offering, "", start),
                    "rule_code": "repeated_incident",
                    "signal_type": "repeated_incident_pattern",
                    "title": f"Repeated incident pattern: {service} / {offering}",
                    "summary": f"{len(items)} tickets in the scan window.",
                    "service_code": service,
                    "offering_code": offering,
                    "ticket_count": len({item.ticket_id for item in items}),
                    "evidence_json": {
                        "ticket_ids": list({item.ticket_id for item in items})[:20],
                        "ticket_count": len({item.ticket_id for item in items}),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                    },
                    "confidence_score": min(1.0, 0.35 + len(items) / 20),
                }
            )
        return result

    async def _upsert_candidate(self, payload: dict[str, Any], *, actor_id: str | None, now: datetime) -> tuple[str, ProblemCandidate | None]:
        evidence = self._redact_evidence(payload.get("evidence_json") or {})
        evidence_hash = self._evidence_hash(evidence)
        row = (
            await self.session.execute(select(ProblemCandidate).where(ProblemCandidate.fingerprint == payload["fingerprint"]))
        ).scalar_one_or_none()
        if row is None:
            row = ProblemCandidate(candidate_id=str(uuid.uuid4()), status="open", **self._model_payload(payload))
            row.fingerprint_version = int(payload.get("fingerprint_version") or 1)
            row.evidence_json = evidence
            row.evidence_hash = evidence_hash
            row.first_seen_at = now
            row.last_seen_at = now
            self.session.add(row)
            await self.session.flush()
            await self._activity(candidate_id=row.candidate_id, event_type="candidate_detected", actor_id=actor_id, payload={"signal_type": row.signal_type})
            return "created", row
        if row.status == "open":
            for key in ("ticket_count", "reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count", "confidence_score"):
                if key in payload:
                    setattr(row, key, payload[key])
            row.evidence_json = evidence
            row.evidence_hash = evidence_hash
            row.last_seen_at = now
            row.duplicate_count = int(row.duplicate_count or 0) + 1
            row.updated_at = now
            await self.session.flush()
            return "updated", row
        row.last_seen_at = now
        row.duplicate_count = int(row.duplicate_count or 0) + 1
        if row.status == "dismissed" and row.dismissed_until and row.dismissed_until <= now and row.evidence_hash != evidence_hash:
            row.status = "open"
            row.evidence_json = evidence
            row.evidence_hash = evidence_hash
            row.updated_at = now
            await self.session.flush()
            await self._activity(candidate_id=row.candidate_id, event_type="candidate_reopened", actor_id=actor_id, payload={"signal_type": row.signal_type})
            return "updated", row
        await self.session.flush()
        return "skipped", row

    def _redact_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in evidence.items()
            if key in {
                "ticket_ids",
                "ticket_count",
                "reopen_count",
                "low_csat_count",
                "sla_breach_count",
                "failed_kb_count",
                "top_reopen_reasons",
                "breach_type_counts",
                "review_type_counts",
                "event_type_counts",
                "knowledge_item_ids",
                "gap_finding_ids",
                "gap_type_counts",
                "window_start",
                "window_end",
            }
        }

    def _model_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "rule_id",
            "fingerprint",
            "fingerprint_version",
            "evidence_hash",
            "signal_type",
            "title",
            "summary",
            "service_code",
            "offering_code",
            "request_type",
            "evidence_json",
            "ticket_count",
            "reopen_count",
            "low_csat_count",
            "sla_breach_count",
            "failed_kb_count",
            "confidence_score",
            "suggested_problem_id",
            "converted_problem_id",
        }
        return {key: value for key, value in payload.items() if key in allowed}

    async def _rule_thresholds(self) -> dict[str, Any]:
        thresholds = {
            "min_ticket_count": 5,
            "min_reopen_count": 2,
            "min_low_csat_count": 2,
            "min_sla_breach_count": 3,
            "min_failed_kb_count": 2,
            "min_failed_qa_count": 2,
            "min_knowledge_gap_count": 1,
        }
        disabled: set[str] = set()
        rows = (await self.session.execute(select(ProblemDetectionRule))).scalars().all()
        for row in rows:
            signals = set(row.signal_types or [])
            if row.code:
                signals.add(row.code)
            if not row.enabled:
                disabled.update(signals)
                disabled.add(self._signal_from_rule(row.code))
                continue
            for key in thresholds:
                value = getattr(row, key, None)
                if value is not None:
                    thresholds[key] = min(thresholds[key], int(value))
        return {"thresholds": thresholds, "disabled": disabled}

    def _disabled(self, signal_type: str, rules: dict[str, Any]) -> bool:
        return signal_type in rules.get("disabled", set())

    def _fingerprint(self, signal_type: str, rule_code: str, service: str, offering: str, signal_key: str, start: datetime) -> str:
        raw = "|".join(["p4.2", signal_type, rule_code, service or "legacy", offering or "uncategorized", signal_key or "-"])
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"p41:{signal_type}:{rule_code}:{service}:{offering}:{digest}"[:220]

    @staticmethod
    def _catalog_code_or_none(value: str | None) -> str | None:
        code = clean_text(value)
        if code in {"legacy", "uncategorized"}:
            return None
        return code

    def _evidence_hash(self, evidence: dict[str, Any]) -> str:
        payload = json.dumps(evidence, sort_keys=True, default=str, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _combine_evidence(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        combined = self._redact_evidence({**left, **right})
        ticket_ids = list(dict.fromkeys([*(left.get("ticket_ids") or []), *(right.get("ticket_ids") or [])]))
        if ticket_ids:
            combined["ticket_ids"] = ticket_ids[:20]
            combined["ticket_count"] = len(ticket_ids)
        for key in ("reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count"):
            combined[key] = max(int(left.get(key) or 0), int(right.get(key) or 0), int(combined.get(key) or 0))
        for key in ("breach_type_counts", "review_type_counts", "event_type_counts", "gap_type_counts"):
            counts = Counter(left.get(key) or {})
            counts.update(right.get(key) or {})
            if counts:
                combined[key] = dict(counts)
        for key in ("knowledge_item_ids", "gap_finding_ids", "top_reopen_reasons"):
            values = list(dict.fromkeys([*(left.get(key) or []), *(right.get(key) or [])]))
            if values:
                combined[key] = values[:20]
        return combined

    @staticmethod
    def _signal_from_rule(code: str | None) -> str:
        mapping = {
            "low_csat": "low_csat_pattern",
            "reopen": "reopen_pattern",
            "sla_breach": "sla_breach_pattern",
            "failed_kb": "failed_kb_pattern",
            "qa_failed": "qa_failed_pattern",
            "knowledge_gap": "knowledge_gap_pattern",
            "repeated_incident": "repeated_incident_pattern",
        }
        return mapping.get(code or "", code or "")

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
