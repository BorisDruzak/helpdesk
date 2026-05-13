from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceDesiredModule, DeviceModule, Module, ServerConfig
from diagnostics.runner_rollout import RunnerRolloutService, RunnerRolloutStateError


RUNNER = "agent_recipe_runner"


def _device(device_id: str, *, os_name: str = "Windows 11") -> Device:
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="1.0.0",
        hostname=f"runner-{device_id[:6]}",
        os=os_name,
        capabilities={},
        device_metadata={},
    )


def _runner_module(version: str, sha: str) -> Module:
    return Module(
        module_name=RUNNER,
        version=version,
        sha256=sha,
        size=1234,
        storage_path=f"agent_recipe_runner/{version}/module.zip",
        uploaded_by="admin",
        manifest_json={
            "module_name": RUNNER,
            "module_version": version,
            "owner_scope": "platform",
            "system_module": True,
            "protected": True,
            "platforms": ["win32", "linux"],
        },
        validation_json={"status": "passed"},
    )


async def _seed_runner_fleet(session, *, device_count: int = 3) -> list[str]:
    device_ids = [str(uuid.uuid4()) for _ in range(device_count)]
    session.add_all([_device(device_id) for device_id in device_ids])
    session.add_all([
        _runner_module("1.0.0", "a" * 64),
        _runner_module("1.1.0", "b" * 64),
    ])
    session.add(
        ServerConfig(
            key=f"module_preferred:{RUNNER}",
            value=json.dumps({"module_name": RUNNER, "version": "1.1.0"}),
        )
    )
    for device_id in device_ids:
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name=RUNNER,
                version="1.0.0",
                installed=True,
                active=True,
                state="active",
                source="test",
            )
        )
    await session.flush()
    return device_ids


