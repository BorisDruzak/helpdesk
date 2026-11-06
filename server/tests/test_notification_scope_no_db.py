from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.repos.notification_repo import NotificationRepo
from tickets import notification_scope as module

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_requester_count_is_scoped_sql_count_without_loading_payloads(monkeypatch):
    from app.repos import notification_repo
    monkeypatch.setattr(notification_repo, "ui_actor_membership_ids", AsyncMock(return_value=("employee",)))
    result = SimpleNamespace(scalar=lambda: 7)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    auth = SimpleNamespace(actor_id="employee", actor_role="user", ticket_scope=None)
    assert await NotificationRepo(session).unread_count("employee", auth_context=auth) == 7
    session.execute.assert_awaited_once()
    stmt = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "count(ticket_notifications.id)" in stmt
    assert "tickets.requester_id = 'employee'" in stmt
    assert "visibility" in stmt and "public" in stmt


@pytest.mark.asyncio
async def test_support_scope_keeps_queue_null_assignee_and_membership_aliases(monkeypatch):
    monkeypatch.setattr(module, "ui_actor_membership_ids", AsyncMock(return_value=("Support", "support")))
    monkeypatch.setattr(module, "unified_queue_enabled", lambda: False)
    auth = SimpleNamespace(actor_id="Support", actor_role="support", ticket_scope=None)
    clause = await module.notification_scope_clause(object(), auth)
    stmt = str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "tickets.queue_id IS NULL" in stmt
    assert "tickets.assignee_id = 'Support'" in stmt
    assert "ticket_queue_members.actor_id IN ('Support', 'support')" in stmt


@pytest.mark.asyncio
async def test_public_ticket_credential_cannot_enumerate_inbox():
    clause = await module.notification_scope_clause(object(), SimpleNamespace(ticket_scope="one-ticket"))
    assert str(clause.compile(dialect=postgresql.dialect())) == "false"


@pytest.mark.asyncio
async def test_scope_uses_only_aliases_granted_by_the_installed_ticket_repository(monkeypatch):
    monkeypatch.setattr(module, "ticket_repo_module", SimpleNamespace())
    assert await module.ui_actor_membership_ids(object(), "Support") == ("Support",)
    resolver = AsyncMock(return_value=("Support", "support"))
    monkeypatch.setattr(module, "ticket_repo_module", SimpleNamespace(ui_actor_membership_ids=resolver))
    assert await module.ui_actor_membership_ids(object(), "Support") == ("Support", "support")
