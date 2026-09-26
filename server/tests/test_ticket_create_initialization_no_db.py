from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tickets import create_flow

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_stage", ["routing", "sla", "ola", None])
async def test_create_initialization_stops_at_failed_required_stage(monkeypatch, failed_stage):
    ticket = SimpleNamespace(ticket_id="create-fault-probe", device_id=None, status="assigned")
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket))
    stages = {
        stage: AsyncMock(side_effect=RuntimeError("private dependency details") if stage == failed_stage else None)
        for stage in ("routing", "sla", "ola")
    }
    monkeypatch.setattr(create_flow, "DevicesRepo", lambda session: object())
    monkeypatch.setattr(create_flow, "TicketRoutingService", lambda *args: SimpleNamespace(apply_routing=stages["routing"]))
    monkeypatch.setattr(create_flow, "TicketSlaService", lambda *args: SimpleNamespace(start_sla=stages["sla"]))
    monkeypatch.setattr(create_flow, "start_ola_for_ticket", stages["ola"])
    approval = AsyncMock(return_value=ticket)
    monkeypatch.setattr(create_flow, "_enter_initial_approval_wait_if_required", approval)

    if failed_stage is None:
        assert await create_flow.apply_create_side_effects(object(), repo, ticket) is ticket
        assert all(stage.await_count == 1 for stage in stages.values())
        approval.assert_awaited_once()
    else:
        with pytest.raises(RuntimeError, match="Ticket initialization unavailable") as caught:
            await create_flow.apply_create_side_effects(object(), repo, ticket)
        assert "private dependency details" not in str(caught.value)
        assert caught.value.stage == failed_stage
        approval.assert_not_awaited()
        order = list(stages)
        assert all(stages[stage].await_count == 0 for stage in order[order.index(failed_stage) + 1:])
