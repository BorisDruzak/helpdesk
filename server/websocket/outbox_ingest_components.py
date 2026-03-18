"""
Focused components for outbox ingest pipeline decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from websocket.batch_ack_manager import NackInfo


@dataclass
class EnvelopeValidationResult:
    ok: bool
    outbox_id: Optional[str]
    trace_id: Optional[str]
    error_message: Optional[str] = None


class OutboxEnvelopeValidator:
    def validate(self, message: dict[str, Any]) -> EnvelopeValidationResult:
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=message.get("trace_id"),
                error_message="Payload is not a dict",
            )
        outbox_id = payload.get("outbox_id")
        trace_id = message.get("trace_id")
        if not outbox_id:
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=trace_id,
                error_message="Missing outbox_id in payload",
            )
        return EnvelopeValidationResult(ok=True, outbox_id=str(outbox_id), trace_id=trace_id)


class OutboxAckDecisionService:
    def add_validation_nack(self, *, batch_ack_manager, device_id: str, outbox_id: str, trace_id: str, error: str) -> None:
        batch_ack_manager.add_nack(
            device_id=device_id,
            outbox_id=outbox_id,
            trace_id=trace_id,
            nack_info=NackInfo(
                retryable=False,
                error_code="VALIDATION_ERROR",
                error_message=error,
                retry_after_sec=None,
            ),
        )
