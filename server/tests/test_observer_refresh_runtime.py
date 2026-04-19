from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import Device, DeviceEvent, ObserverTrace, Operation, Ticket, TicketEvent
from observer.service import ObserverOverlayService
from observer.runtime import ObserverRefreshRuntime


async def _wait_until(predicate, *, timeout: float = 3.0, interval: float = 0.05) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition was not met before timeout")


@pytest.mark.asyncio
async def test_observer_refresh_runtime_projects_recent_trace_without_rebuild():
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000fa01"
    ticket_id = "00000000-0000-0000-0000-00000000fb01"
    device_id = "00000000-0000-0000-0000-00000000fc01"
    operation_id = "00000000-0000-0000-0000-00000000fd01"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="observer-runtime-host",
                os="windows",
                capabilities=[],
                tools_version="runtime-t1",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-RUNTIME01",
                device_id=device_id,
                title="Background observer projection",
                description="Projection should appear without explicit search/rebuild",
                status="in_progress",
                created_at=now - timedelta(minutes=5),
                updated_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="support",
                trace_id=trace_id,
                status="running",
                queued_at=now - timedelta(seconds=10),
                sent_at=now - timedelta(seconds=9),
                accepted_at=now - timedelta(seconds=8),
                started_at=now - timedelta(seconds=7),
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_started",
                payload={"tool_name": "system.collect", "call_id": "runtime-call-1"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(seconds=6),
            )
        )
        await session.commit()

    runtime = ObserverRefreshRuntime(
        scan_interval_sec=0.05,
        scan_overlap_sec=1.0,
        bootstrap_lookback_sec=60.0,
        debounce_sec=0.01,
        max_batch=20,
    )
    await runtime.start()
    try:
        async def _trace_exists() -> bool:
            async with get_session() as session:
                projected = await session.get(ObserverTrace, trace_id)
                return projected is not None

        await _wait_until(_trace_exists)

        async with get_session() as session:
            projected = await session.get(ObserverTrace, trace_id)
            assert projected is not None
            assert projected.trace_id == trace_id
            assert projected.operation_id == operation_id
            assert projected.ticket_id == ticket_id
            assert projected.span_count >= 2
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_observer_refresh_runtime_refreshes_existing_trace_after_new_source():
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000fa02"
    ticket_id = "00000000-0000-0000-0000-00000000fb02"
    device_id = "00000000-0000-0000-0000-00000000fc02"
    operation_id = "00000000-0000-0000-0000-00000000fd02"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="observer-runtime-refresh-host",
                os="windows",
                capabilities=[],
                tools_version="runtime-t2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-RUNTIME02",
                device_id=device_id,
                title="Background observer refresh",
                description="Existing trace should refresh after a new committed source event",
                status="in_progress",
                created_at=now - timedelta(minutes=5),
                updated_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="support",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now - timedelta(seconds=12),
                sent_at=now - timedelta(seconds=11),
                accepted_at=now - timedelta(seconds=10),
                started_at=now - timedelta(seconds=9),
                finished_at=now - timedelta(seconds=8),
                result_summary="ok",
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_started",
                payload={"tool_name": "system.collect", "call_id": "runtime-call-2"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(seconds=9),
            )
        )
        await session.commit()

    async with get_session() as session:
        service = ObserverOverlayService(session)
        projected = await service.project_trace(trace_id, force=True)
        assert projected is not None
        await session.commit()

    async with get_session() as session:
        before = await session.get(ObserverTrace, trace_id)
        assert before is not None
        before_updated_at = before.updated_at

    runtime = ObserverRefreshRuntime(
        scan_interval_sec=0.05,
        scan_overlap_sec=1.0,
        bootstrap_lookback_sec=60.0,
        debounce_sec=0.01,
        max_batch=20,
    )
    await runtime.start()
    try:
        event_created_at = datetime.now(timezone.utc)
        async with get_session() as session:
            session.add(
                DeviceEvent(
                    device_id=device_id,
                    device_seq=1,
                    event_type="command_result",
                    payload={"status": "succeeded", "tool_name": "system.collect"},
                    trace_id=trace_id,
                    operation_id=operation_id,
                    created_at=event_created_at,
                )
            )
            await session.commit()

        async def _trace_refreshed() -> bool:
            async with get_session() as session:
                service = ObserverOverlayService(session)
                detail = await service.get_trace_detail(trace_id)
                if not detail:
                    return False
                return "device.command_result" in {span["name"] for span in detail["spans"]}

        await _wait_until(_trace_refreshed)

        async with get_session() as session:
            refreshed = await session.get(ObserverTrace, trace_id)
            assert refreshed is not None
            assert refreshed.updated_at is not None
            assert refreshed.updated_at >= before_updated_at
            service = ObserverOverlayService(session)
            detail = await service.get_trace_detail(trace_id)
            assert detail is not None
            span_names = {span["name"] for span in detail["spans"]}
            assert "device.command_result" in span_names
    finally:
        await runtime.stop()
