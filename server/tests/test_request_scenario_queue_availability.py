"""Published scenario preview rejects an unavailable current routing target."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tickets import service_catalog_preview as module

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("queue", [None, SimpleNamespace(is_active=False), SimpleNamespace(is_active=True)])
async def test_scenario_preview_revalidates_current_queue_without_ticket_writes(monkeypatch, queue):
    simulation = {"routing": {"queue_id": 9, "queue_code": "configured"}}
    monkeypatch.setattr(module, "simulate_service_catalog_processing", AsyncMock(return_value=(SimpleNamespace(service={}, offering={}), simulation)))
    session = SimpleNamespace(scalar=AsyncMock(return_value=queue), add=AsyncMock(), flush=AsyncMock(), commit=AsyncMock())
    result = await module.build_requester_service_catalog_preview(session, {}, scenario_snapshot={"version_id": "pinned"})
    assert result["ok"] is bool(queue and queue.is_active)
    assert bool(result["blockers"]) is not result["ok"]
    assert "configured" not in str(result) and "queue_id" not in result
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_preview_keeps_existing_route_behavior(monkeypatch):
    monkeypatch.setattr(module, "simulate_service_catalog_processing", AsyncMock(return_value=(SimpleNamespace(service={}, offering={}), {"routing": {"queue_id": 9}})))
    session = SimpleNamespace(scalar=AsyncMock(side_effect=AssertionError("No scenario queue check expected")))
    assert (await module.build_requester_service_catalog_preview(session, {}))["ok"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
async def test_actual_scenario_routing_is_checked_before_other_initialization(monkeypatch, active):
    from tickets import create_flow

    ticket = SimpleNamespace(ticket_id="scenario-route", device_id=None, queue_id=9, status="assigned")
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(is_active=active)))
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket))
    routing, sla, ola = AsyncMock(), AsyncMock(), AsyncMock()
    approval = AsyncMock(return_value=ticket)
    monkeypatch.setattr(create_flow, "DevicesRepo", lambda session: object())
    monkeypatch.setattr(create_flow, "TicketRoutingService", lambda *args: SimpleNamespace(apply_routing=routing))
    monkeypatch.setattr(create_flow, "TicketSlaService", lambda *args: SimpleNamespace(start_sla=sla))
    monkeypatch.setattr(create_flow, "start_ola_for_ticket", ola)
    monkeypatch.setattr(create_flow, "_enter_initial_approval_wait_if_required", approval)
    if active:
        assert await create_flow.apply_create_side_effects(session, repo, ticket, require_active_queue=True) is ticket
        sla.assert_awaited_once()
        ola.assert_awaited_once()
        approval.assert_awaited_once()
    else:
        with pytest.raises(create_flow.TicketInitializationError) as caught:
            await create_flow.apply_create_side_effects(session, repo, ticket, require_active_queue=True)
        assert caught.value.stage == "scenario_queue"
        sla.assert_not_awaited()
        ola.assert_not_awaited()
        approval.assert_not_awaited()
    routing.assert_awaited_once()
