from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from app.db import get_session
from app.repos.ticket_events_repo import TicketEventsRepo
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.serialization import evidence_to_dict


EvidenceCreator = Callable[..., Awaitable[Any]]
EventWriter = Callable[..., Awaitable[Any]]

MANUAL_CAPABILITY_DEFAULTS: dict[str, dict[str, Any]] = {
    "manual.visual_check": {
        "kind": "manual.visual_check",
        "title": "Manual visual check",
        "required_fact": "operator_visual_check",
        "section_key": "operator_checks",
    },
    "manual.vendor_response": {
        "kind": "manual.vendor_response",
        "title": "Vendor response",
        "required_fact": "vendor_response",
        "section_key": "vendor_response",
    },
    "manual.operator_note": {
        "kind": "manual.operator_note",
        "title": "Operator note",
        "required_fact": "operator_note",
        "section_key": "operator_checks",
    },
    "manual.customer_confirmation": {
        "kind": "manual.customer_confirmation",
        "title": "Customer confirmation",
        "required_fact": "customer_confirmation",
        "section_key": "customer_confirmation",
    },
}

ALLOWED_STATUSES = {"ok", "warning", "error", "info", "unknown"}
ALLOWED_SEVERITIES = {"none", "low", "medium", "high", "critical"}


def _actor_id(actor: Any) -> str:
    return str(getattr(actor, "actor_id", None) or actor or "support")


