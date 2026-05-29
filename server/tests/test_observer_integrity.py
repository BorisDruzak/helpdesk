from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AgentRuntimeAudit,
    Device,
    DeviceDesiredModule,
    DeviceOutbox,
    DeviceToolsetSnapshot,
    ObserverIntegrityEvent,
    ObserverKnownContamination,
    Operation,
    ProblemCandidate,
    UiUser,
)
from observer.integrity_service import ObserverIntegrityService
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_USER_PREFIX


RUN_ID = "obs1-test-20260529-0000"


class _FakeRuntimeState:
    def __init__(self, online_devices: set[str]) -> None:
        self._online_devices = online_devices

    def is_agent_online(self, device_id: str) -> bool:
        return device_id in self._online_devices


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _requester_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}observer-integrity-denied"}


async def _seed_device(session, *, device_id: str) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session.add(
        Device(
            device_id=device_id,
            protocol_version="ws_ticket_v3",
            agent_version="3.1.61",
            hostname=f"{device_id}.local",
            capabilities={"protocol_v3": True},
            first_seen_at=now - timedelta(hours=1),
            last_seen_at=now,
        )
    )


@pytest.mark.asyncio
async def test_observer_integrity_terminal_operation_stale_outbox_resolves(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    operation_id = str(uuid.uuid4())
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=str(uuid.uuid4()),
                kind="command",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=now - timedelta(minutes=20),
                sent_at=now - timedelta(minutes=19),
                finished_at=now - timedelta(minutes=18),
            )
        )
        session.add(
            DeviceOutbox(
                device_id=device_id,
                command_id=str(uuid.uuid4()),
                command="system.collect",
                params={"marker": RUN_ID},
                status="sent",
                actor_role="support",
                operation_id=operation_id,
                created_at=now - timedelta(minutes=20),
                sent_at=now - timedelta(minutes=19),
            )
        )
        await session.commit()

    async with session_maker() as session:
        result = await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        assert result.active >= 1
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "operation_outbox_mismatch",
                    ObserverIntegrityEvent.operation_id == operation_id,
                )
            )
        ).scalar_one()
        assert event.severity == "critical"
        assert event.status == "active"
        assert event.run_id == RUN_ID

        outbox = (
            await session.execute(select(DeviceOutbox).where(DeviceOutbox.operation_id == operation_id))
        ).scalar_one()
        outbox.status = "delivered"
        outbox.delivered_at = datetime.now(timezone.utc)
        await session.flush()
        result = await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        assert result.resolved >= 1
        await session.refresh(event)
        assert event.status == "resolved"
        assert event.resolved_at is not None


@pytest.mark.asyncio
async def test_observer_integrity_active_operation_inside_grace_has_no_stuck_event(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    operation_id = str(uuid.uuid4())
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=str(uuid.uuid4()),
                kind="command",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="running",
                queued_at=now - timedelta(minutes=2),
                sent_at=now - timedelta(minutes=1),
            )
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        count = await session.scalar(
            select(ObserverIntegrityEvent).where(
                ObserverIntegrityEvent.event_type == "operation_stuck_active",
                ObserverIntegrityEvent.operation_id == operation_id,
            )
        )
        assert count is None


@pytest.mark.asyncio
async def test_observer_integrity_known_contamination_is_suppressed(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    operation_id = str(uuid.uuid4())
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add(
            ObserverKnownContamination(
                source_phase="OBS1-test",
                entity_type="device_outbox",
                entity_id="135",
                suppression_scope="observer_integrity",
                reason="test historical contamination",
                active=True,
                created_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=str(uuid.uuid4()),
                kind="command",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=now - timedelta(minutes=20),
                finished_at=now - timedelta(minutes=18),
            )
        )
        session.add(
            DeviceOutbox(
                id=135,
                device_id=device_id,
                command_id=str(uuid.uuid4()),
                command="system.collect",
                params={"marker": RUN_ID},
                status="sent",
                actor_role="support",
                operation_id=operation_id,
                created_at=now - timedelta(minutes=20),
            )
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(ObserverIntegrityEvent.operation_id == operation_id)
            )
        ).scalar_one()
        assert event.status == "suppressed"
        assert "test historical contamination" in (event.suppression_reason or "")


