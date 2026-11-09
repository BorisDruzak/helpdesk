"""Confirmed identity authority must never infer a person from a login claim."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
import uuid

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser
from auth.identity import IdentityService, IdentityError, parse_identity
from auth.identity_handlers import handle_identity_resolve

pytestmark = pytest.mark.db_cleanup("registry_access")


@pytest.mark.no_db
def test_subject_is_exact_and_guid_is_canonical():
    guid = str(uuid.uuid4())
    assert parse_identity("https://sso.example/realms/org", "Case /\\ sub", guid)[1] == "Case /\\ sub"
    with pytest.raises(ValueError):
        parse_identity("https://sso.example/realms/org", "subject", guid.upper())


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("authorization", [None, "Bearer ordinary-ui-token", "Token integration-service-token"])
async def test_resolve_requires_its_own_bearer_authority(monkeypatch, authorization):
    import config
    monkeypatch.setattr(config, "IDENTITY_RESOLVE_SERVICE_TOKEN", "integration-service-token-32-bytes-long")
    app = web.Application()
    app.router.add_post("/api/integration/v1/identities/resolve", handle_identity_resolve)
    async with TestClient(TestServer(app)) as client:
        headers = {"Authorization": authorization} if authorization else {}
        response = await client.post("/api/integration/v1/identities/resolve", json={}, headers=headers)
        assert response.status == 401
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_shared_service_budget_accepts_polling_burst_and_enforces_configured_limit(monkeypatch):
    import config
    import auth.identity_handlers as handlers
    from auth.rate_limit import reset_rate_limits

    @asynccontextmanager
    async def sessions():
        yield None

    async def resolve(self, issuer, subject, guid):
        return dict(version=1, person_id=str(uuid.uuid4()), issuer=issuer,
                    subject=subject, ad_object_guid=guid, state="active", department_id=None)

    issuer = "https://sso.example/realms/org"
    token = "separate-service-credential-32-bytes-long"
    monkeypatch.setattr(config, "OIDC_ISSUER", issuer)
    monkeypatch.setattr(config, "IDENTITY_RESOLVE_SERVICE_TOKEN", token)
    monkeypatch.setattr(handlers, "get_session", sessions)
    monkeypatch.setattr(IdentityService, "resolve", resolve)
    app = web.Application()
    app.router.add_post("/resolve", handle_identity_resolve)
    reset_rate_limits()
    try:
        async with TestClient(TestServer(app)) as client:
            data = dict(issuer=issuer, subject="pilot", ad_object_guid=str(uuid.uuid4()))
            headers = {"Authorization": "Bearer " + token}
            for _ in range(121):
                assert (await client.post("/resolve", json=data, headers=headers)).status == 200
            reset_rate_limits()
            monkeypatch.setattr(config, "IDENTITY_RESOLVE_RATE_LIMIT_PER_MINUTE", 2)
            assert (await client.post("/resolve", json=data)).status == 401
            assert (await client.post("/resolve", json=data, headers=headers)).status == 200
            assert (await client.post("/resolve", json=data, headers=headers)).status == 200
            assert (await client.post("/resolve", json=data, headers=headers)).status == 429
    finally:
        reset_rate_limits()


@pytest.mark.asyncio
async def test_confirm_requires_verified_legacy_login_and_preserves_role(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id, guid = str(uuid.uuid4()), str(uuid.uuid4())
    login = "sso-" + uuid.uuid4().hex
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=person_id, display_name="Pilot", status="active"),
                         UiUser(user_login=login, password_hash="unchanged", actor_role="support", is_active=True)])
        await session.commit()
        service = IdentityService(session)
        candidate = await service.propose(person_id=person_id, user_login=login, issuer="https://sso.example/realms/org", subject="CaseSubject", ad_object_guid=guid, actor_id="admin")
        with pytest.raises(IdentityError, match="verified_ui_login_required"):
            await service.confirm(candidate.candidate_id, actor_id="admin", verification_reference="AD pilot reviewed")
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True))
        await session.commit()
        binding = await service.confirm(candidate.candidate_id, actor_id="admin", verification_reference="AD pilot reviewed")
        assert binding.user_login == login
        user = await session.get(UiUser, login)
        assert user.actor_role == "support" and user.password_hash == "unchanged" and user.password_login_enabled
        result = await service.resolve(binding.issuer, binding.subject, guid)
        assert result["person_id"] == person_id and result["state"] == "active"
        with pytest.raises(IdentityError):
            await service.resolve(binding.issuer, "casesubject", guid)
        second_id = str(uuid.uuid4())
        session.add(RegistryPerson(person_id=second_id, display_name="Other", status="active"))
        await session.commit()
        from registry.admin_operations_service import RegistryAdminOperationsService
        with pytest.raises(ValueError, match="SSO-bound"):
            await RegistryAdminOperationsService(session).merge_people({"master_person_id": second_id,
                "duplicate_person_id": person_id, "reason": "operator merge test"}, actor_id="admin")
        with pytest.raises(IdentityError, match="verified_sso_session_required"):
            await service.migrate_password(binding.binding_id, actor_id="admin", verification_reference="SSO login verified")
        assert user.password_login_enabled
        await service.revoke(binding.binding_id, actor_id="admin")
        with pytest.raises(IdentityError):
            await service.resolve(binding.issuer, binding.subject, guid)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["user", "support", "admin", "auditor"])
async def test_inactive_person_denies_every_role(test_engine, role):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id, guid = str(uuid.uuid4()), str(uuid.uuid4())
    login = "sso-" + uuid.uuid4().hex
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=person_id, display_name="Pilot", status="active"),
                         UiUser(user_login=login, password_hash="unchanged", actor_role=role, is_active=True)])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True))
        await session.commit()
        service = IdentityService(session)
        candidate = await service.propose(person_id=person_id, user_login=login, issuer="https://sso.example", subject=guid, ad_object_guid=guid, actor_id="admin")
        binding = await service.confirm(candidate.candidate_id, actor_id="admin", verification_reference="verified")
        person = await session.get(RegistryPerson, person_id)
        person.status = "merged"
        await session.commit()
        with pytest.raises(IdentityError) as exc:
            await service.resolve(binding.issuer, binding.subject, guid)
        assert exc.value.status == 403


@pytest.mark.asyncio
async def test_unmapped_self_reported_password_and_token_keep_legacy_access(test_engine, monkeypatch):
    """Strict SSO activity rules must not disable supported legacy requester accounts."""
    import config
    import auth.service as auth_service_module
    from auth.password_service import hash_password
    from auth.service import AuthService
    from app.db.models import UiToken, UiUserAudit
    from sqlalchemy import select

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id, guid, login = str(uuid.uuid4()), str(uuid.uuid4()), "self-reported-" + uuid.uuid4().hex
    password = "Legacy-requester-password-27!"
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=person_id, display_name="Requester", status="self_reported"),
                         UiUser(user_login=login, password_hash=hash_password(password), actor_role="user", is_active=True)])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login,
                                          normalized_identifier=login, verified=True))
        await session.commit()

    @asynccontextmanager
    async def sessions():
        async with maker() as session:
            yield session

    monkeypatch.setattr(auth_service_module, "get_session", sessions)
    monkeypatch.setattr(config, "OIDC_ENABLED", False)
    monkeypatch.setattr(config, "AUTH_UI_DB_USERS_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_UI_CONFIG_FALLBACK_ENABLED", False)
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0)
    auth = AuthService(SimpleNamespace(users={}))
    # Issue first, so password authentication must not revoke existing authority.
    token = await auth.generate_ui_token(login, "user", expires_hours=1)
    assert await auth.authenticate(login, password) == (True, "user")
    assert (await auth.verify_ui_token(token))["user_login"] == login

    async with maker() as session:
        service = IdentityService(session)
        candidate = await service.propose(person_id=person_id, user_login=login,
            issuer="https://sso.example/realms/org", subject="self-reported-sub", ad_object_guid=guid, actor_id="admin")
        with pytest.raises(IdentityError) as exc:
            await service.confirm(candidate.candidate_id, actor_id="admin", verification_reference="reviewed")
        assert exc.value.status == 403
        user = await session.get(UiUser, login)
        assert user.is_active and user.password_login_enabled
        stored_token = (await session.execute(select(UiToken).where(UiToken.user_login == login))).scalar_one()
        assert stored_token.revoked_at is None
        actions = (await session.execute(select(UiUserAudit.action).where(UiUserAudit.user_login == login))).scalars().all()
        assert "user_disabled_by_registry_status" not in actions
    assert (await auth.verify_ui_token(token))["user_login"] == login


@pytest.mark.asyncio
async def test_resolve_route_exact_identity_statuses_and_payload_bound(test_engine, monkeypatch):
    import config
    import auth.identity_handlers as handlers
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    issuer, guid, person_id = "https://sso.example/realms/org", str(uuid.uuid4()), str(uuid.uuid4())
    login = "sso-" + uuid.uuid4().hex
    async with maker() as session:
        session.add_all([RegistryPerson(person_id=person_id, display_name="Pilot", status="active"),
                         UiUser(user_login=login, password_hash="unchanged", actor_role="user", is_active=True)])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True))
        await session.commit()
        service = IdentityService(session)
        candidate = await service.propose(person_id=person_id, user_login=login, issuer=issuer, subject="CaseSub", ad_object_guid=guid, actor_id="admin")
        await service.confirm(candidate.candidate_id, actor_id="admin", verification_reference="reviewed")

    @asynccontextmanager
    async def sessions():
        async with maker() as session:
            yield session
    token = "separate-service-credential-32-bytes-long"
    monkeypatch.setattr(config, "OIDC_ISSUER", issuer)
    monkeypatch.setattr(config, "IDENTITY_RESOLVE_SERVICE_TOKEN", token)
    monkeypatch.setattr(handlers, "get_session", sessions)
    app = web.Application()
    app.router.add_post("/api/integration/v1/identities/resolve", handle_identity_resolve)
    authority = {"Authorization": "Bearer " + token}
    data = dict(issuer=issuer, subject="CaseSub", ad_object_guid=guid)
    async with TestClient(TestServer(app)) as client:
        path = "/api/integration/v1/identities/resolve"
        result = await client.post(path, headers=authority, json=data)
        assert result.status == 200
        assert await result.json() == dict(version=1, person_id=person_id, state="active", department_id=None, **data)
        assert (await client.post(path, headers=authority, json={**data, "subject": "casesub"})).status == 409
        assert (await client.post(path, headers=authority, json={**data, "subject": "unknown", "ad_object_guid": str(uuid.uuid4())})).status == 404
        assert (await client.post(path, headers=authority, json={**data, "person_id": person_id})).status == 400
        assert (await client.post(path, headers=authority, json={**data, "issuer": "https://wrong.example"})).status == 400
        assert (await client.post(path, headers=authority, data="x" * 4097)).status == 400
        async with maker() as session:
            person = await session.get(RegistryPerson, person_id)
            person.status = "inactive"
            await session.commit()
        assert (await client.post(path, headers=authority, json=data)).status == 403
        monkeypatch.setattr(config, "IDENTITY_RESOLVE_SERVICE_TOKEN", "")
        assert (await client.post(path, headers=authority, json=data)).status == 401
