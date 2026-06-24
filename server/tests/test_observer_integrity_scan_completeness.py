from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Operation, Ticket, TicketEvent
from observer.checks.operation_lifecycle import QUERY_LIMIT as OPERATION_QUERY_LIMIT
from observer.checks.operation_lifecycle import check_operation_lifecycle
from observer.checks.runtime_presence import check_runtime_presence
from observer.checks.types import ObserverIntegrityCheckResult
from observer.checks.web_cabinet import check_web_cabinet


pytestmark = pytest.mark.db_cleanup("full")


class _OnlineState:
    def is_agent_online(self, _device_id: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_operation_lifecycle_marks_incomplete_when_limit_plus_one_rows_are_filtered(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for index in range(OPERATION_QUERY_LIMIT + 1):
            operation_id = f"obs-limit-op-{index:03d}"
            ticket_id = f"obs-limit-ticket-{index:03d}"
            finished_at = now - timedelta(seconds=index)
            session.add(
                Operation(
                    operation_id=operation_id,
                    device_id=f"obs-device-{index:03d}",
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="diagnose",
                    actor_role="support",
                    trace_id=f"obs-trace-{index:03d}",
                    status="succeeded",
                    queued_at=finished_at - timedelta(seconds=5),
                    finished_at=finished_at,
                )
            )
            if index < OPERATION_QUERY_LIMIT:
                session.add(
                    TicketEvent(
                        ticket_id=ticket_id,
                        device_id=f"obs-device-{index:03d}",
                        event_type="tool_call_result",
                        payload={},
                        operation_id=operation_id,
                        created_at=finished_at,
                    )
                )
        await session.commit()

    async with session_maker() as session:
        result = await check_operation_lifecycle(session, run_id="operation-limit-plus-one")

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert result.events == []


@pytest.mark.asyncio
async def test_web_cabinet_marks_incomplete_at_ticket_limit_plus_one(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for index in range(301):
            session.add(
                Ticket(
                    ticket_id=f"obs-web-ticket-{index:03d}",
                    title=f"Observer web ticket {index}",
                    description="Observer completeness fixture",
                    status="open",
                    requester_id=f"requester-{index:03d}",
                    requester_account_mode="browser_no_device",
                    custom_fields={"request_context": "requester_portal"},
                    created_at=now - timedelta(seconds=index),
                    updated_at=now - timedelta(seconds=index),
                )
            )
        await session.commit()

    async with session_maker() as session:
        result = await check_web_cabinet(session, run_id="web-limit-plus-one", limit=300)

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert len(result.events) >= 300


@pytest.mark.asyncio
async def test_runtime_presence_marks_incomplete_at_device_limit_plus_one(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    stale = now - timedelta(hours=1)
    async with session_maker() as session:
        for index in range(501):
            session.add(
                Device(
                    device_id=f"obs-runtime-device-{index:03d}",
                    first_seen_at=stale,
                    last_seen_at=stale,
                    last_handshake_at=stale,
                    protocol_version="ws_ticket_v3",
                    agent_version="test",
                    capabilities={},
                )
            )
        await session.commit()

    async with session_maker() as session:
        result = await check_runtime_presence(
            session,
            state=_OnlineState(),
            run_id="runtime-limit-plus-one",
            stale_after=timedelta(minutes=15),
        )

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert len(result.events) == 500
