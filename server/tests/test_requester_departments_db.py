from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryDepartment, RegistryLocation, RegistryPerson
from scripts.helpdesk_requester_departments import publish_department_catalog

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]


async def test_department_publication_archives_only_exact_test_choices_and_preserves_links(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    department_id, location_id, person_id = (str(uuid.uuid4()) for _ in range(3))
    async with maker.begin() as session:
        session.add_all([
            RegistryDepartment(department_id=department_id, name="Synthetic staging", status="active", source="test", metadata_json={}),
            RegistryLocation(location_id=location_id, building="Synthetic building", display_name="Synthetic location fixture", status="active", source="test", metadata_json={}),
        ])
        await session.flush()
        session.add(RegistryPerson(person_id=person_id, display_name="Synthetic catalog fixture", department_id=department_id, location_id=location_id, status="active", metadata_json={"preserve":True}))
    kwargs = dict(synthetic_departments={department_id:"Synthetic staging"}, synthetic_locations={location_id:"Synthetic location fixture"}, isolated_test=True)
    auth = SimpleNamespace(actor_role="admin", actor_id="catalog-fixture")
    plan = await publish_department_catalog(maker, auth, **kwargs)
    assert len(plan["create"]) == 30 and not plan["applied"]
    async with maker() as session:
        assert (await session.get(RegistryDepartment,department_id)).status == "active"
    await publish_department_catalog(maker, auth, **kwargs, apply=True, expected_fingerprint=plan["fingerprint"])
    again = await publish_department_catalog(maker, auth, **kwargs)
    assert not again["create"] and not again["archive_departments"] and not again["archive_locations"]
    await publish_department_catalog(maker, auth, **kwargs, apply=True, expected_fingerprint=again["fingerprint"])
    async with maker() as session:
        assert (await session.get(RegistryDepartment,department_id)).status == "archived"
        assert (await session.get(RegistryLocation,location_id)).status == "archived"
        person = await session.get(RegistryPerson,person_id)
        assert (person.department_id,person.location_id,person.metadata_json) == (department_id,location_id,{"preserve":True})
        active = list(await session.scalars(select(RegistryDepartment).where(RegistryDepartment.status=="active")))
        assert len(active) == 30
    with pytest.raises(ValueError, match="changed since"):
        await publish_department_catalog(maker, auth, **kwargs, apply=True, expected_fingerprint=plan["fingerprint"])
    with pytest.raises(ValueError, match="Exact synthetic"):
        await publish_department_catalog(maker, auth, **{**kwargs,"synthetic_departments":{department_id:"Official department"}})