def _list_param(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


class ManualCapabilityProvider:
    def __init__(
        self,
        *,
        evidence_creator: Optional[EvidenceCreator] = None,
        event_writer: Optional[EventWriter] = None,
    ) -> None:
        self.evidence_creator = evidence_creator
        self.event_writer = event_writer

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        if capability.id not in MANUAL_CAPABILITY_DEFAULTS:
            return {
                "status": "unsupported",
                "error_code": "CAPABILITY_TARGET_UNSUPPORTED",
                "message": f"Manual capability '{capability.id}' is not implemented",
                "capability_id": capability.id,
                "ticket_id": str(kwargs.get("ticket_id") or "").strip() or None,
                "device_id": str(kwargs.get("device_id") or "").strip() or None,
            }
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        summary = str(params.get("summary") or params.get("note") or params.get("response") or "").strip()
        if not summary:
            return {
                "status": "error",
                "error_code": "SUMMARY_REQUIRED",
                "capability_id": capability.id,
                "message": "summary is required for manual evidence",
            }

        defaults = MANUAL_CAPABILITY_DEFAULTS[capability.id]
        evidence_meta = capability.evidence or {}
        title = str(params.get("title") or defaults["title"] or capability.title).strip()
        status = self._status(params.get("status"))
        severity = self._severity(params.get("severity"), status)
        actor_id = _actor_id(kwargs.get("actor"))
        artifact_refs = _list_param(params.get("artifact_refs"))
        tags = [str(item) for item in _list_param(params.get("tags")) if str(item).strip()]
        normalized_payload = self._normalized_payload(capability, params, actor_id)
        source_id = self._source_id(capability.id, ticket_id, params, summary)
        passport_eligible = bool(params.get("passport_eligible", evidence_meta.get("passport_eligible", True)))
        selected_for_passport = bool(params.get("selected_for_passport", False)) and passport_eligible

        evidence = await self._create_evidence(
            ticket_id=ticket_id,
            title=title,
            summary=summary,
            status=status,
            kind=str(params.get("kind") or evidence_meta.get("kind") or defaults["kind"]),
            domain=str(params.get("domain") or evidence_meta.get("domain") or "manual"),
            perspective=str(params.get("perspective") or evidence_meta.get("perspective") or "manual"),
            created_by=actor_id,
            source_id=source_id,
            capability_id=capability.id,
            severity=severity,
            confidence=params.get("confidence"),
            normalized_payload=normalized_payload,
            raw_ref=params.get("raw_ref"),
            artifact_refs=artifact_refs,
            redaction_level=params.get("redaction_level"),
            tags=tags,
            passport_eligible=passport_eligible,
            selected_for_passport=selected_for_passport,
        )
        event_id = await self._write_event(
            ticket_id=ticket_id,
            device_id=str(kwargs.get("device_id") or params.get("device_id") or "manual"),
            capability=capability,
            evidence=evidence,
            actor_id=actor_id,
            status=status,
            title=title,
            summary=summary,
            source_id=source_id,
        )

        output = self._evidence_output(evidence)
        result = {
            "status": "created",
            "diagnostic_status": status,
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "device_id": str(kwargs.get("device_id") or "").strip() or None,
            "evidence_id": getattr(evidence, "id", None),
            "event_id": event_id,
            "output": output,
            "summary": summary,
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"manual:{getattr(evidence, 'id', source_id)}", "status": status},
            capability,
            {"status": status, "summary": summary, "output": output},
        ).to_dict()
        return result

    async def _create_evidence(self, **kwargs: Any) -> Any:
        if self.evidence_creator is not None:
            injected = dict(kwargs)
            injected.setdefault("source_type", "manual")
            injected.setdefault("provider_id", "manual")
            return await self.evidence_creator(**injected)
        async with get_session() as session:
            evidence = await DiagnosticProjectionService(session).create_manual_evidence(**kwargs)
            await session.commit()
            return evidence

    async def _write_event(self, **kwargs: Any) -> Any:
        if self.event_writer is not None:
            return await self.event_writer(
                ticket_id=kwargs["ticket_id"],
                device_id=kwargs["device_id"],
                event_type="diagnostic_manual_evidence_created",
                event_id=f"manual-evidence:{getattr(kwargs['evidence'], 'id', kwargs['source_id'])}",
                payload=self._event_payload(**kwargs),
            )
        async with get_session() as session:
            event_id = await self._write_event_in_session(session, **kwargs)
            await session.commit()
            return event_id

    async def _write_event_in_session(self, session: Any, **kwargs: Any) -> Any:
        evidence = kwargs["evidence"]
        result = await TicketEventsRepo(session).add_event(
            ticket_id=kwargs["ticket_id"],
            device_id=kwargs["device_id"],
            agent_seq=None,
            event_type="diagnostic_manual_evidence_created",
            event_id=f"manual-evidence:{getattr(evidence, 'id', kwargs['source_id'])}",
            payload=self._event_payload(**kwargs),
        )
        return result[0] if result else None

    def _event_payload(self, **kwargs: Any) -> dict[str, Any]:
        evidence = kwargs["evidence"]
        return {
            "type": "diagnostic_manual_evidence_created",
            "capability_id": kwargs["capability"].id,
            "provider_id": kwargs["capability"].provider_id,
            "evidence_id": getattr(evidence, "id", None),
            "source_type": getattr(evidence, "source_type", "manual"),
            "source_id": getattr(evidence, "source_id", kwargs["source_id"]),
            "kind": getattr(evidence, "kind", None),
            "domain": getattr(evidence, "domain", None),
            "perspective": getattr(evidence, "perspective", None),
            "status": kwargs["status"],
            "title": kwargs["title"],
            "summary": kwargs["summary"],
            "actor_id": kwargs["actor_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _status(self, raw: Any) -> str:
        value = str(raw or "info").strip().lower()
        return value if value in ALLOWED_STATUSES else "info"

    def _severity(self, raw: Any, status: str) -> str:
        value = str(raw or "").strip().lower()
        if value in ALLOWED_SEVERITIES:
            return value
        if status == "ok":
            return "none"
        if status == "error":
            return "medium"
        return "low"

    def _normalized_payload(self, capability: CapabilityDescriptor, params: dict[str, Any], actor_id: str) -> dict[str, Any]:
        reserved = {
            "title",
            "summary",
            "note",
            "response",
            "status",
            "severity",
            "confidence",
            "artifact_refs",
            "tags",
            "passport_eligible",
            "selected_for_passport",
            "raw_ref",
            "redaction_level",
        }
        extra = {key: value for key, value in params.items() if key not in reserved}
        return {
            "capability_id": capability.id,
            "provider_id": capability.provider_id,
            "actor_id": actor_id,
            **extra,
        }

    def _source_id(self, capability_id: str, ticket_id: str, params: dict[str, Any], summary: str) -> str:
        explicit = str(params.get("source_id") or "").strip()
        if explicit:
            return explicit
        source_text = "|".join(
            [
                capability_id,
                ticket_id,
                str(params.get("title") or ""),
                summary,
                str(params.get("raw_ref") or ""),
            ]
        )
        return f"{capability_id}:{ticket_id}:{hashlib.sha256(source_text.encode('utf-8')).hexdigest()[:16]}"

    def _evidence_output(self, evidence: Any) -> dict[str, Any]:
        if hasattr(evidence, "observed_at"):
            return evidence_to_dict(evidence)
        return {
            "id": getattr(evidence, "id", None),
            "ticket_id": getattr(evidence, "ticket_id", None),
            "source_type": getattr(evidence, "source_type", None),
            "source_id": getattr(evidence, "source_id", None),
            "provider_id": getattr(evidence, "provider_id", None),
            "capability_id": getattr(evidence, "capability_id", None),
            "kind": getattr(evidence, "kind", None),
            "domain": getattr(evidence, "domain", None),
            "perspective": getattr(evidence, "perspective", None),
            "title": getattr(evidence, "title", None),
            "summary": getattr(evidence, "summary", None),
            "status": getattr(evidence, "status", None),
            "severity": getattr(evidence, "severity", None),
            "confidence": getattr(evidence, "confidence", None),
            "normalized_payload": getattr(evidence, "normalized_payload", {}) or {},
            "artifact_refs": getattr(evidence, "artifact_refs", []) or [],
            "tags": getattr(evidence, "tags", []) or [],
            "passport_eligible": bool(getattr(evidence, "passport_eligible", False)),
            "selected_for_passport": bool(getattr(evidence, "selected_for_passport", False)),
            "created_by": getattr(evidence, "created_by", None),
        }
