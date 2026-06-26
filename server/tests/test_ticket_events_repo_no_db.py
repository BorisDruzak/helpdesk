from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.repos.ticket_events_repo import TicketEventsRepo

pytestmark = pytest.mark.no_db


class _ScalarRows:
    def all(self) -> list[object]:
        return []


class _ExecuteResult:
    def scalars(self) -> _ScalarRows:
        return _ScalarRows()


class _NoDuplicateResult:
    def scalar_one_or_none(self) -> None:
        return None


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ExecuteResult()


class _IntegrityConflictSession:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name
        self.execute_count = 0
        self.rollback_called = False

    async def execute(self, statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return _NoDuplicateResult()
        raise IntegrityError(
            statement="INSERT INTO ticket_events",
            params={},
            orig=RuntimeError(
                f'duplicate key value violates unique constraint "{self.constraint_name}"'
            ),
        )

    async def rollback(self) -> None:
        self.rollback_called = True


def _compiled_order_by(statement) -> list[str]:
    dialect = postgresql.dialect()
    return [str(clause.compile(dialect=dialect)) for clause in statement._order_by_clauses]


@pytest.mark.asyncio
async def test_get_events_orders_timeline_by_created_at_before_agent_seq() -> None:
    session = _CapturingSession()

    await TicketEventsRepo(session).get_events("ticket-1", since_agent_seq=None, limit=200)

    assert session.statement is not None
    assert _compiled_order_by(session.statement)[:2] == [
        "ticket_events.created_at ASC",
        "ticket_events.id ASC",
    ]


def test_ticket_events_server_idempotency_unique_indexes_are_migrated() -> None:
    migrations_dir = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions"
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in migrations_dir.glob("*.py")
    )

    assert "uq_ticket_events_server_event_id" in migration_text
    assert "uq_ticket_events_server_message_id" in migration_text
    assert "agent_seq IS NULL" in migration_text
    assert "payload ->> 'message_id'" in migration_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("constraint_name", "event_id", "payload"),
    [
        ("uq_ticket_events_server_event_id", "event-1", {"text": "hello"}),
        ("uq_ticket_events_server_message_id", None, {"message_id": "msg-1", "text": "hello"}),
    ],
)
async def test_add_event_treats_server_idempotency_unique_conflicts_as_duplicates(
    monkeypatch: pytest.MonkeyPatch,
    constraint_name: str,
    event_id: str | None,
    payload: dict[str, str],
) -> None:
    async def _resolve_trace(*args, **kwargs) -> str:
        return "trace-1"

    monkeypatch.setattr(TicketEventsRepo, "resolve_ticket_trace_id", _resolve_trace)
    session = _IntegrityConflictSession(constraint_name)

    result = await TicketEventsRepo(session).add_event(
        ticket_id="ticket-1",
        device_id="device-1",
        agent_seq=None,
        event_type="chat_message",
        payload=payload,
        event_id=event_id,
    )

    assert result is None
    assert session.rollback_called is True
