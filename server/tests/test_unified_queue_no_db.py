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
async def test_unified_routing_uses_common_queue_without_evaluating_partition_rules(monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    repo = SimpleNamespace(get_queue_by_code=AsyncMock(return_value=SimpleNamespace(id=7, is_active=True)))
    routing = TicketRoutingService(None, repo, None)
    decision = await routing.resolve_routing_decision(SimpleNamespace(device_id=None))
    assert decision["queue_id"] == 7 and decision["source"] == "unified_queue"
    repo.get_queue_by_code.assert_awaited_once_with(config.TICKET_TAKE_QUEUE_COMMON_CODE)
    repo.get_ticket = AsyncMock(return_value=SimpleNamespace(queue_id=2))
    assert await routing.apply_routing("existing", None) == 2


@pytest.mark.asyncio
async def test_unified_auto_assignment_keeps_common_queue_policy_and_global_candidates(monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    queue = SimpleNamespace(auto_assign_enabled=False)
    repo = SimpleNamespace(get_queue_by_code=AsyncMock(return_value=queue), select_assignee_for_update=AsyncMock(return_value="support1"), count_active_tickets_for_assignee=AsyncMock(return_value=0))
    service = TicketAssignmentService(repo)
    with pytest.raises(TicketAssignmentError):
        await service.resolve_assignee(SimpleNamespace(queue_id=99), requested_assignee_id=None, auto_assign=True)
    repo.select_assignee_for_update.assert_not_awaited()
    queue.auto_assign_enabled = True
    result = await service.resolve_assignee(SimpleNamespace(queue_id=99), requested_assignee_id=None, auto_assign=True)
    assert result["assignee_id"] == "support1"
    repo.select_assignee_for_update.assert_awaited_once_with(3, queue_id=None)
