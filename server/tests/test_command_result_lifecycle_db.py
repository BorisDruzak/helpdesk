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
async def test_command_result_error_acknowledges_recovery_result(test_client, monkeypatch):
    monkeypatch.setattr(agent_services, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_services, "ENABLE_DB_PERSISTENCE", True)
    operation_id = "77777777-7777-4777-8777-777777777777"

    async with get_session() as session:
        await _create_sent_operation(
            session,
            operation_id=operation_id,
            device_id="device-restart-recovery",
            command="run_tool",
            kind="tool_call",
        )
        op_service = OperationService(session)
        await op_service.mark_accepted(operation_id, expected_statuses=["sent"])
        await session.commit()

    sent = []

    class _Ws:
        async def send_json(self, payload):
            sent.append(payload)

    ctx = AgentConnectionContext(
        ws=_Ws(),
        request=SimpleNamespace(),
        state=SimpleNamespace(get_agent=lambda _agent_id: None),
        agent_id="device-restart-recovery",
    )

    await CommandResultService().handle(
        {
            "type": "command_result",
            "request_id": operation_id,
            "payload": {
                "status": "error",
                "data": {
                    "observations": {
                        "interrupted": True,
                        "reason": "AGENT_RESTARTED",
                        "target_operation_id": operation_id,
                    }
                },
                "error": {
                    "code": "AGENT_RESTARTED",
                    "message": "Command was interrupted because the agent process restarted",
                    "retryable": True,
                },
                "meta": {"request_id": operation_id, "recovery": True},
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
    assert operation.status == "failed"
    assert operation.error_code == "AGENT_RESTARTED"
    assert outbox.status == "delivered"
    assert sent == [
        {
            "type": "command_result_ack",
            "request_id": operation_id,
            "device_id": "device-restart-recovery",
            "payload": {
                "status": "accepted",
                "operation_id": operation_id,
                "processed": True,
            },
        }
    ]


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


@pytest.mark.asyncio
async def test_cancel_operation_success_reconciles_target_outbox(test_client, monkeypatch):
    monkeypatch.setattr(agent_services, "DB_AVAILABLE", True)
    monkeypatch.setattr(agent_services, "ENABLE_DB_PERSISTENCE", True)
    device_id = "device-lifecycle-cancel"
    target_operation_id = "55555555-5555-4555-8555-555555555555"
    cancel_operation_id = "66666666-6666-4666-8666-666666666666"

    async with get_session() as session:
        target_outbox_id = await _create_sent_operation(
            session,
            operation_id=target_operation_id,
            device_id=device_id,
            command="run_tool",
        )
        op_service = OperationService(session)
        await op_service.mark_accepted(target_operation_id, expected_statuses=["sent"])
        await op_service.mark_running(target_operation_id, expected_statuses=["accepted"])
        await op_service.mark_cancel_requested(
            target_operation_id,
            expected_statuses=["running"],
        )
        outbox_repo = DeviceOutboxRepo(session)
        cancel_outbox_id = await outbox_repo.enqueue_command(
            device_id=device_id,
            command_id=cancel_operation_id,
            command="cancel_operation",
            params={"target_operation_id": target_operation_id},
            request_id=cancel_operation_id,
            trace_id="trace-lifecycle-cancel",
            actor_role="support",
            operation_id=cancel_operation_id,
        )
        cancel_op = await op_service.enqueue_operation(
            operation_id=cancel_operation_id,
            device_id=device_id,
            kind="cancel_operation",
            command_name="cancel_operation",
            actor_role="support",
            trace_id="trace-lifecycle-cancel",
        )
        cancel_op.cancel_target_operation_id = target_operation_id
        await outbox_repo.mark_as_sent(cancel_outbox_id)
        await op_service.mark_sent(cancel_operation_id, expected_statuses=["queued"])
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
            "request_id": cancel_operation_id,
            "payload": {
                "status": "success",
                "data": {
                    "observations": {
                        "cancel_status": "canceled",
                        "target_operation_id": target_operation_id,
                    }
                },
                "error": {},
                "meta": {"request_id": cancel_operation_id},
            },
        },
        ctx,
    )

    async with get_session() as session:
        target_operation = await session.get(Operation, target_operation_id)
        cancel_operation = await session.get(Operation, cancel_operation_id)
        target_outbox = await session.get(DeviceOutbox, target_outbox_id)
        cancel_outbox = (
            await session.execute(select(DeviceOutbox).where(DeviceOutbox.operation_id == cancel_operation_id))
        ).scalar_one()

    assert target_operation is not None
    assert target_operation.status == "canceled"
    assert cancel_operation is not None
    assert cancel_operation.status == "succeeded"
    assert target_outbox is not None
    assert target_outbox.status == "delivered"
    assert target_outbox.delivered_at is not None
    assert cancel_outbox.status == "delivered"
