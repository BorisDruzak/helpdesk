from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DeviceOutbox, DiagnosticEvidence, Operation, Ticket
from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.execution_router import CapabilityExecutionRouter


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

def _ticket(ticket_id: str, device_id: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=device_id,
        title="Server builtin diagnostic",
        description="Server builtin diagnostic lifecycle test",
        status="in_progress",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_server_builtin_dns_runner_creates_succeeded_operation_without_outbox(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    router = CapabilityExecutionRouter(
        capability_registry=CapabilityRegistry(tool_service=None, state=None),
        tool_service=None,
    )
    result = await router.run_capability(
        ticket_id=ticket_id,
        device_id=None,
        capability_id="server.dns.resolve",
        params={"hostname": "localhost"},
        actor=None,
        idempotency_key="server-dns-idem",
        timeout_ms=2000,
    )

    assert result["status"] == "success"
    assert result["execution_target"] == "server_builtin"
    assert result["execution_kind"] == "query"
    assert result["operation_id"]
    assert result["poll_url"] == f"/api/operations/{result['operation_id']}"
    assert result["idempotency_key"] == "server-dns-idem"
    assert result["output"]["hostname"] == "localhost"
    assert result["evidence_preview"]["kind"] == "network.dns"

    async with session_maker() as session:
        operation = await session.scalar(select(Operation).where(Operation.operation_id == result["operation_id"]))
        outbox_count = await session.scalar(select(func.count(DeviceOutbox.id)))

    assert operation is not None
    assert operation.status == "succeeded"
    assert operation.kind == "server_capability"
    assert operation.tool_name == "server.dns.resolve"
    assert operation.command_name == "server_builtin"
    assert operation.device_id == "server"
    assert operation.ticket_id == ticket_id
    assert operation.started_at is not None
    assert operation.finished_at is not None
    assert operation.result_summary
    assert outbox_count == 0

    repeat = await router.run_capability(
        ticket_id=ticket_id,
        device_id=None,
        capability_id="server.dns.resolve",
        params={"hostname": "localhost"},
        actor=None,
        idempotency_key="server-dns-idem",
        timeout_ms=2000,
    )

    assert repeat["status"] == "succeeded"
    assert repeat["operation_id"] == result["operation_id"]
    assert repeat["idempotent"] is True

    async with session_maker() as session:
        operation_count = await session.scalar(
            select(func.count(Operation.operation_id)).where(
                Operation.ticket_id == ticket_id,
                Operation.tool_name == "server.dns.resolve",
            )
        )
        outbox_count = await session.scalar(select(func.count(DeviceOutbox.id)))

    assert operation_count == 1
    assert outbox_count == 0


@pytest.mark.asyncio
async def test_server_builtin_failure_marks_operation_failed_without_outbox(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    router = CapabilityExecutionRouter(
        capability_registry=CapabilityRegistry(tool_service=None, state=None),
        tool_service=None,
    )
    result = await router.run_capability(
        ticket_id=ticket_id,
        device_id=None,
        capability_id="server.dns.resolve",
        params={"hostname": "invalid host name with spaces"},
        actor=None,
        idempotency_key="server-dns-fail-idem",
        timeout_ms=2000,
    )

    assert result["status"] == "error"
    assert result["error_code"] == "SERVER_BUILTIN_QUERY_FAILED"
    assert result["operation_id"]

    async with session_maker() as session:
        operation = await session.scalar(select(Operation).where(Operation.operation_id == result["operation_id"]))
        outbox_count = await session.scalar(select(func.count(DeviceOutbox.id)))

    assert operation is not None
    assert operation.status == "failed"
    assert operation.error_code == "SERVER_BUILTIN_QUERY_FAILED"
    assert operation.finished_at is not None
    assert outbox_count == 0


@pytest.mark.asyncio
async def test_server_builtin_capability_api_persists_diagnostic_evidence(test_client):
    from app.db import get_session

    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    async with get_session() as session:
        session.add(_ticket(ticket_id, device_id))
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/capabilities/server.dns.resolve/run",
        headers=_auth(),
        json={"params": {"hostname": "localhost"}, "idempotency_key": "server-dns-evidence"},
    )
    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["operation_id"]
    assert payload["diagnostic_evidence_id"]
    assert payload["evidence_preview"]["kind"] == "network.dns"

    async with get_session() as session:
        evidence = await session.get(DiagnosticEvidence, payload["diagnostic_evidence_id"])
        operation = await session.scalar(select(Operation).where(Operation.operation_id == payload["operation_id"]))
        outbox_count = await session.scalar(select(func.count(DeviceOutbox.id)))

    assert evidence is not None
    assert evidence.source_type == "operation"
    assert evidence.source_id == payload["operation_id"]
    assert evidence.provider_id == "server_builtin"
    assert evidence.capability_id == "server.dns.resolve"
    assert evidence.kind == "network.dns"
    assert evidence.status == "ok"
    assert operation is not None
    assert operation.status == "succeeded"
    assert outbox_count == 0
