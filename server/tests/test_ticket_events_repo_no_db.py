from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.repos.ticket_events_repo import TicketEventsRepo

pytestmark = pytest.mark.no_db


class _ScalarRows:
    def all(self) -> list[object]:
        return []


class _ExecuteResult:
    def scalars(self) -> _ScalarRows:
        return _ScalarRows()


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ExecuteResult()


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
