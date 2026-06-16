from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryPerson
from registry.policy_service import RegistryPolicyService
from registry.primary_agent_resolver import PrimaryAgentResolver
from registry.registration_service import RegistrationService


def _new_id() -> str:
    return str(uuid.uuid4())


def _device(device_id: str, *, hostname: str, agent_version: str = "3.1.70") -> Device:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version=agent_version,
        hostname=hostname,
        os="Windows 11",
        capabilities={"protocol_v3": True},
        device_metadata={"machine_id": device_id, "secret_hint": "must-not-leak"},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


def _person(display_name: str) -> RegistryPerson:
    return RegistryPerson(
        person_id=_new_id(),
        display_name=display_name,
        full_name=display_name,
        source="manual",
        status="active",
    )


class _State:
    def __init__(self, online_device_ids: set[str]):
        self._online_device_ids = online_device_ids

    def is_agent_online(self, device_id: str) -> bool:
        return device_id in self._online_device_ids


@pytest.mark.asyncio
async def test_primary_agent_resolver_prefers_single_primary_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    primary_device_id = _new_id()
    shared_device_id = _new_id()

    async with session_maker() as session:
        session.add_all(
            [
                _device(primary_device_id, hostname="PRIMARY-AGENT", agent_version="3.1.70"),
                _device(shared_device_id, hostname="SHARED-AGENT", agent_version="3.1.69"),
            ]
        )
        person = _person("Resolver Owner")
        session.add(person)
        await session.flush()

        registration = RegistrationService(session)
        primary = await registration.bind_person_to_device(
            device_id=primary_device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="primary diagnostic target",
        )
        await registration.add_shared_user(
            device_id=shared_device_id,
            person_id=person.person_id,
            reviewed_by="admin",
            reason="shared fallback candidate",
        )

        resolved = await PrimaryAgentResolver(session, state=_State({primary_device_id})).resolve_for_person(
            person.person_id
        )
        await session.commit()

    assert resolved["resolved"] is True
    assert resolved["reason_code"] == "primary_binding"
    assert resolved["source"] == "primary_user_binding"
    assert resolved["person_id"] == person.person_id
    assert resolved["device_id"] == primary_device_id
    assert resolved["binding_id"] == primary["binding"]["binding_id"]
    assert resolved["relationship_type"] == "primary_user"
    assert resolved["hostname"] == "PRIMARY-AGENT"
    assert resolved["agent_version"] == "3.1.70"
    assert resolved["online"] is True
    assert resolved["connection_state"] == "online"
    assert resolved["last_seen_at"]
    assert "capabilities" not in resolved
    assert "device_metadata" not in resolved
    assert "secret_hint" not in str(resolved)


@pytest.mark.asyncio
async def test_primary_agent_resolver_keeps_offline_primary_target(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id, hostname="OFFLINE-PRIMARY"))
        person = _person("Offline Owner")
        session.add(person)
        await session.flush()
        binding = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="offline primary target",
        )

        resolved = await PrimaryAgentResolver(session, state=_State(set())).resolve_for_person(person.person_id)
        await session.commit()

    assert resolved["resolved"] is True
    assert resolved["reason_code"] == "primary_binding"
    assert resolved["source"] == "primary_user_binding"
    assert resolved["device_id"] == device_id
    assert resolved["binding_id"] == binding["binding"]["binding_id"]
    assert resolved["online"] is False
    assert resolved["connection_state"] == "offline"


@pytest.mark.asyncio
async def test_primary_agent_resolver_requires_policy_for_single_active_fallback(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id, hostname="SHARED-ONLY"))
        person = _person("Shared Only")
        session.add(person)
        await session.flush()
        await RegistrationService(session).add_shared_user(
            device_id=device_id,
            person_id=person.person_id,
            reviewed_by="admin",
            reason="shared workstation",
        )

        resolved = await PrimaryAgentResolver(session, state=_State(set())).resolve_for_person(person.person_id)
        await session.commit()

    assert resolved == {
        "resolved": False,
        "person_id": person.person_id,
        "reason_code": "primary_device_missing",
        "candidate_count": 1,
    }


@pytest.mark.asyncio
async def test_primary_agent_resolver_returns_safe_reason_for_person_without_devices(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        person = _person("No Devices")
        session.add(person)
        await session.flush()

        resolved = await PrimaryAgentResolver(session, state=_State(set())).resolve_for_person(person.person_id)
        await session.commit()

    assert resolved == {
        "resolved": False,
        "person_id": person.person_id,
        "reason_code": "primary_device_missing",
        "candidate_count": 0,
    }


@pytest.mark.asyncio
async def test_primary_agent_resolver_falls_back_to_single_active_binding_when_policy_allows(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id, hostname="RESPONSIBLE-ONLY"))
        person = _person("Responsible Only")
        session.add(person)
        await session.flush()
        await RegistryPolicyService(session).update_policies(
            {"diagnostic_target": {"allow_single_active_binding_fallback": True}},
            actor_id="test",
        )
        binding = await RegistrationService(session).assign_responsible(
            device_id=device_id,
            person_id=person.person_id,
            reviewed_by="admin",
            reason="responsible diagnostic target",
        )

        resolved = await PrimaryAgentResolver(session, state=_State(set())).resolve_for_person(person.person_id)
        await session.commit()

    assert resolved["resolved"] is True
    assert resolved["reason_code"] == "single_active_binding"
    assert resolved["source"] == "single_active_binding_fallback"
    assert resolved["device_id"] == device_id
    assert resolved["binding_id"] == binding["binding"]["binding_id"]
    assert resolved["relationship_type"] == "responsible"
    assert resolved["online"] is False
    assert resolved["connection_state"] == "offline"


@pytest.mark.asyncio
async def test_primary_agent_resolver_reports_ambiguous_primary_bindings(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    first_device_id = _new_id()
    second_device_id = _new_id()

    async with session_maker() as session:
        session.add_all(
            [
                _device(first_device_id, hostname="PRIMARY-ONE"),
                _device(second_device_id, hostname="PRIMARY-TWO"),
            ]
        )
        person = _person("Ambiguous Owner")
        session.add(person)
        await session.flush()
        registration = RegistrationService(session)
        await registration.bind_person_to_device(
            device_id=first_device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="first primary",
        )
        await registration.bind_person_to_device(
            device_id=second_device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="second primary",
        )

        resolved = await PrimaryAgentResolver(
            session,
            state=_State({first_device_id, second_device_id}),
        ).resolve_for_person(person.person_id)
        await session.commit()

    assert resolved["resolved"] is False
    assert resolved["person_id"] == person.person_id
    assert resolved["reason_code"] == "ambiguous_primary_device"
    assert resolved["candidate_count"] == 2
    assert sorted(item["device_id"] for item in resolved["candidates"]) == sorted([first_device_id, second_device_id])
    assert all("session_token" not in item for item in resolved["candidates"])
