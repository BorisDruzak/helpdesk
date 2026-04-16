from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.operations_repo import OperationsRepo
from websocket.protocol import enqueue_command_async


@pytest.mark.asyncio
async def test_enqueue_command_async_creates_missing_operation_for_precreated_operation_id(
    test_client,
    test_engine,
):
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="enqueue-device",
                os="win32",
                capabilities={},
                device_metadata={},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    command_id = await enqueue_command_async(
        state=test_client.app["state"],
        device_id=device_id,
        command="install_module_package",
        params={
            "name": "network_basic",
            "version": "1.0.0",
            "download_url": "https://example.invalid/network_basic.zip",
            "sha256": "deadbeef",
        },
        actor_role="system",
        trace_id="trace-precreated-op",
        ticket_id="ticket-precreated-op",
        job_id="job-precreated-op",
        operation_id=operation_id,
        require_online=False,
    )

    assert command_id == operation_id

    async with session_maker() as session:
        operations_repo = OperationsRepo(session)
        outbox_repo = DeviceOutboxRepo(session)

        operation = await operations_repo.get_by_operation_id(operation_id)
        outbox_entry = await outbox_repo.get_command_by_id(operation_id)

        assert operation is not None
        assert operation.operation_id == operation_id
        assert operation.command_name == "install_module_package"
        assert operation.status == "queued"
        assert operation.ticket_id == "ticket-precreated-op"
        assert operation.job_id == "job-precreated-op"

        assert outbox_entry is not None
        assert outbox_entry.operation_id == operation_id
        assert outbox_entry.command == "install_module_package"
