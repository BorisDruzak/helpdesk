from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import DeviceModule, DeviceOutbox, Operation
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.services.operation_service import OperationService
import websocket.agent_services as agent_services
from websocket.agent_services import CommandAckService, CommandResultService
from websocket.contexts import AgentConnectionContext


async def _create_sent_operation(
    session,
    *,
    operation_id: str,
    device_id: str = "device-lifecycle-1",
    command: str = "install_module_package",
    kind: str = "command",
) -> int:
    outbox_repo = DeviceOutboxRepo(session)
    outbox_id = await outbox_repo.enqueue_command(
        device_id=device_id,
        command_id=operation_id,
        command=command,
        params={},
        request_id=operation_id,
        trace_id="trace-lifecycle-1",
        actor_role="support",
        operation_id=operation_id,
    )
    op_service = OperationService(session)
    await op_service.enqueue_operation(
        operation_id=operation_id,
        device_id=device_id,
        kind=kind,
        command_name=command if kind == "command" else None,
        actor_role="support",
        trace_id="trace-lifecycle-1",
    )
    await outbox_repo.mark_as_sent(outbox_id)
    await op_service.mark_sent(operation_id, expected_statuses=["queued"])
    await session.commit()
    return outbox_id


@pytest.mark.asyncio
async def test_command_result_succeeds_sent_command_and_delivers_outbox(test_client, monkeypatch):
    monkeypatch.setattr(agent_services, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_services, "ENABLE_DB_PERSISTENCE", True)
    operation_id = "11111111-1111-4111-8111-111111111111"

    async with get_session() as session:
        await _create_sent_operation(session, operation_id=operation_id)

    class _State:
        def __init__(self) -> None:
            self.resolved: list[str] = []

        def get_agent(self, _agent_id):
            return None

        def resolve_pending_command_future(self, command_id, _result_data):
            self.resolved.append(command_id)
            return False

    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=_State(),
        agent_id="device-lifecycle-1",
    )

    await CommandResultService().handle(
        {
            "type": "command_result",
            "request_id": operation_id,
            "payload": {
                "status": "success",
                "data": {"observations": {"installed": True}},
                "error": {},
                "meta": {"request_id": operation_id},
            },
        },
        ctx,
    )

    async with get_session() as session:
        operation = await session.get(Operation, operation_id)
        outbox = (
            await session.execute(select(DeviceOutbox).where(DeviceOutbox.operation_id == operation_id))
        ).scalar_one()

    assert operation is not None
    assert operation.status == "succeeded"
    assert operation.finished_at is not None
    assert operation.deadline_at is None
    assert outbox.status == "delivered"


@pytest.mark.asyncio
async def test_install_module_package_result_syncs_device_module_inventory(test_client, monkeypatch):
    monkeypatch.setattr(agent_services, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_services, "ENABLE_DB_PERSISTENCE", True)
    operation_id = "44444444-4444-4444-8444-444444444444"
    device_id = "device-lifecycle-install-sync"

    async with get_session() as session:
        await _create_sent_operation(session, operation_id=operation_id, device_id=device_id)
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name="agent_recipe_runner",
                version="1.0.0",
                installed=False,
                active=False,
                state="missing",
                source="test",
            )
        )
        await session.commit()

    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(get_agent=lambda _agent_id: None),
        agent_id=device_id,
    )

    await CommandResultService().handle(
        {
            "type": "command_result",
            "request_id": operation_id,
            "payload": {
                "status": "success",
                "data": {
                    "observations": {
                        "installed": "agent_recipe_runner",
                        "version": "1.0.0",
                        "path": "/tmp/modules/agent_recipe_runner/1.0.0",
                        "mode": "package",
                    }
                },
                "error": {},
                "meta": {"request_id": operation_id},
            },
        },
        ctx,
    )

    async with get_session() as session:
        module = (
            await session.execute(
                select(DeviceModule).where(
                    DeviceModule.device_id == device_id,
                    DeviceModule.module_name == "agent_recipe_runner",
                    DeviceModule.version == "1.0.0",
                )
            )
        ).scalar_one()

    assert module.installed is True
    assert module.active is True
    assert module.state == "active"


@pytest.mark.asyncio
async def test_command_ack_updates_operation_without_runtime_agent_entry(test_client, monkeypatch):
    monkeypatch.setattr(agent_services, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_services, "ENABLE_DB_PERSISTENCE", True)
    operation_id = "22222222-2222-4222-8222-222222222222"

    async with get_session() as session:
        await _create_sent_operation(session, operation_id=operation_id)

    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(get_agent=lambda _agent_id: None),
        agent_id="device-lifecycle-1",
    )

    await CommandAckService().handle(
        {
            "type": "command_ack",
            "request_id": operation_id,
            "payload": {"status": "accepted"},
        },
        ctx,
    )

    async with get_session() as session:
        operation = await session.get(Operation, operation_id)

    assert operation is not None
    assert operation.status == "accepted"
    assert operation.accepted_at is not None
