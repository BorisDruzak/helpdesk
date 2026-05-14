from __future__ import annotations

import pytest

from tickets.side_effects import (
    WorkflowSideEffectError,
    get_workflow_side_effect_metric,
    reset_workflow_side_effect_metrics,
    run_workflow_side_effect,
)


pytestmark = pytest.mark.no_db


class FakeTicketRepo:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def add_event(self, **kwargs):
        self.events.append(kwargs)
        return ("event-1", None)


async def _raise_secret_error():
    raise RuntimeError("failed with token=secret-123 and password=hunter2")


@pytest.mark.asyncio
async def test_non_critical_side_effect_failure_is_audited_and_metriced() -> None:
    reset_workflow_side_effect_metrics()
    repo = FakeTicketRepo()
    event_payload: dict = {}

    result = await run_workflow_side_effect(
        ticket_repo=repo,
        ticket_id="ticket-1",
        device_id="device-1",
        side_effect="ola",
        action="pause",
        trigger="status_changed",
        from_status="in_progress",
        to_status="waiting_on_user",
        actor_id="support-1",
        actor_role="support",
        critical=False,
        operation=_raise_secret_error,
        event_payload=event_payload,
        correlation_id="corr-1",
    )

    assert result["status"] == "failed"
    assert result["side_effect"] == "ola"
    assert result["retryable"] is True
    assert "secret-123" not in result["error_message_redacted"]
    assert "hunter2" not in result["error_message_redacted"]
    assert get_workflow_side_effect_metric("ola", "pause") == 1
    assert len(repo.events) == 1
    assert repo.events[0]["event_type"] == "workflow_side_effect_failed"
    payload = repo.events[0]["payload"]
    assert payload["side_effect"] == "ola"
    assert payload["action"] == "pause"
    assert payload["correlation_id"] == "corr-1"
    assert "secret-123" not in str(payload)
    assert event_payload["workflow_side_effect_results"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_critical_side_effect_failure_raises_after_audit() -> None:
    reset_workflow_side_effect_metrics()
    repo = FakeTicketRepo()

    with pytest.raises(WorkflowSideEffectError):
        await run_workflow_side_effect(
            ticket_repo=repo,
            ticket_id="ticket-1",
            device_id="device-1",
            side_effect="approval",
            action="create_request",
            trigger="transition_gate",
            from_status="assigned",
            to_status="waiting_on_approval",
            actor_id="support-1",
            actor_role="support",
            critical=True,
            operation=_raise_secret_error,
        )

    assert get_workflow_side_effect_metric("approval", "create_request") == 1
    assert repo.events[0]["event_type"] == "workflow_side_effect_failed"


def test_no_silent_except_pass_in_workflow_service() -> None:
    path = SERVER_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
    workflow_source = (SERVER_ROOT / "tickets" / "workflow_service.py").read_text(encoding="utf-8")
    assert "except Exception:\n                pass" not in workflow_source


def test_public_session_revocation_uses_workflow_side_effect_observability() -> None:
    server_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    workflow_source = (server_root / "tickets" / "workflow_service.py").read_text(encoding="utf-8")

    assert "side_effect=\"public_session\"" in workflow_source
    assert "action=\"revoke\"" in workflow_source
    assert "failed to revoke public ticket sessions" not in workflow_source
