import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import RegistryAdminEvent, RegistryPerson, Ticket

pytestmark = pytest.mark.db_cleanup("registry_access")


@pytest.fixture
def test_client(test_client_light):
    return test_client_light


@pytest.mark.asyncio
async def test_registry_readiness_is_read_only_scoped_and_exports_only_aggregates(test_client, test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Synthetic readiness", status="active", phone="555-0100", email="private-readiness@example.test", metadata_json={"private_note": "DO_NOT_EXPORT"})
        session.add(person)
        await session.commit()
        before = [await session.scalar(select(func.count()).select_from(model)) for model in (RegistryAdminEvent, Ticket, RegistryPerson)]
    route = "/api/web/admin/registry/scenario-readiness"
    forbidden = await test_client.get(route, headers={"Authorization": "Bearer test-ui-user:readiness@example.test"})
    assert forbidden.status == 403
    response = await test_client.get(route, headers={"Authorization": "Bearer test-ui-admin-token"})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["read_only"] is True
    assert len(data["dimensions"]) == 9
    assert any(issue["dimension"] == "profiles" and issue["impact"] == "attention" for issue in data["issues"])
    assert any(issue["dimension"] == "devices" and issue["impact"] == "information" for issue in data["issues"])
    exported = json.dumps(data["export"])
    assert all(value not in exported for value in (person.person_id, person.email, person.phone, "DO_NOT_EXPORT", "issue_key", "object_id"))
    async with maker() as session:
        after = [await session.scalar(select(func.count()).select_from(model)) for model in (RegistryAdminEvent, Ticket, RegistryPerson)]
        assert before == after
        assert (await session.get(RegistryPerson, person.person_id)).metadata_json == {"private_note": "DO_NOT_EXPORT"}
