from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AgentRuntimeAudit, Device, Operation
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.services.operation_service import OperationService
from websocket.device_outbox_sender import _sync_operation_delivery_state


class _StateStub:
    ui_publisher = None


async def _seed_device(session, *, device_id: str) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        Device(
            device_id=device_id,
            protocol_version="ws_ticket_v3",
            agent_version="3.1.19",
            hostname="retry-sync-host",
            os="windows",
            capabilities={},
            device_metadata={"os_type": "windows"},
            first_seen_at=now,
            last_seen_at=now,
            last_handshake_at=now,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_retry_sync_updates_operation_retry_count_and_runtime_audit(test_engine):
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        op_service = OperationService(session, publisher=None)
        await op_service.enqueue_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            tool_name="observer_canary.sleep",
            actor_role="admin",
            trace_id=str(uuid.uuid4()),
            max_retries=2,
        )
        repo = DeviceOutboxRepo(session)
        outbox_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=operation_id,
            command="run_tool",
            params={"tool_name": "observer_canary.sleep"},
            trace_id=str(uuid.uuid4()),
            actor_role="admin",
            max_retries=2,
            operation_id=operation_id,
        )
        await session.commit()

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        assert await repo.mark_as_failed(
            outbox_id=outbox_id,
            error_code="SEND_ERROR",
            error_message="socket write failed",
            should_retry=True,
        )
        outbox_entry = await repo.get_by_id(outbox_id)
        assert outbox_entry is not None
        await _sync_operation_delivery_state(
            state_manager=_StateStub(),
            repo=repo,
            outbox_entry=outbox_entry,
            error_code="SEND_ERROR",
            error_message="socket write failed",
        )
        await session.commit()

    async with session_maker() as session:
        operation = (
            await session.execute(select(Operation).where(Operation.operation_id == operation_id))
        ).scalar_one()
        assert operation.status == "queued"
        assert operation.retry_count == 1

        audits = (
            await session.execute(
                select(AgentRuntimeAudit)
                .where(
                    AgentRuntimeAudit.device_id == device_id,
                    AgentRuntimeAudit.operation_id == operation_id,
                )
                .order_by(AgentRuntimeAudit.id.asc())
            )
        ).scalars().all()
        assert any(item.event_type == "command_retry_scheduled" for item in audits)


@pytest.mark.asyncio
async def test_retry_exhaustion_marks_operation_failed_and_writes_runtime_audit(test_engine):
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        op_service = OperationService(session, publisher=None)
        await op_service.enqueue_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            tool_name="observer_canary.sleep",
            actor_role="admin",
            trace_id=str(uuid.uuid4()),
            max_retries=1,
        )
        repo = DeviceOutboxRepo(session)
        outbox_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=operation_id,
            command="run_tool",
            params={"tool_name": "observer_canary.sleep"},
            trace_id=str(uuid.uuid4()),
            actor_role="admin",
            max_retries=1,
            operation_id=operation_id,
        )
        await session.commit()

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        assert await repo.mark_as_failed(
            outbox_id=outbox_id,
            error_code="SEND_ERROR",
            error_message="first delivery failure",
            should_retry=True,
        )
        outbox_entry = await repo.get_by_id(outbox_id)
        assert outbox_entry is not None
        await _sync_operation_delivery_state(
            state_manager=_StateStub(),
            repo=repo,
            outbox_entry=outbox_entry,
            error_code="SEND_ERROR",
            error_message="first delivery failure",
        )
        await session.commit()

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        assert await repo.mark_as_failed(
            outbox_id=outbox_id,
            error_code="SEND_ERROR",
            error_message="second delivery failure",
            should_retry=True,
        )
        outbox_entry = await repo.get_by_id(outbox_id)
        assert outbox_entry is not None
        await _sync_operation_delivery_state(
            state_manager=_StateStub(),
            repo=repo,
            outbox_entry=outbox_entry,
            error_code="SEND_ERROR",
            error_message="second delivery failure",
        )
        await session.commit()

    async with session_maker() as session:
        operation = (
            await session.execute(select(Operation).where(Operation.operation_id == operation_id))
        ).scalar_one()
        assert operation.retry_count == 1
        assert operation.status == "failed"
        assert operation.error_code == "DELIVERY_RETRY_EXHAUSTED"
        assert "second delivery failure" in str(operation.error_message or "")

        audits = (
            await session.execute(
                select(AgentRuntimeAudit)
                .where(
                    AgentRuntimeAudit.device_id == device_id,
                    AgentRuntimeAudit.operation_id == operation_id,
                )
                .order_by(AgentRuntimeAudit.id.asc())
            )
        ).scalars().all()
        assert any(item.event_type == "command_retry_scheduled" for item in audits)
        assert any(item.event_type == "command_delivery_failed" for item in audits)
