from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.no_db


def test_notification_projection_is_explicit_json_and_has_safe_link():
    from tickets.browser_notifications import notification_to_dict

    row = SimpleNamespace(id=19, ticket_id="ticket-1", event_type="chat_message", payload={"text": "private text", "ticket_code": "T-000077"}, is_read=False, created_at=None, read_at=None)
    result = notification_to_dict(row, requester=True)
    assert result["title"] == "Новое сообщение по обращению T-000077"
    assert result["url"] == "/app/requester/tickets/ticket-1"
    assert "private text" not in str(result)
    assert result["id"] == 19


@pytest.mark.asyncio
async def test_event_notifications_use_initiator_and_existing_recipient_policy(monkeypatch):
    from tickets import browser_notifications as module

    notify = AsyncMock()
    monkeypatch.setattr(module, "notify_ticket_event", notify)
    repo = SimpleNamespace(session=object(), get_ticket=AsyncMock(return_value=SimpleNamespace(ticket_code="T-000077")))
    await module.enqueue_event_notifications(repo, "ticket-1", 37, "chat_message", {"sender_actor_id": "support-1", "visibility": "internal"})
    assert notify.await_args.kwargs["initiator_id"] == "support-1"
    assert notify.await_args.kwargs["visibility"] == "internal"
    assert notify.await_args.kwargs["payload"]["source_event_id"] == 37


@pytest.mark.asyncio
async def test_unrelated_event_does_not_recurse_into_notification_service(monkeypatch):
    from tickets import browser_notifications as module

    notify = AsyncMock()
    monkeypatch.setattr(module, "notify_ticket_event", notify)
    await module.enqueue_event_notifications(SimpleNamespace(session=None), "t", 1, "external_notification_delivery", {})
    notify.assert_not_awaited()
