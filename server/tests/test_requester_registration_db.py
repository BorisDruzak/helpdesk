import asyncio
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryDepartment, RegistryLocation, RegistryPerson, UiUser, WebRequesterRegistration
from auth.requester_registration import register_requester, RegistrationConflict
from auth.requester_registration import registration_login_base
from auth.password_service import hash_password, PasswordPolicyError
from requester.identity_service import RequesterIdentityResolver
from requester.identity_service import RequesterProfileValidationError

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]


async def fixture(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    department = str(uuid.uuid4())
    async with maker.begin() as session:
        session.add(RegistryDepartment(department_id=department, name="Real fixture department", status="active", source="test", metadata_json={}))
    data = {"request_id": str(uuid.uuid4()), "first_name": "Иван", "last_name": "Петров", "patronymic": "Сергеевич", "department_id": department, "phone": "1234", "password": "Registration-test-long-43!", "password_repeat": "Registration-test-long-43!"}
    return maker, data


async def test_signup_is_complete_and_replay_does_not_duplicate(test_engine):
    maker, data = await fixture(test_engine)
    async with maker.begin() as session:
        result = await register_requester(session, data)
    async with maker.begin() as session:
        replay = await register_requester(session, data)
        assert replay["user_login"] == result["user_login"]
        user = await session.get(UiUser, result["user_login"])
        assert user.actor_role == "user"
        receipt = await session.get(WebRequesterRegistration, data["request_id"])
        person = await session.get(RegistryPerson, receipt.person_id)
        assert person.full_name == "Петров Иван Сергеевич"
        assert person.department_id == data["department_id"] and person.location_id is None
        own_person = await RequesterIdentityResolver(session).resolve_person_for_web_user(result["user_login"])
        assert own_person.person_id == receipt.person_id
        assert result["profile_complete"] is True
        assert await session.scalar(select(func.count()).select_from(WebRequesterRegistration).where(WebRequesterRegistration.request_id == data["request_id"])) == 1


async def test_concurrent_namesakes_and_same_attempt_are_serialized(test_engine):
    maker, data = await fixture(test_engine)
    async def submit(value):
        async with maker.begin() as session:
            return await register_requester(session, value)
    left, right = await asyncio.gather(submit(data), submit(data))
    assert left["user_login"] == right["user_login"]
    other = {**data, "request_id": str(uuid.uuid4())}
    third, fourth = await asyncio.gather(submit(other), submit({**data, "request_id": str(uuid.uuid4())}))
    assert len({left["user_login"], third["user_login"], fourth["user_login"]}) == 3
    assert third["user_login"].startswith("ipetrov")


async def test_changed_payload_or_password_cannot_replay(test_engine):
    maker, data = await fixture(test_engine)
    async with maker.begin() as session:
        await register_requester(session, data)
    for patch in ({"phone": "9999"}, {"password": "Another-test-password-43!", "password_repeat": "Another-test-password-43!"}):
        with pytest.raises(RegistrationConflict):
            async with maker.begin() as session:
                await register_requester(session, {**data, **patch})


async def test_profile_failure_rolls_back_account_and_receipt(test_engine, monkeypatch):
    maker, data = await fixture(test_engine)
    async with maker() as session:
        baseline = await session.scalar(select(func.count()).select_from(UiUser))
    async def fail(*args, **kwargs):
        raise RuntimeError("Synthetic profile failure")
    monkeypatch.setattr(RequesterIdentityResolver, "update_own_profile", fail)
    with pytest.raises(RuntimeError):
        async with maker.begin() as session:
            await register_requester(session, data)
    async with maker() as session:
        assert await session.scalar(select(func.count()).select_from(UiUser)) == baseline
        assert await session.get(WebRequesterRegistration, data["request_id"]) is None


async def test_existing_hidden_archived_location_is_preserved_on_profile_save(test_engine):
    maker, data = await fixture(test_engine)
    location_id = str(uuid.uuid4())
    async with maker.begin() as session:
        result = await register_requester(session,data)
        person = await RequesterIdentityResolver(session).resolve_person_for_web_user(result["user_login"])
        session.add(RegistryLocation(location_id=location_id, building="Historical", display_name="Historical", status="archived", source="test", metadata_json={}))
        await session.flush()
        person.location_id = location_id
        person.metadata_json = {**person.metadata_json,"position":"Historical position","workplace_label":"Historical workplace"}
    async with maker.begin() as session:
        saved = await RequesterIdentityResolver(session).update_own_profile(actor_id=result["user_login"],payload={"full_name":"Петров Иван Сергеевич","department_id":data["department_id"],"phone":"5678"})
        assert saved["profile"]["location_id"] == location_id
        assert saved["profile_completion"]["complete"] is True
        assert saved["profile"]["position"] == "Historical position"
        assert saved["profile"]["workplace_label"] == "Historical workplace"


async def test_password_must_not_equal_actual_collision_suffixed_login(test_engine):
    maker, data = await fixture(test_engine)
    data["last_name"] = "Александровский"
    base = registration_login_base(data["first_name"],data["last_name"])
    async with maker.begin() as session:
        session.add(UiUser(user_login=base,password_hash=hash_password("Existing-long-password-43!"),actor_role="user",is_active=True))
    data.update(password=base+"2",password_repeat=base+"2")
    with pytest.raises(PasswordPolicyError):
        async with maker.begin() as session:
            await register_requester(session,data)
    async with maker() as session:
        assert await session.get(UiUser,base+"2") is None
        assert await session.get(WebRequesterRegistration,data["request_id"]) is None


async def test_contact_edit_keeps_current_archived_department_but_cannot_select_another(test_engine):
    maker,data = await fixture(test_engine)
    other = str(uuid.uuid4())
    async with maker.begin() as session:
        result = await register_requester(session,data)
        (await session.get(RegistryDepartment,data["department_id"])).status = "archived"
        session.add(RegistryDepartment(department_id=other,name="Other archived department",status="archived",source="test",metadata_json={}))
    profile = {"full_name":"Петров Иван Сергеевич","department_id":data["department_id"],"phone":"5678"}
    async with maker.begin() as session:
        saved = await RequesterIdentityResolver(session).update_own_profile(actor_id=result["user_login"],payload=profile)
        assert saved["profile"]["department_id"] == data["department_id"]
        assert saved["profile"]["phone"] == "5678"
    with pytest.raises(RequesterProfileValidationError):
        async with maker.begin() as session:
            await RequesterIdentityResolver(session).update_own_profile(actor_id=result["user_login"],payload={**profile,"department_id":other})
