import pytest

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.providers.observer_provider import ObserverCapabilityProvider


def _capability(capability_id: str, kind: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        title=capability_id,
        provider_id="observer",
        provider_type="observer_provider",
        execution_target="observer_query",
        evidence={
            "produces_evidence": True,
            "kind": kind,
            "domain": "observer",
            "perspective": "observer",
            "passport_eligible": True,
        },
    )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_observer_ticket_summary_returns_normalized_support_output_and_evidence_preview():
    calls = []

    async def load_summary(ticket_id, params):
        calls.append((ticket_id, params))
        return {
            "summary": {
                "ticket_id": ticket_id,
                "root_trace_id": "trace-root",
                "root_trace_status": "error",
                "root_trace_url": "/app/admin/observer?trace_id=trace-root",
                "trace_count": 3,
                "active_trace_count": 0,
                "error_trace_count": 1,
                "signature_count": 1,
                "latest_error_label": "HTTP 502",
                "latest_error_stage": "server.http.request",
                "latest_error_at": "2026-05-12T10:00:00+00:00",
                "top_signature": {
                    "error_signature": "sig-http-502",
                    "title": "HTTP 502",
                    "ticket_occurrences_count": 2,
                },
                "health_label": "error",
            },
            "related_traces_compact": [
                {"trace_id": "trace-root", "status": "error", "title": "root"},
                {"trace_id": "trace-ok", "status": "ok", "title": "ok"},
            ],
            "recent_occurrences_compact": [
                {
                    "error_signature": "sig-http-502",
                    "message": "HTTP 502",
                    "stage": "server.http.request",
                    "severity": "error",
                    "trace_id": "trace-root",
                }
            ],
        }

    provider = ObserverCapabilityProvider(summary_loader=load_summary)

    result = await provider.run(
        _capability("observer.ticket.summary", "observer.summary"),
        ticket_id="ticket-1",
        params={"trace_limit": 5},
    )

    assert calls == [("ticket-1", {"trace_limit": 5})]
    assert result["status"] == "success"
    assert result["diagnostic_status"] == "error"
    assert result["output"]["root_trace_id"] == "trace-root"
    assert result["output"]["health"]["label"] == "error"
    assert result["output"]["counts"]["trace"] == 3
    assert result["output"]["latest_error"]["label"] == "HTTP 502"
    assert result["output"]["top_signature"]["error_signature"] == "sig-http-502"
    assert result["output"]["related_traces"][0]["trace_id"] == "trace-root"
    assert result["evidence_preview"]["kind"] == "observer.summary"
    assert result["evidence_preview"]["status"] == "error"
    assert result["evidence_preview"]["trace_id"] == "trace-root"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_observer_trace_bundle_uses_bundle_loader_and_returns_bundle_contract():
    summary_calls = []
    bundle_calls = []

    async def load_summary(ticket_id, params):
        summary_calls.append((ticket_id, params))
        return {"summary": {"ticket_id": ticket_id, "health_label": "ok"}}

    async def load_bundle(ticket_id, params):
        bundle_calls.append((ticket_id, params))
        return {
            "summary": {
                "primary_trace_id": "trace-root",
                "related_trace_count": 2,
                "span_count": 7,
                "error_count": 1,
                "agent_audit_count": 1,
                "recent_log_count": 0,
            },
            "primary_trace": {
                "trace_id": "trace-root",
                "status": "error",
                "root_kind": "tool_call",
                "error_count": 1,
            },
            "related_traces": [
                {"trace_id": "trace-root", "status": "error", "root_kind": "tool_call", "error_count": 1},
                {"trace_id": "trace-ok", "status": "ok", "root_kind": "ticket", "error_count": 0},
            ],
            "error_occurrences": [
                {
                    "error_signature": "sig-tool",
                    "message_norm": "tool failed",
                    "failure_stage": "tool_run",
                    "severity": "error",
                    "trace_id": "trace-root",
                }
            ],
            "signatures": [
                {
                    "error_signature": "sig-tool",
                    "title": "Tool failed",
                    "occurrences_count": 4,
                    "ticket_occurrences_count": 1,
                }
            ],
            "degradations": [{"tool_name": "screen.collect", "timeout_rate": 0.4}],
            "recommended_next_checks": [{"id": "inspect_trace", "title": "Inspect trace"}],
            "links": {"trace_detail": "/api/admin/tech/traces/trace-root"},
        }

    provider = ObserverCapabilityProvider(summary_loader=load_summary, bundle_loader=load_bundle)

    result = await provider.run(
        _capability("observer.trace.bundle", "observer.trace_bundle"),
        ticket_id="ticket-1",
        params={"trace_id": "trace-root", "include_agent_actions": False},
    )

    assert summary_calls == []
    assert bundle_calls == [("ticket-1", {"trace_id": "trace-root", "include_agent_actions": False})]
    assert result["status"] == "success"
    assert result["diagnostic_status"] == "error"
    assert result["output"]["primary_trace_id"] == "trace-root"
    assert result["output"]["counts"]["related_trace"] == 2
    assert result["output"]["counts"]["error_occurrence"] == 1
    assert result["output"]["degradations"][0]["tool_name"] == "screen.collect"
    assert result["output"]["recommended_next_checks"][0]["id"] == "inspect_trace"
    assert result["summary"] == "Observer bundle: 2 related trace(s), 1 error(s)"
    assert result["evidence_preview"]["kind"] == "observer.trace_bundle"
    assert result["evidence_preview"]["status"] == "error"
    assert result["evidence_preview"]["trace_id"] == "trace-root"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_observer_provider_rejects_unknown_observer_capability_without_querying():
    calls = []

    async def load_summary(ticket_id, params):
        calls.append((ticket_id, params))
        return {}

    provider = ObserverCapabilityProvider(summary_loader=load_summary)

    result = await provider.run(_capability("observer.unknown", "observer.summary"), ticket_id="ticket-1", params={})

    assert result["status"] == "unsupported"
    assert result["error_code"] == "CAPABILITY_TARGET_UNSUPPORTED"
    assert calls == []
