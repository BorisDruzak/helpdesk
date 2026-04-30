"""
Stage 8: Notification Preferences, Problem/Change Hardening — unit and integration tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from tickets.problems_statuses import (
    PROBLEM_STATUSES,
    PROBLEM_TRANSITIONS,
    normalize_problem_status,
    validate_problem_transition,
)
from app.repos.notification_prefs_repo import (
    DEFAULT_MUTE_INTERNAL,
    DEFAULT_MUTED_EVENT_TYPES,
    DEFAULT_SUPPRESS_SELF,
    NotificationPrefsRepo,
)


class TestProblemsStatuses:
    """Unit tests для problems_statuses FSM."""

    def test_normalize_valid(self):
        assert normalize_problem_status("New") == ("New", False)
        assert normalize_problem_status("Investigating") == ("Investigating", False)
        assert normalize_problem_status("new") == ("New", True)  # case change -> normalized
        assert normalize_problem_status("  Mitigated  ") == ("Mitigated", False)  # strip only, case match

    def test_normalize_invalid(self):
        assert normalize_problem_status("") == (None, False)
        assert normalize_problem_status(None) == (None, False)
        assert normalize_problem_status("Invalid") == (None, False)
        assert normalize_problem_status(123) == (None, False)

    def test_validate_transitions(self):
        assert validate_problem_transition("New", "Investigating") is True
        assert validate_problem_transition("Investigating", "Mitigated") is True
        assert validate_problem_transition("Investigating", "Resolved") is True
        assert validate_problem_transition("Resolved", "Closed") is True
        assert validate_problem_transition("Resolved", "Investigating") is True  # reopen
        assert validate_problem_transition("Closed", "Investigating") is False
        assert validate_problem_transition("New", "Resolved") is False
        assert validate_problem_transition("New", "New") is False


class TestNotificationPrefsDefaults:
    """Defaults для notification prefs."""

    def test_defaults(self):
        assert DEFAULT_MUTE_INTERNAL is False
        assert DEFAULT_MUTED_EVENT_TYPES == []
        assert DEFAULT_SUPPRESS_SELF is True


@pytest.mark.asyncio
async def test_notification_prefs_repo_get_or_default():
    """NotificationPrefsRepo.get_or_default возвращает defaults при отсутствии записи."""
    session = AsyncMock()
    prefs_repo = NotificationPrefsRepo(session)
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mute, muted_types, suppress = await prefs_repo.get_or_default("actor-1")
    assert mute is False
    assert muted_types == []
    assert suppress is True


@pytest.mark.asyncio
async def test_notify_ticket_event_suppress_self():
    """suppress_self блокирует уведомление инициатору."""
    from tickets.notification_service import get_recipients, notify_ticket_event

    ticket_repo = AsyncMock()
    ticket_repo.get_ticket = AsyncMock(return_value=MagicMock(
        queue_id=1, assignee_id=None, requester_id="user-1", device_id="d1"
    ))
    ticket_repo.list_queue_member_actor_ids = AsyncMock(return_value=["support-1"])
    ticket_repo.list_watchers = AsyncMock(return_value=[])

    notif_repo = AsyncMock()
    prefs_repo = AsyncMock()
    prefs_repo.get_or_default = AsyncMock(return_value=(False, [], True))  # suppress_self=True

    await notify_ticket_event(
        ticket_repo, notif_repo, "t1", "status_changed", {},
        visibility="public",
        initiator_id="support-1",
        prefs_repo=prefs_repo,
    )
    # support-1 = initiator, suppress_self=True -> не создаём ему уведомление
    # user-1 = requester, public event -> создаём
    assert notif_repo.create.call_count >= 1
    # Проверяем что support-1 не в create calls
    for call in notif_repo.create.call_args_list:
        assert call.kwargs.get("actor_id") != "support-1"


@pytest.mark.asyncio
async def test_notification_policy_limits_recipients_by_request_template():
    """request_template.notification_policy controls event recipients before prefs filtering."""
    from tickets.notification_service import notify_ticket_event

    ticket_repo = AsyncMock()
    ticket_repo.get_ticket = AsyncMock(return_value=MagicMock(
        queue_id=1,
        assignee_id="assignee-1",
        requester_id="requester-1",
        custom_fields={
            "request_template": {
                "notification_policy": {
                    "on_status_changed": {
                        "requester": True,
                        "assignee": True,
                        "queue": False,
                        "watchers": False,
                    }
                }
            }
        },
    ))
    ticket_repo.list_queue_member_actor_ids = AsyncMock(return_value=["queue-1", "queue-2"])
    ticket_repo.list_watchers = AsyncMock(return_value=[MagicMock(actor_id="watcher-1")])

    notif_repo = AsyncMock()
    prefs_repo = AsyncMock()
    prefs_repo.get_or_default = AsyncMock(return_value=(False, [], False))

    await notify_ticket_event(
        ticket_repo,
        notif_repo,
        "t-policy",
        "status_changed",
        {"status": "in_progress"},
        visibility="public",
        prefs_repo=prefs_repo,
    )

    actor_ids = [call.kwargs["actor_id"] for call in notif_repo.create.call_args_list]
    assert actor_ids == ["assignee-1", "requester-1"]


@pytest.mark.asyncio
async def test_notification_policy_resolves_from_registry_when_snapshot_missing(test_engine):
    """Published notification policy suppresses legacy recipients during lifecycle events."""
    import uuid

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import HelpdeskPolicyAudit, NotificationPolicy, Ticket
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    from app.repos.ticket_events_repo import TicketEventsRepo
    from tickets.notification_service import get_recipients

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "notification_policies"))
        await session.execute(delete(NotificationPolicy))
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="notification",
            code="website_notification_runtime",
            title="Website notification runtime",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={
                "on_status_changed": {
                    "requester": False,
                    "assignee": False,
                    "queue": False,
                    "watchers": False,
                }
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        ticket_id = str(uuid.uuid4())
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Website unavailable",
                description="Registry notification policy check",
                status="in_progress",
                requester_id="requester-1",
                assignee_id="assignee-1",
                ticket_type="incident",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                    }
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        recipients = await get_recipients(
            TicketEventsRepo(session),
            ticket_id,
            "status_changed",
            visibility="public",
        )

    assert recipients == []
