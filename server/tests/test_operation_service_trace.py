from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import Device, Ticket
from app.services.operation_service import OperationService


@pytest.mark.asyncio
async def test_enqueue_operation_uses_canonical_ticket_root_trace_for_ticket_bound_work():
    now = datetime.now(timezone.utc)
    ticket_id = "00000000-0000-0000-0000-00000000f501"
    device_id = "00000000-0000-0000-0000-00000000f502"
    root_trace_id = "00000000-0000-0000-0000-00000000f503"
    operation_id = "00000000-0000-0000-0000-00000000f504"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.18",
                hostname="operation-trace-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OPTRACE01",
                device_id=device_id,
                title="Operation trace convergence",
                description="Ticket-bound operations must use the canonical observer root trace",
                status="in_progress",
                created_at=now - timedelta(minutes=10),
                updated_at=now,
                observer_root_trace_id=root_trace_id,
            )
        )
        await session.commit()

    async with get_session() as session:
        service = OperationService(session)
        operation = await service.enqueue_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            actor_role="support",
            trace_id="11111111-1111-1111-1111-111111111111",
            ticket_id=ticket_id,
            tool_name="system.collect",
        )
        await session.commit()
        assert operation.trace_id == root_trace_id
