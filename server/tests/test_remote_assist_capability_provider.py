from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.providers.remote_assist_provider import RemoteAssistCapabilityProvider


def _capability(capability_id: str, *, permission: str = "remote_assist.request") -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        title=capability_id,
        provider_id="remote_assist",
        provider_type="remote_assist_provider",
        execution_target="remote_assist",
        required_permission=permission,
        evidence={
            "produces_evidence": True,
            "kind": "remote_assist.session",
            "domain": "remote_assist",
            "perspective": "remote_assist",
            "passport_eligible": True,
        },
    )


def _session(session_id: str, *, mode: str, status: str, consent_status: str = "pending") -> SimpleNamespace:
    now = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=session_id,
        ticket_id="ticket-1",
        device_id="device-1",
        operator_id="support-1",
        requester_id=None,
        mode=mode,
        status=status,
        reason="diagnostic check",
        consent_required=True,
        consent_status=consent_status,
        requested_at=now,
        approved_at=None,
        denied_at=None,
        started_at=now if status in {"active", "ended"} else None,
        ended_at=now if status == "ended" else None,
        expires_at=now,
        max_duration_sec=900,
        ice_config={"ice_servers": [], "media": {}, "features": {}},
        close_reason="finished" if status == "ended" else None,
        error_code=None,
        error_message=None,
    )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_remote_assist_request_view_uses_session_service_boundary_and_maps_evidence():
    calls = []

    async def request_session(**kwargs):
        calls.append(kwargs)
        return _session("session-view", mode=kwargs["mode"], status="waiting_consent")

    async def send_request(remote_session, **kwargs):
        assert remote_session.id == "session-view"
        return "command-1"

    provider = RemoteAssistCapabilityProvider(session_requester=request_session, request_sender=send_request)

    result = await provider.run(
        _capability("remote_assist.request_view"),
        ticket_id="ticket-1",
        device_id="device-1",
        actor=SimpleNamespace(actor_id="support-1"),
        params={"reason": "diagnostic check"},
    )

    assert calls[0]["mode"] == "view_only"
    assert result["status"] == "created"
    assert result["session_id"] == "session-view"
    assert result["command_id"] == "command-1"
    assert result["diagnostic_status"] == "warning"
    assert result["output"]["mode"] == "view_only"
    assert result["evidence_preview"]["kind"] == "remote_assist.session"
    assert result["evidence_preview"]["status"] == "warning"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_remote_assist_request_control_uses_interactive_control_mode():
    calls = []

    async def request_session(**kwargs):
        calls.append(kwargs)
        return _session("session-control", mode=kwargs["mode"], status="waiting_consent")

    async def send_request(remote_session, **kwargs):
        return "command-control"

    provider = RemoteAssistCapabilityProvider(session_requester=request_session, request_sender=send_request)

    result = await provider.run(
        _capability("remote_assist.request_control", permission="remote_assist.control"),
        ticket_id="ticket-1",
        device_id="device-1",
        actor=SimpleNamespace(actor_id="support-1"),
        params={},
    )

    assert calls[0]["mode"] == "interactive_control"
    assert result["status"] == "created"
    assert result["summary"] == "Remote Assist session requested: interactive_control"
    assert result["output"]["mode"] == "interactive_control"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_remote_assist_session_summary_returns_counts_latest_and_evidence_preview():
    async def list_sessions(ticket_id, limit):
        assert ticket_id == "ticket-1"
        assert limit == 20
        return [
            _session("session-ended", mode="view_only", status="ended", consent_status="approved"),
            _session("session-active", mode="interactive_control", status="active", consent_status="approved"),
            _session("session-denied", mode="view_only", status="denied", consent_status="denied"),
        ]

    provider = RemoteAssistCapabilityProvider(sessions_loader=list_sessions)

    result = await provider.run(
        _capability("remote_assist.session.summary", permission="remote_assist.view"),
        ticket_id="ticket-1",
        params={"limit": 20},
    )

    assert result["status"] == "success"
    assert result["diagnostic_status"] == "warning"
    assert result["output"]["counts"] == {"total": 3, "active": 1, "completed": 1, "denied": 1, "failed": 0}
    assert result["output"]["latest_session"]["session_id"] == "session-ended"
    assert result["summary"] == "Remote Assist sessions: 3 total, 1 active"
    assert result["evidence_preview"]["kind"] == "remote_assist.session"
    assert result["evidence_preview"]["status"] == "warning"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_remote_assist_unknown_capability_is_not_routed_to_session_service():
    calls = []

    async def request_session(**kwargs):
        calls.append(kwargs)
        return _session("session-unexpected", mode="view_only", status="waiting_consent")

    provider = RemoteAssistCapabilityProvider(session_requester=request_session)

    result = await provider.run(_capability("remote_assist.unknown"), ticket_id="ticket-1", device_id="device-1")

    assert result["status"] == "unsupported"
    assert result["error_code"] == "CAPABILITY_TARGET_UNSUPPORTED"
    assert calls == []
