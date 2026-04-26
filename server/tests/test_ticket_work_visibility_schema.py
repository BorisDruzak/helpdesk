from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, select

from app.db.engine import async_sessionmaker
from app.db.models import Ticket


@pytest.mark.asyncio
async def test_ticket_work_visibility_schema_contract(test_engine):
    async with test_engine.begin() as connection:
        schema = await connection.run_sync(
            lambda sync_connection: {
                "ticket_columns": {
                    column["name"]: column
                    for column in inspect(sync_connection).get_columns("tickets")
                },
                "tables": set(inspect(sync_connection).get_table_names()),
                "wait_columns": {
                    column["name"]: column
                    for column in inspect(sync_connection).get_columns("ticket_waits")
                },
                "wait_indexes": {
                    index["name"]: index
                    for index in inspect(sync_connection).get_indexes("ticket_waits")
                },
            }
        )

    ticket_columns = schema["ticket_columns"]
    for column_name in (
        "next_action_owner",
        "next_action_due_at",
        "status_reason",
        "requester_status",
        "resolution_summary",
        "requester_resolution_summary",
        "evidence_required",
        "evidence_ref",
        "closure_feedback",
        "canceled_at",
    ):
        assert column_name in ticket_columns

    assert ticket_columns["next_action_owner"]["nullable"] is False
    assert ticket_columns["requester_status"]["nullable"] is False
    assert ticket_columns["evidence_required"]["nullable"] is False
    assert "ticket_waits" in schema["tables"]

    wait_columns = schema["wait_columns"]
    for column_name in (
        "id",
        "ticket_id",
        "wait_type",
        "started_at",
        "ended_at",
        "reason",
        "related_party",
        "created_by",
        "closed_by",
        "payload",
    ):
        assert column_name in wait_columns

    assert schema["wait_indexes"]["ix_ticket_waits_ticket_active"]["column_names"] == [
        "ticket_id",
        "ended_at",
    ]
    assert schema["wait_indexes"]["ix_ticket_waits_type_active"]["column_names"] == [
        "wait_type",
        "ended_at",
    ]


@pytest.mark.asyncio
async def test_ticket_work_visibility_fields_round_trip(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    due_at = datetime.now(timezone.utc)

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=str(uuid.uuid4()),
            title="Schema visibility",
            description="Ticket should persist work visibility metadata",
            status="waiting_on_internal_team",
            requester_id="requester-a",
            next_action_owner="internal_team",
            next_action_due_at=due_at,
            status_reason="network_team",
            requester_status="in_work",
            resolution_summary="Reconfigured network route",
            requester_resolution_summary="Connection restored",
            evidence_required=True,
            evidence_ref="trace:abc",
            closure_feedback={"result": "helped"},
        )
        session.add(ticket)
        await session.flush()
        await session.execute(
            sa.text(
                """
                INSERT INTO ticket_waits (
                    ticket_id,
                    wait_type,
                    started_at,
                    reason,
                    related_party,
                    created_by,
                    payload
                )
                VALUES (
                    :ticket_id,
                    'internal_team',
                    :started_at,
                    'network_team',
                    'network',
                    'support-test',
                    CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "ticket_id": ticket_id,
                "started_at": due_at,
                "payload": '{"ola_due_at":"soon"}',
            },
        )
        await session.commit()

    async with session_maker() as session:
        result = await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ticket = result.scalar_one()
        wait_result = await session.execute(
            sa.text(
                """
                SELECT wait_type, reason, related_party, payload
                FROM ticket_waits
                WHERE ticket_id = :ticket_id AND ended_at IS NULL
                """
            ),
            {"ticket_id": ticket_id},
        )
        wait_row = wait_result.mappings().one()

    assert ticket.next_action_owner == "internal_team"
    assert ticket.status_reason == "network_team"
    assert ticket.requester_status == "in_work"
    assert ticket.evidence_required is True
    assert ticket.evidence_ref == "trace:abc"
    assert ticket.closure_feedback == {"result": "helped"}
    assert wait_row["wait_type"] == "internal_team"
    assert wait_row["reason"] == "network_team"
    assert wait_row["related_party"] == "network"
    assert wait_row["payload"] == {"ola_due_at": "soon"}
