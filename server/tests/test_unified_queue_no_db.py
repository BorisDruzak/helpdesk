from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import config
from tickets.assignment_service import TicketAssignmentService, TicketAssignmentError
from tickets.routing_service import TicketRoutingService
from tickets.smart_views import _matches_custom_filter

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("unified", [False, True])
def test_queue_filter_switch_preserves_other_saved_view_filters(monkeypatch, unified):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified" if unified else "partitioned")
    ticket = {"queue_code": "legacy", "status": "new"}
    filters = {"queue_code": "another", "status": "new"}
    assert _matches_custom_filter(ticket, filters, now=datetime.now(timezone.utc)) is unified
    filters["status"] = "closed"
    assert _matches_custom_filter(ticket, filters, now=datetime.now(timezone.utc)) is False

@pytest.mark.asyncio
async def test_unified_routing_preserves_policy_actions_and_overrides_only_partition(monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    repo = SimpleNamespace(get_queue_by_code=AsyncMock(return_value=SimpleNamespace(id=7, is_active=True)))
    routing = TicketRoutingService(None, repo, None)
    policy = {"queue_id": 99, "queue_code": "legacy", "minimum_priority": "P1", "sla_policy_id": 4, "approval_policy": {"required": True}}
    routing._resolve_partitioned_routing_decision = AsyncMock(return_value={"source": "request_template.routing_policy", "queue_id": 99, "actions": policy})
    decision = await routing.resolve_routing_decision(SimpleNamespace(device_id=None, queue_id=None))
    assert decision["queue_id"] == 7 and decision["source"] == "unified_queue"
    assert decision["actions"] == {key: value for key, value in policy.items() if key not in {"queue_id", "queue_code"}} | {"queue_id": 7}
    repo.get_queue_by_code.assert_awaited_once_with(config.TICKET_TAKE_QUEUE_COMMON_CODE)
    decision = await routing.resolve_routing_decision(SimpleNamespace(device_id=None, queue_id=2))
    assert decision["queue_id"] == 2 and decision["actions"]["sla_policy_id"] == 4
    repo.get_queue_by_code.assert_awaited_once()


@pytest.mark.asyncio
async def test_unified_existing_ticket_persists_approval_only_policy_without_queue_change(monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    ticket = SimpleNamespace(queue_id=2, custom_fields={}, priority="normal", tags=None)
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket), update_ticket=AsyncMock())
    routing = TicketRoutingService(None, repo, None)
    approval = {"required": True}
    routing.resolve_routing_decision = AsyncMock(return_value={"source": "unified_queue", "queue_id": 2, "actions": {"queue_id": 2, "approval_policy": approval}})
    events = AsyncMock()
    assert await routing.apply_routing("existing", None, add_events_fn=events) == 2
    update = repo.update_ticket.await_args.kwargs
    assert update["queue_id"] == 2
    assert update["custom_fields"]["request_template"]["approval_policy"] == approval
    assert [call.args[2] for call in events.await_args_list] == ["routing_applied"]


@pytest.mark.asyncio
async def test_unified_auto_assignment_keeps_common_queue_policy_and_global_candidates(monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    queue = SimpleNamespace(auto_assign_enabled=False)
    repo = SimpleNamespace(get_queue_by_code=AsyncMock(return_value=queue), select_assignee_for_update=AsyncMock(return_value="support1"), count_active_tickets_for_assignee=AsyncMock(return_value=0))
    ticket = SimpleNamespace(ticket_id="auto-assignment", queue_id=99)
    repo.get_ticket = AsyncMock(return_value=ticket)
    service = TicketAssignmentService(repo)
    with pytest.raises(TicketAssignmentError):
        await service.resolve_assignee(ticket, requested_assignee_id=None, auto_assign=True)
    repo.select_assignee_for_update.assert_not_awaited()
    queue.auto_assign_enabled = True
    result = await service.resolve_assignee(ticket, requested_assignee_id=None, auto_assign=True)
    assert result["assignee_id"] == "support1"
    repo.select_assignee_for_update.assert_awaited_once_with(3, queue_id=None)