@pytest.mark.asyncio
async def test_runner_rollout_start_canary_sets_desired_only_for_first_wave(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    reconciled: list[str] = []

    async def fake_reconcile(device_id, *_args, **_kwargs):
        reconciled.append(device_id)
        return {"installs": 1, "operations": [{"operation_id": f"op-{device_id}", "command": "install_module_package"}]}

    monkeypatch.setattr("diagnostics.runner_rollout.reconcile_device", fake_reconcile)

    async with session_maker() as session:
        device_ids = await _seed_runner_fleet(session)
        service = RunnerRolloutService(session)
        plan = await service.create_plan(
            target_version="1.1.0",
            rollback_version="1.0.0",
            target_device_ids=device_ids,
            canary_size=1,
            wave_size=2,
            max_concurrency=2,
            actor="admin",
        )
        await session.commit()

    async with session_maker() as session:
        desired_before = (await session.execute(select(DeviceDesiredModule))).scalars().all()
        assert desired_before == []

        service = RunnerRolloutService(session)
        started = await service.start_canary(plan["plan_id"], actor="admin")
        await session.commit()

    assert started["status"] == "active"
    assert started["current_wave"]["wave_index"] == 1
    assert started["current_wave"]["target_count"] == 1
    assert len(reconciled) == 1

    async with session_maker() as session:
        desired = (await session.execute(select(DeviceDesiredModule))).scalars().all()
        assert len(desired) == 1
        assert desired[0].module_name == RUNNER
        assert desired[0].desired_version == "1.1.0"
        assert desired[0].reason == "runner_rollout"
        assert desired[0].updated_by == "admin"


@pytest.mark.asyncio
async def test_runner_rollout_promote_requires_completed_canary_and_starts_next_wave(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    reconciled: list[str] = []

    async def fake_reconcile(device_id, *_args, **_kwargs):
        reconciled.append(device_id)
        return {"installs": 1, "operations": []}

    monkeypatch.setattr("diagnostics.runner_rollout.reconcile_device", fake_reconcile)

    async with session_maker() as session:
        device_ids = await _seed_runner_fleet(session)
        service = RunnerRolloutService(session)
        plan = await service.create_plan(
            target_version="1.1.0",
            rollback_version="1.0.0",
            target_device_ids=device_ids,
            canary_size=1,
            wave_size=2,
            actor="admin",
        )
        started = await service.start_canary(plan["plan_id"], actor="admin")
        canary_device_id = started["current_wave"]["targets"][0]["device_id"]
        with pytest.raises(RunnerRolloutStateError):
            await service.promote_next_wave(plan["plan_id"], actor="admin")
        session.add(
            DeviceModule(
                device_id=canary_device_id,
                module_name=RUNNER,
                version="1.1.0",
                installed=True,
                active=True,
                state="active",
                source="test",
            )
        )
        await session.flush()
        refreshed = await service.refresh_plan(plan["plan_id"])
        promoted = await service.promote_next_wave(plan["plan_id"], actor="admin")
        await session.commit()

    assert refreshed["waves"][0]["status"] == "completed"
    assert promoted["current_wave"]["wave_index"] == 2
    assert promoted["current_wave"]["target_count"] == 2
    assert len(reconciled) == 3


@pytest.mark.asyncio
async def test_runner_rollout_rollback_reverts_started_targets_only(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    reconciled: list[str] = []

    async def fake_reconcile(device_id, *_args, **_kwargs):
        reconciled.append(device_id)
        return {"installs": 1, "operations": []}

    monkeypatch.setattr("diagnostics.runner_rollout.reconcile_device", fake_reconcile)

    async with session_maker() as session:
        device_ids = await _seed_runner_fleet(session)
        service = RunnerRolloutService(session)
        plan = await service.create_plan(
            target_version="1.1.0",
            rollback_version="1.0.0",
            target_device_ids=device_ids,
            canary_size=1,
            wave_size=2,
            actor="admin",
        )
        started = await service.start_canary(plan["plan_id"], actor="admin")
        rolled_back = await service.rollback_plan(plan["plan_id"], actor="admin", reason="failed canary")
        refreshed = await service.refresh_plan(plan["plan_id"])
        second_refresh = await service.refresh_plan(plan["plan_id"])
        await session.commit()

    assert rolled_back["status"] == "rolling_back"
    assert refreshed["status"] == "rolled_back"
    assert refreshed["summary"]["rolled_back"] == 1
    assert second_refresh["summary"]["rolled_back"] == 1
    touched = {item["device_id"] for item in started["current_wave"]["targets"]}
    assert set(reconciled) == touched | touched

    async with session_maker() as session:
        desired = (await session.execute(select(DeviceDesiredModule))).scalars().all()
        assert {row.device_id for row in desired} == touched
        assert {row.desired_version for row in desired} == {"1.0.0"}
        assert {row.reason for row in desired} == {"runner_rollback"}


@pytest.mark.asyncio
async def test_runner_rollout_noop_rollback_stays_rolled_back_after_refresh(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def fake_reconcile(device_id, *_args, **_kwargs):
        return {"installs": 1, "operations": []}

    monkeypatch.setattr("diagnostics.runner_rollout.reconcile_device", fake_reconcile)

    async with session_maker() as session:
        device_ids = await _seed_runner_fleet(session)
        service = RunnerRolloutService(session)
        plan = await service.create_plan(
            target_version="1.0.0",
            rollback_version="1.0.0",
            target_device_ids=device_ids[:1],
            canary_size=1,
            wave_size=1,
            actor="admin",
        )
        await service.start_canary(plan["plan_id"], actor="admin")
        await service.rollback_plan(plan["plan_id"], actor="admin", reason="noop rollback")
        first_refresh = await service.refresh_plan(plan["plan_id"])
        second_refresh = await service.refresh_plan(plan["plan_id"])
        await session.commit()

    assert first_refresh["status"] == "rolled_back"
    assert first_refresh["summary"] == {"rolled_back": 1}
    assert second_refresh["status"] == "rolled_back"
    assert second_refresh["summary"] == {"rolled_back": 1}
