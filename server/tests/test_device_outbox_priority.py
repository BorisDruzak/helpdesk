from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.device_outbox_repo import DeviceOutboxRepo


pytestmark = pytest.mark.db_cleanup("agent_runtime")

async def _set_created_at(repo: DeviceOutboxRepo, outbox_id: int, created_at: datetime) -> None:
    entry = await repo.get_by_id(outbox_id)
    assert entry is not None
    entry.created_at = created_at


@pytest.mark.asyncio
async def test_pending_commands_prioritize_cancel_update_and_control_lanes(test_engine):
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    base_time = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        run_tool_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="run_tool",
            params={"tool_name": "observer_canary.sleep"},
        )
        get_status_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="get_status",
            params={},
        )
        update_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="update",
            params={"version": "3.1.20"},
        )
        cancel_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="cancel_operation",
            params={"operation_id": str(uuid.uuid4())},
        )
        await _set_created_at(repo, run_tool_id, base_time)
        await _set_created_at(repo, get_status_id, base_time + timedelta(seconds=1))
        await _set_created_at(repo, update_id, base_time + timedelta(seconds=2))
        await _set_created_at(repo, cancel_id, base_time + timedelta(seconds=3))
        await session.commit()

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        pending = await repo.get_pending_commands(device_id=device_id, limit=10)

    assert [entry.command for entry in pending] == [
        "cancel_operation",
        "update",
        "get_status",
        "run_tool",
    ]


@pytest.mark.asyncio
async def test_pending_commands_preserve_fifo_inside_each_priority_lane(test_engine):
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    base_time = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        get_history_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="get_history",
            params={},
        )
        list_tools_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="list_tools",
            params={},
        )
        run_tool_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="run_tool",
            params={"tool_name": "observer_canary.sleep"},
        )
        start_job_id = await repo.enqueue_command(
            device_id=device_id,
            command_id=str(uuid.uuid4()),
            command="start_job",
            params={},
        )
        await _set_created_at(repo, get_history_id, base_time + timedelta(seconds=4))
        await _set_created_at(repo, list_tools_id, base_time + timedelta(seconds=5))
        await _set_created_at(repo, run_tool_id, base_time + timedelta(seconds=6))
        await _set_created_at(repo, start_job_id, base_time + timedelta(seconds=7))
        await session.commit()

    async with session_maker() as session:
        repo = DeviceOutboxRepo(session)
        pending = await repo.get_pending_commands(device_id=device_id, limit=10)

    assert [entry.command for entry in pending] == [
        "get_history",
        "list_tools",
        "run_tool",
        "start_job",
    ]
