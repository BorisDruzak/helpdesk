from types import SimpleNamespace

import pytest

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.providers.manual_provider import ManualCapabilityProvider


def _capability(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        title=capability_id,
        provider_id="manual",
        provider_type="manual_provider",
        execution_target="manual",
        required_permission="diagnostics.create_manual_evidence",
        evidence={
            "produces_evidence": True,
            "kind": capability_id,
            "domain": "manual",
            "perspective": "manual",
            "passport_eligible": True,
        },
    )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_manual_provider_creates_diagnostic_evidence_and_audit_event():
    evidence_calls = []
    event_calls = []

    async def create_evidence(**kwargs):
        evidence_calls.append(kwargs)
        return SimpleNamespace(
            id="evidence-1",
            ticket_id=kwargs["ticket_id"],
            source_type=kwargs["source_type"],
            source_id=kwargs["source_id"],
            provider_id=kwargs["provider_id"],
            capability_id=kwargs["capability_id"],
            kind=kwargs["kind"],
            domain=kwargs["domain"],
            perspective=kwargs["perspective"],
            title=kwargs["title"],
            summary=kwargs["summary"],
            status=kwargs["status"],
            severity=kwargs["severity"],
            confidence=kwargs["confidence"],
            artifact_refs=kwargs["artifact_refs"],
            tags=kwargs["tags"],
            normalized_payload=kwargs["normalized_payload"],
            passport_eligible=kwargs["passport_eligible"],
            selected_for_passport=kwargs["selected_for_passport"],
            created_by=kwargs["created_by"],
        )

    async def write_event(**kwargs):
        event_calls.append(kwargs)
        return 42

    provider = ManualCapabilityProvider(evidence_creator=create_evidence, event_writer=write_event)

    result = await provider.run(
        _capability("manual.vendor_response"),
        ticket_id="ticket-1",
        device_id="device-1",
        actor=SimpleNamespace(actor_id="support-1"),
        params={
            "title": "Vendor response",
            "summary": "Vendor confirmed upstream outage",
            "status": "warning",
            "severity": "medium",
            "confidence": 0.7,
            "artifact_refs": [{"artifact_id": "artifact-1", "kind": "vendor_pdf"}],
            "tags": ["vendor"],
            "selected_for_passport": True,
            "vendor": {"name": "ISP"},
        },
    )

    assert result["status"] == "created"
    assert result["evidence_id"] == "evidence-1"
    assert result["diagnostic_status"] == "warning"
    assert result["output"]["selected_for_passport"] is True
    assert result["evidence_preview"]["kind"] == "manual.vendor_response"
    assert evidence_calls[0]["source_type"] == "manual"
    assert evidence_calls[0]["source_id"].startswith("manual.vendor_response:ticket-1:")
    assert evidence_calls[0]["created_by"] == "support-1"
    assert evidence_calls[0]["normalized_payload"]["vendor"] == {"name": "ISP"}
    assert event_calls[0]["event_type"] == "diagnostic_manual_evidence_created"
    assert event_calls[0]["payload"]["capability_id"] == "manual.vendor_response"
    assert event_calls[0]["payload"]["evidence_id"] == "evidence-1"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_manual_provider_requires_summary_and_rejects_unknown_capability():
    provider = ManualCapabilityProvider()

    missing_summary = await provider.run(_capability("manual.visual_check"), ticket_id="ticket-1", params={})
    unknown = await provider.run(_capability("manual.unknown"), ticket_id="ticket-1", params={"summary": "ok"})

    assert missing_summary["status"] == "error"
    assert missing_summary["error_code"] == "SUMMARY_REQUIRED"
    assert unknown["status"] == "unsupported"
    assert unknown["error_code"] == "CAPABILITY_TARGET_UNSUPPORTED"
