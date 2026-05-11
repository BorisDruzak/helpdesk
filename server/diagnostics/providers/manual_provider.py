from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

from app.db import get_session
from app.repos.ticket_passport_repo import TicketPassportRepo
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub


def _actor_id(actor: Any) -> str:
    return str(getattr(actor, "actor_id", None) or "system")


class ManualCapabilityProvider:
    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        title = str(params.get("title") or capability.title).strip() or capability.title
        summary = str(params.get("summary") or params.get("note") or "").strip()
        if not summary:
            return {
                "status": "error",
                "error_code": "SUMMARY_REQUIRED",
                "capability_id": capability.id,
                "message": "summary is required for manual evidence",
            }
        evidence = capability.evidence or {}
        source_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()[:16]
        async with get_session() as session:
            item = await TicketPassportRepo(session).add_evidence(
                ticket_id=ticket_id,
                passport_id=None,
                evidence_type=str(evidence.get("kind") or capability.id),
                source_ref=f"manual:{capability.id}:{ticket_id}",
                source_kind="manual_capability",
                source_id=f"{capability.id}:{ticket_id}:{source_hash}",
                required_fact=str(params.get("required_fact") or "operator_checks"),
                section_key=str(params.get("section_key") or "operator_checks"),
                artifact_id=params.get("artifact_id"),
                title=title,
                summary=summary,
                visibility=str(params.get("visibility") or "internal"),
                verification_status=str(params.get("verification_status") or "accepted"),
                verified_by=_actor_id(kwargs.get("actor")),
                verified_at=datetime.now(timezone.utc),
                captured_at=datetime.now(timezone.utc),
                metadata_json={
                    "capability_id": capability.id,
                    "provider_id": capability.provider_id,
                    "domain": evidence.get("domain"),
                    "perspective": evidence.get("perspective"),
                    **(params.get("metadata") if isinstance(params.get("metadata"), dict) else {}),
                },
                export_visibility=str(params.get("export_visibility") or "internal"),
                created_by=_actor_id(kwargs.get("actor")),
            )
            await session.commit()
        result = {
            "status": "created",
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "evidence_id": item.id,
            "output": {
                "evidence_id": item.id,
                "title": item.title,
                "summary": item.summary,
                "verification_status": item.verification_status,
            },
            "summary": summary,
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"manual:{item.id}", "status": "created"},
            capability,
            result,
        ).to_dict()
        return result
