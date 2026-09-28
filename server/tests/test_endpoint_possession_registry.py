from uuid import uuid4
import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, DeviceUserBinding, DeviceRegistrationClaim, RegistryEndpointDeviceMapping
from domain_ports.registry_contracts import EndpointPossessionBindingRequest
from registry.endpoint_possession_service import EndpointPossessionService

pytestmark = pytest.mark.db_cleanup("registration")


@pytest.mark.asyncio
async def test_person_archived_after_profile_read_cannot_activate_binding(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid4())
    async with maker() as session:
        session.add(RegistryPerson(person_id=person_id, display_name="Archive fixture", status="active", source="test"))
        await session.commit()
    async with maker() as caller:
        person = await caller.get(RegistryPerson, person_id)
        assert person.status == "active"
        async with maker() as administrator:
            archived = await administrator.get(RegistryPerson, person_id)
            archived.status = "archived"
            await administrator.commit()
        result = await EndpointPossessionService(caller).bind(EndpointPossessionBindingRequest(
            operation_id=str(uuid4()), endpoint_device_ref=str(uuid4()), person_id=person_id,
            actor_id="archive-fixture", hostname=None, platform="unknown"))
        assert result.status == "unavailable"
        assert result.code == "registry_person_unavailable"


@pytest.mark.asyncio
async def test_endpoint_possession_mapping_binding_replay_and_conflict(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_ref = str(uuid4())
    person_ids = [str(uuid4()), str(uuid4())]
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=value, display_name="Binding fixture", status="active", source="test") for value in person_ids])
        await session.commit()
    def request(person_id):
        return EndpointPossessionBindingRequest(operation_id=str(uuid4()), endpoint_device_ref=device_ref,
            person_id=person_id, actor_id="binding-fixture", hostname="Binding fixture PC", platform="windows")
    async with maker() as session:
        first = await EndpointPossessionService(session).bind(request(person_ids[0]))
        await session.commit()
        assert first.status == "applied"
    async with maker() as session:
        replay = await EndpointPossessionService(session).bind(request(person_ids[0]))
        await session.commit()
        assert replay.status == "replayed"
        assert replay.binding == first.binding
    async with maker() as session:
        conflict = await EndpointPossessionService(session).bind(request(person_ids[1]))
        await session.commit()
        assert conflict.status == "accepted"
        assert conflict.code == "endpoint_possession_pending_admin_review"
        mapping = await session.get(RegistryEndpointDeviceMapping, device_ref)
        rows = (await session.scalars(select(DeviceUserBinding).where(DeviceUserBinding.device_id == mapping.device_id))).all()
        assert len(rows) == 1 and rows[0].person_id == person_ids[0]
        assert rows[0].source == "endpoint_possession_proof"
        claim = await session.get(DeviceRegistrationClaim, conflict.registration.external_id)
        assert claim.status == "conflict" and claim.person_id == person_ids[1]
        assert claim.source == "endpoint_possession_proof"
        from registry.service import RegistrySnapshotService
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        projected = next(row for row in snapshot["registration_claims"] if row["claim_id"] == claim.claim_id)
        assert projected["source"] == "endpoint_possession_proof"


@pytest.mark.asyncio
async def test_concurrent_people_cannot_replace_the_same_device_owner(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    people = [str(uuid4()), str(uuid4())]
    reference = str(uuid4())
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=value, display_name="Concurrent fixture", status="active", source="test") for value in people])
        await session.commit()
    async def bind(person_id):
        async with maker() as session:
            result = await EndpointPossessionService(session).bind(EndpointPossessionBindingRequest(
                operation_id=str(uuid4()), endpoint_device_ref=reference, person_id=person_id,
                actor_id="concurrent-fixture", hostname=None, platform="windows"))
            await session.commit()
            return result
    results = await asyncio.wait_for(asyncio.gather(*(bind(value) for value in people)), timeout=30)
    assert sorted(result.status for result in results) == ["accepted", "applied"]
    async with maker() as session:
        rows = (await session.scalars(select(DeviceUserBinding).where(DeviceUserBinding.device_id == reference))).all()
        assert len(rows) == 1 and rows[0].status == "active"


@pytest.mark.asyncio
async def test_possession_conflict_admin_approval_requires_explicit_transfer(test_engine):
    from registry.registration_service import RegistrationService, RegistrationConflictError
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    people = [str(uuid4()), str(uuid4())]
    reference = str(uuid4())
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=value, display_name="Approval fixture", status="active", source="test") for value in people])
        await session.commit()
    async with maker() as session:
        def request(person_id):
            return EndpointPossessionBindingRequest(operation_id=str(uuid4()), endpoint_device_ref=reference,
                person_id=person_id, actor_id="approval-fixture", hostname=None, platform="windows")
        original = await EndpointPossessionService(session).bind(request(people[0]))
        conflict = await EndpointPossessionService(session).bind(request(people[1]))
        service = RegistrationService(session)
        with pytest.raises(RegistrationConflictError):
            await service.approve_claim(conflict.registration.external_id, reviewed_by="fixture-admin")
        original_row = await session.get(DeviceUserBinding, original.binding.external_id)
        assert original_row.status == "active" and original_row.person_id == people[0]
        approved = await service.approve_claim(conflict.registration.external_id, reviewed_by="fixture-admin", replace_existing=True)
        await session.commit()
        new = await session.get(DeviceUserBinding, approved["binding"]["binding_id"])
        assert original_row.status == "transferred"
        assert new.status == "active" and new.person_id == people[1]
        assert new.source_claim_id == conflict.registration.external_id
        claim = await session.get(DeviceRegistrationClaim, new.source_claim_id)
        assert claim.source == "endpoint_possession_proof" and claim.status == "approved"
        mapping = await session.get(RegistryEndpointDeviceMapping, reference)
        assert mapping.device_id == new.device_id
