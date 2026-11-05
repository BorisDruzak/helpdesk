from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPersonIdentity, UiUser
from app.services.user_display_names import ui_user_display_names
from requester.ticket_handling import assignee_name
from tests.test_requester_workspace_api import _person_for_login
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]


async def test_access_and_requester_use_verified_registry_names_with_safe_login_fallback(test_client_light, test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid4().hex[:8]
    verified, unverified, absent = [name + suffix for name in ("named-", "unverified-", "no-profile-")]
    async with maker() as session:
        for login in (verified, unverified, absent):
            session.add(UiUser(user_login=login, password_hash="fixture-only", actor_role="support", is_active=True))
        person = await _person_for_login(session, login=verified)
        person.full_name = "Иван Специалист"
        person.display_name = "Короткое имя"
        other = await _person_for_login(session, login=unverified)
        other.full_name = "UNVERIFIED PRIVATE NAME"
        identity = await session.scalar(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == other.person_id))
        identity.verified = False
        await session.commit()
        names = await ui_user_display_names(session, [verified, unverified, absent])
        assert names == {verified: "Иван Специалист", unverified: unverified, absent: absent}
        assert await assignee_name(session, verified) == names[verified]
    response = await test_client_light.get("/api/web/admin/access/summary", headers={"Authorization": "Bearer " + TEST_UI_ADMIN_TOKEN})
    payload = await response.json()
    assert response.status == 200, payload
    users = {user["user_login"]: user for user in payload["data"]["users"]}
    assert users[verified]["display_name"] == "Иван Специалист"
    assert users[unverified]["display_name"] == unverified
    assert "UNVERIFIED PRIVATE NAME" not in str(payload)
    assert "fixture-only" not in str(payload)
    denied = await test_client_light.get("/api/web/admin/access/summary", headers={"Authorization": "Bearer " + TEST_UI_SUPPORT_TOKEN})
    assert denied.status == 403
