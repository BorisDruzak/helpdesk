from __future__ import annotations

from typing import Any, Dict

from app.db import get_session
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from observer.service import ObserverOverlayService


class ObserverCapabilityProvider:
    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        async with get_session() as session:
            payload = await ObserverOverlayService(session).get_ticket_observer_summary(ticket_id)
            await session.commit()
        result = {
            "status": "success",
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "output": payload,
            "summary": self._summary(capability.id, payload),
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"observer:{ticket_id}:{capability.id}", "status": "succeeded"},
            capability,
            result,
        ).to_dict()
        return result

    def _summary(self, capability_id: str, payload: Dict[str, Any]) -> str:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if capability_id == "observer.trace.bundle":
            return f"Observer bundle: {summary.get('trace_count', 0)} traces"
        return str(summary.get("latest_error_label") or summary.get("health_label") or "Observer summary")
