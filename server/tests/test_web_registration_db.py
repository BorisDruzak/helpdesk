"""Registration policy and normal-user authority against isolated PostgreSQL."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
import uuid

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser
from auth.password_service import verify_password
import web_api.session_handlers as handlers

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]


async def test_registration_policy_duplicates_invalid_and_existing_profile_survival(test_engine, monkeypatch):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "registration-" + uuid.uuid4().hex
    existing_login = "existing-" + uuid.uuid4().hex
    person_id = str(uuid.uuid4())
    async with maker() as session:
        session.add_all([
            RegistryPerson(person_id=person_id, display_name="Existing employee", status="active",
                metadata_json={"preserve": "profile"}),
            UiUser(user_login=existing_login, password_hash="existing-hash", actor_role="support", is_active=True),
        ])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=existing_login,
            normalized_identifier=existing_login, verified=True))
        await session.commit()
        baseline_people = await session.scalar(select(func.count()).select_from(RegistryPerson))

    @asynccontextmanager
    async def sessions():
        async with maker() as session:
            yield session

    async def observer(*args, **kwargs):
        pass

    monkeypatch.setattr(handlers, "get_session", sessions)
    monkeypatch.setattr(handlers, "_write_web_session_observer_event", observer)
    monkeypatch.setattr(handlers, "check_rate_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", False)
    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    app.router.add_post("/register", handlers.handle_web_session_register)
    password = "Registration-only-long-password-43!"
    data = dict(login=login, password=password, password_repeat=password)
    async with TestClient(TestServer(app)) as client:
        disabled = await client.post("/register", json=data)
        assert disabled.status == 403
        assert (await disabled.json())["error_code"] == "SELF_REGISTRATION_DISABLED"
        async with maker() as session:
            assert await session.get(UiUser, login) is None

        monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", True)
        for invalid in [dict(login="bad login"), dict(password_repeat="different"),
                        dict(password="short", password_repeat="short"), dict(actor_role="admin")]:
            assert (await client.post("/register", json={**data, **invalid})).status == 400
        created = await client.post("/register", json={**data, "login": " " + login + " "})
        assert created.status == 201
        assert "Set-Cookie" not in created.headers
        assert (await created.json())["data"] == dict(user_login=login, actor_role="user", next_path="/app/login?registered=1")
        for duplicate in [login.upper(), existing_login.upper()]:
            response = await client.post("/register", json={**data, "login": duplicate})
            assert response.status == 409
            assert (await response.json())["error_code"] == "LOGIN_ALREADY_EXISTS"

    async with maker() as session:
        user = await session.get(UiUser, login)
        assert user.actor_role == "user" and user.is_active and user.password_login_enabled
        assert verify_password(password, user.password_hash)
        existing = await session.get(UiUser, existing_login)
        assert existing.actor_role == "support" and existing.password_hash == "existing-hash"
        person = await session.get(RegistryPerson, person_id)
        assert person.display_name == "Existing employee" and person.metadata_json == {"preserve": "profile"}
        assert await session.scalar(select(func.count()).select_from(RegistryPerson)) == baseline_people
        alias = (await session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.provider == "ui_login", RegistryPersonIdentity.normalized_identifier == existing_login))).scalar_one()
        assert alias.person_id == person_id and alias.verified
