from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _ticket(notification_policy: dict) -> SimpleNamespace:
    return SimpleNamespace(
        ticket_id="t-notify",
        device_id="device-notify",
        queue_id=10,
        assignee_id="assignee-1",
        requester_id="requester-1",
        custom_fields={"request_template": {"notification_policy": notification_policy}},
    )


def _repo(ticket: SimpleNamespace) -> AsyncMock:
    repo = AsyncMock()
    repo.get_ticket = AsyncMock(return_value=ticket)
    repo.list_queue_member_actor_ids = AsyncMock(return_value=["queue-1", "queue-2"])
    repo.list_watchers = AsyncMock(return_value=[SimpleNamespace(actor_id="watcher-1")])
    repo.add_event = AsyncMock(return_value=(1, None))
    return repo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "policy_key", "expected"),
    [
        ("ticket_created", "on_created", ["requester-1"]),
        ("ticket_assigned", "on_assigned", ["assignee-1"]),
        ("waiting_user", "on_waiting_user", ["requester-1"]),
        ("requester_replied", "on_requester_replied", ["assignee-1"]),
        ("sla_warning", "on_sla_warning", ["assignee-1"]),
        ("sla_breached", "on_sla_breach", ["assignee-1"]),
        ("resolved", "on_resolved", ["requester-1"]),
        ("closed", "on_closed", ["requester-1"]),
        ("approval_escalated", "on_approval_escalated", ["watcher-1"]),
        ("diagnostic_completed", "on_diagnostic_completed", ["assignee-1"]),
    ],
)
async def test_notification_policy_resolves_canonical_event_blocks(event_type, policy_key, expected):
    from tickets.notification_service import get_recipients

    recipients = await get_recipients(
        _repo(
            _ticket(
                {
                    policy_key: {
                        "requester": "requester-1" in expected,
                        "assignee": "assignee-1" in expected,
                        "queue": False,
                        "watchers": "watcher-1" in expected,
                    }
                }
            )
        ),
        "t-notify",
        event_type,
        visibility="public",
    )

    assert recipients == expected


@pytest.mark.asyncio
async def test_external_channel_validation_audits_disabled_unavailable_and_unknown_channels():
    from tickets.notification_service import notify_ticket_event

    class Provider:
        available_channels = {"email"}

        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def send(self, **kwargs):
            self.calls.append(kwargs)
            return {"status": "sent", "provider_message_id": f"{kwargs['channel']}-1"}

    ticket_repo = _repo(
        _ticket(
            {
                "channels": {"web": True, "email": True, "telegram": False, "vk_teams": True, "sms": True},
                "on_status_changed": {
                    "requester": True,
                    "queue": False,
                    "watchers": False,
                    "channels": {"telegram": True, "vk_teams": False, "sms": True},
                },
            }
        )
    )
    notif_repo = AsyncMock()
    prefs_repo = AsyncMock()
    prefs_repo.get_or_default = AsyncMock(return_value=(False, [], False))
    provider = Provider()

    await notify_ticket_event(
        ticket_repo,
        notif_repo,
        "t-notify",
        "status_changed",
        {"status": "resolved"},
        visibility="public",
        prefs_repo=prefs_repo,
        channel_provider=provider,
    )

    notif_repo.create.assert_called_once()
    assert [call["channel"] for call in provider.calls] == ["email"]
    audit_payloads = [call.kwargs["payload"] for call in ticket_repo.add_event.call_args_list]
    assert [(payload["channel"], payload["delivery_status"], payload.get("reason")) for payload in audit_payloads] == [
        ("email", "sent", None),
        ("telegram", "skipped", "channel_unavailable"),
        ("vk_teams", "skipped", "channel_disabled"),
        ("sms", "skipped", "channel_unavailable"),
    ]


@pytest.mark.asyncio
async def test_notification_preferences_remain_final_filter_for_in_app_and_external_delivery():
    from tickets.notification_service import notify_ticket_event

    class Provider:
        async def send(self, **kwargs):
            raise AssertionError(f"muted actor must not receive external delivery: {kwargs}")

    ticket_repo = _repo(
        _ticket(
            {
                "channels": {"email": True},
                "on_status_changed": {
                    "requester": True,
                    "queue": False,
                    "watchers": False,
                    "channels": {"email": True},
                },
            }
        )
    )
    notif_repo = AsyncMock()
    prefs_repo = AsyncMock()
    prefs_repo.get_or_default = AsyncMock(return_value=(False, ["status_changed"], False))

    await notify_ticket_event(
        ticket_repo,
        notif_repo,
        "t-notify",
        "status_changed",
        {"status": "resolved"},
        visibility="public",
        prefs_repo=prefs_repo,
        channel_provider=Provider(),
    )

    notif_repo.create.assert_not_called()
    ticket_repo.add_event.assert_not_called()