@pytest.mark.asyncio
async def test_observer_integrity_account_boundary_audit_becomes_critical(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="account_boundary_mutation_success",
                severity="critical",
                source="observer_test",
                ticket_id=ticket_id,
                actor_role="agent",
                details_json={"mutation_kind": "ticket_message", "ticket_id": ticket_id, "auth_state": "missing_account_session"},
                created_at=now,
            )
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "account_boundary_mutation_success",
                    ObserverIntegrityEvent.ticket_id == ticket_id,
                )
            )
        ).scalar_one()
        assert event.severity == "critical"
        assert event.status == "active"
        assert "missing_account_session" in str(event.evidence_json)


@pytest.mark.asyncio
async def test_observer_integrity_protocol_repeated_nack_becomes_warning_or_error(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        for _ in range(5):
            session.add(
                AgentRuntimeAudit(
                    device_id=device_id,
                    event_type="protocol_nack",
                    severity="warning",
                    source="observer_test",
                    details_json={"error_code": "DEVICE_MISMATCH", "marker": RUN_ID},
                    created_at=now,
                )
            )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "protocol_repeated_nack",
                    ObserverIntegrityEvent.device_id == device_id,
                )
            )
        ).scalar_one()
        assert event.severity == "error"
        assert event.status == "active"


@pytest.mark.asyncio
async def test_observer_integrity_runtime_online_stale_db_projection(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        device = (await session.execute(select(Device).where(Device.device_id == device_id))).scalar_one()
        device.last_seen_at = now - timedelta(hours=1)
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session, state=_FakeRuntimeState({device_id})).run_scan(run_id=RUN_ID)
        await session.commit()
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "runtime_online_db_last_seen_stale",
                    ObserverIntegrityEvent.device_id == device_id,
                )
            )
        ).scalar_one()
        assert event.severity == "warning"
        assert event.status == "active"


@pytest.mark.asyncio
async def test_observer_integrity_module_and_toolset_drift_events(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        device = (await session.execute(select(Device).where(Device.device_id == device_id))).scalar_one()
        device.current_toolset_hash = "current-hash"
        session.add(
            DeviceToolsetSnapshot(
                device_id=device_id,
                captured_at=now - timedelta(minutes=30),
                agent_version="3.1.61",
                toolset_hash="snapshot-hash",
                toolset_json={"tools": [{"name": "system.collect"}]},
                tool_count=1,
            )
        )
        session.add(
            DeviceDesiredModule(
                device_id=device_id,
                module_name="obs1.synthetic",
                desired_version="1.0.0",
                state="installed",
                reason="manual",
                updated_at=now - timedelta(minutes=30),
                updated_by="observer-test",
            )
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        event_types = {
            row.event_type
            for row in (
                await session.execute(
                    select(ObserverIntegrityEvent).where(ObserverIntegrityEvent.device_id == device_id)
                )
            ).scalars().all()
        }
        assert "toolset_hash_drift" in event_types
        assert "module_desired_actual_drift" in event_types


@pytest.mark.asyncio
async def test_observer_integrity_governance_duplicate_problem_candidates(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        for idx in range(2):
            session.add(
                ProblemCandidate(
                    candidate_id=str(uuid.uuid4()),
                    fingerprint=f"obs1-{uuid.uuid4()}",
                    status="open",
                    signal_type="reopen_spike",
                    title=f"OBS1 duplicate candidate {idx}",
                    summary="Synthetic OBS1 duplicate candidate",
                    service_code="svc-obs1",
                    offering_code="off-obs1",
                    request_type="incident",
                    evidence_json={"marker": RUN_ID},
                    ticket_count=2,
                    created_at=now,
                    updated_at=now,
                )
            )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        event = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "problem_duplicate_open_candidates",
                    ObserverIntegrityEvent.source == "observer.governance",
                )
            )
        ).scalar_one()
        assert event.severity == "error"
        assert event.status == "active"


@pytest.mark.asyncio
async def test_observer_integrity_api_rbac(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(UiUser(user_login="observer-admin", password_hash="test", actor_role="admin", is_active=True))
        await session.commit()

    denied = await test_client.get("/api/web/admin/observer/integrity", headers=_requester_headers())
    assert denied.status == 403

    allowed = await test_client.get("/api/web/admin/observer/integrity?limit=5", headers=_admin_headers())
    assert allowed.status == 200, await allowed.text()
    payload = await allowed.json()
    assert payload["status"] == "success"
    assert "summary" in payload["data"]
    assert isinstance(payload["data"]["items"], list)
