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
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput, ObserverIntegrityRepo
from observer.integrity_service import ObserverIntegrityService
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_USER_PREFIX


RUN_ID = "obs1-test-20260529-0000"


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")


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
    outbox_id = 900_000 + (uuid.uuid4().int % 100_000)
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add(
            ObserverKnownContamination(
                source_phase="OBS1-test",
                entity_type="device_outbox",
                entity_id=str(outbox_id),
                suppression_scope="observer_integrity",
                reason="test historical contamination",
                active=True,
                created_at=now,
                expires_at=now + timedelta(days=7),
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
                id=outbox_id,
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
async def test_observer_integrity_protocol_ack_audit_valid_duplicate_and_missing_proof(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        session.add_all(
            [
                AgentRuntimeAudit(
                    device_id=device_id,
                    event_type="outbox_ack_persisted",
                    severity="info",
                    source="observer_test",
                    ticket_id=str(uuid.uuid4()),
                    details_json={
                        "audit_contract_version": 2,
                        "outbox_id": "ack-persisted",
                        "trace_id": str(uuid.uuid4()),
                        "event_type": "tool_call_result",
                        "persisted_event_id": 123,
                        "persisted": True,
                        "duplicate": False,
                    },
                    created_at=now,
                ),
                AgentRuntimeAudit(
                    device_id=device_id,
                    event_type="outbox_ack_persisted",
                    severity="info",
                    source="observer_test",
                    details_json={
                        "audit_contract_version": 2,
                        "outbox_id": "ack-duplicate",
                        "trace_id": str(uuid.uuid4()),
                        "event_type": "tools_changed",
                        "persisted": False,
                        "duplicate": True,
                        "duplicate_proof": "session_seen_outbox_id",
                    },
                    created_at=now,
                ),
                AgentRuntimeAudit(
                    device_id=device_id,
                    event_type="outbox_ack_persisted",
                    severity="info",
                    source="observer_test",
                    details_json={
                        "audit_contract_version": 2,
                        "outbox_id": "ack-missing-proof",
                        "trace_id": "trace-missing-proof",
                        "event_type": "tool_call_result",
                        "persisted_event_id": None,
                        "persisted": False,
                        "duplicate": False,
                    },
                    created_at=now,
                ),
            ]
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        events = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.source == "observer.protocol_integrity",
                    ObserverIntegrityEvent.device_id == device_id,
                )
            )
        ).scalars().all()

        assert {event.event_type for event in events} == {"protocol_ack_without_persistence"}
        event = events[0]
        assert event.severity == "critical"
        assert event.outbox_id == "ack-missing-proof"
        assert event.trace_id == "trace-missing-proof"


@pytest.mark.asyncio
async def test_observer_integrity_protocol_gap_resolves_and_repeated_scan_dedupes(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"obs1-device-{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        await _seed_device(session, device_id=device_id)
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        gap = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "protocol_ack_audit_gap",
                    ObserverIntegrityEvent.source == "observer.protocol_integrity",
                )
            )
        ).scalar_one()
        assert gap.status == "active"

        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="outbox_ack_persisted",
                severity="info",
                source="observer_test",
                details_json={
                    "audit_contract_version": 2,
                    "outbox_id": "ack-stable-dedupe",
                    "trace_id": "trace-stable-dedupe",
                    "event_type": "tools_changed",
                    "persisted_event_id": 456,
                    "persisted": True,
                    "duplicate": False,
                },
                created_at=now,
            )
        )
        await session.flush()
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()
        await session.refresh(gap)
        assert gap.status == "resolved"

        bad = AgentRuntimeAudit(
            device_id=device_id,
            event_type="outbox_ack_persisted",
            severity="info",
            source="observer_test",
            details_json={
                "audit_contract_version": 2,
                "outbox_id": "ack-noise-tuning",
                "trace_id": "trace-noise-tuning",
                "event_type": "tool_call_result",
                "persisted_event_id": None,
                "persisted": False,
                "duplicate": False,
            },
            created_at=now,
        )
        session.add(bad)
        await session.flush()
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await ObserverIntegrityService(session).run_scan(run_id=RUN_ID)
        await session.commit()

        rows = (
            await session.execute(
                select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.event_type == "protocol_ack_without_persistence",
                    ObserverIntegrityEvent.outbox_id == "ack-noise-tuning",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].scan_observation_count == 2
        assert rows[0].recurrence_count == 1
        assert rows[0].occurrence_count == 1
        assert rows[0].last_reopened_at is None


@pytest.mark.asyncio
async def test_observer_integrity_recurrence_count_increments_only_after_resolution(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    source = "observer.protocol_integrity"
    event = ObserverIntegrityEventInput(
        event_type="protocol_ack_without_persistence",
        severity="warning",
        source=source,
        dedupe_key=f"recurrence-semantics:{uuid.uuid4()}",
        expected="ack persisted",
        actual="missing persisted event",
        evidence={"case": "recurrence-semantics"},
    )
    async with session_maker() as session:
        repo = ObserverIntegrityRepo(session)
        row = await repo.upsert_event(event)
        await repo.upsert_event(event)
        await session.flush()

        assert row.status == "active"
        assert row.scan_observation_count == 2
        assert row.recurrence_count == 1
        assert row.occurrence_count == 1
        assert row.last_reopened_at is None

        await repo.resolve_missing(source=source, active_dedupe_keys=set())
        await session.flush()
        assert row.status == "resolved"
        resolved_at = row.resolved_at

        await repo.upsert_event(event)
        await session.flush()

        assert row.status == "active"
        assert row.scan_observation_count == 3
        assert row.recurrence_count == 2
        assert row.occurrence_count == 2
        assert row.last_reopened_at is not None
        assert resolved_at is not None
        assert row.last_reopened_at >= resolved_at


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
