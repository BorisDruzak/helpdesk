from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AccessAudit, AccessGroup, AccessGroupMember, AccessGroupQueueMember, ConfirmedIdentityBinding,
    RegistryPerson, RegistryPersonIdentity, TicketQueue, TicketQueueMember, UiToken, UiUser,
)
from auth.password_service import verify_password

pytestmark = pytest.mark.db_cleanup("full")
ADMIN = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT = {"Authorization": "Bearer test-ui-support-token"}
PASSWORD = "Unique-local-secret-123"


@pytest.fixture
async def account_person(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Account person", status="active")
        queue = TicketQueue(code="account-" + uuid.uuid4().hex[:8], name="Account queue", is_active=True)
        group = AccessGroup(code="account-" + uuid.uuid4().hex[:8], name="Account group", is_active=True)
        session.add_all([person, queue, group])
        await session.commit()
        return person.person_id, queue.id, group.id


def body(queue_id=None, group_id=None, **updates):
    return {"user_login": "account.new", "password": PASSWORD, "actor_role": "support", "is_active": True,
            "queue_ids": [queue_id] if queue_id else [], "group_ids": [group_id] if group_id else [],
            "reason": "Approved account setup", **updates}


@pytest.mark.asyncio
async def test_account_provider_is_admin_only(test_client):
    path = "/api/web/admin/users/unknown/account"
    for method in (test_client.get, test_client.put):
        assert (await method(path, headers=SUPPORT)).status == 403
        assert (await method(path, headers={"Authorization": "Bearer test-ui-user:ordinary"})).status == 403


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_account_handlers_require_authenticated_context():
    from aiohttp.test_utils import make_mocked_request
    from web_api.user_account_handlers import handle_web_admin_user_accounts, handle_web_admin_user_account_save

    request = make_mocked_request("GET", "/api/web/admin/users/unknown/account")
    assert (await handle_web_admin_user_accounts(request)).status == 401
    assert (await handle_web_admin_user_account_save(request)).status == 401


@pytest.mark.asyncio
async def test_provisions_person_account_and_separates_inherited_queues(test_client, test_engine, account_person):
    person_id, queue_id, group_id = account_person
    path = f"/api/web/admin/users/{person_id}/account"
    read = await test_client.get(path, headers=ADMIN)
    assert read.status == 200
    assert (await read.json())["data"] == {"accounts": []}
    response = await test_client.put(path, headers=ADMIN, json=body(queue_id, group_id))
    assert response.status == 200
    account = (await response.json())["data"]["account"]
    assert account == {"user_login": "account.new", "actor_role": "support", "is_active": True,
                       "queue_ids": [queue_id], "group_ids": [group_id]}
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = await session.get(UiUser, "account.new")
        assert verify_password(PASSWORD, user.password_hash)
        identity = (await session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.person_id == person_id))).scalar_one()
        assert identity.verified and identity.normalized_identifier == "account.new"
        audit = (await session.execute(select(AccessAudit).where(AccessAudit.entity_id == "account.new"))).scalars().all()
        assert audit
        assert PASSWORD not in json.dumps([row.after_json for row in audit])
        assert "password_hash" not in json.dumps([row.after_json for row in audit])
        session.add(AccessGroupQueueMember(group_id=group_id, queue_id=queue_id))
        await session.commit()
    update = body(group_id=group_id)
    update.pop("password")
    response = await test_client.put(path, headers=ADMIN, json=update)
    assert response.status == 200
    assert (await response.json())["data"]["account"]["queue_ids"] == []
    async with maker() as session:
        assert await session.get(AccessGroupQueueMember, (group_id, queue_id)) is not None
    assert (await (await test_client.get(path, headers=ADMIN)).json())["data"]["accounts"][0]["queue_ids"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("updates,code", [
    ({"reason": "  "}, "VALIDATION_ERROR"),
    ({"password": "short"}, "PASSWORD_POLICY_ERROR"),
    ({"password": None}, "PASSWORD_REQUIRED"),
    ({"queue_ids": [99999999]}, "INVALID_QUEUE"),
    ({"group_ids": [99999999]}, "INVALID_GROUP"),
    ({"actor_role": "system"}, "VALIDATION_ERROR"),
    ({"queue_ids": [True]}, "VALIDATION_ERROR"),
    ({"is_active": "false"}, "VALIDATION_ERROR"),
])
async def test_rejects_invalid_account_without_persisting(test_client, test_engine, account_person, updates, code):
    person_id, _, _ = account_person
    response = await test_client.put(f"/api/web/admin/users/{person_id}/account", headers=ADMIN, json=body(**updates))
    assert response.status == 400
    assert (await response.json())["error_code"] == code
    async with async_sessionmaker(test_engine)() as session:
        assert await session.get(UiUser, "account.new") is None


@pytest.mark.asyncio
async def test_links_existing_case_preserving_login_but_never_reparents(test_client, test_engine, account_person):
    person_id, queue_id, _ = account_person
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(UiUser(user_login="Existing.Mixed", password_hash="existing", actor_role="user", is_active=True))
        other = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Other", status="active")
        session.add(other)
        await session.commit()
        other_id = other.person_id
    data = body(queue_id, user_login="EXISTING.MIXED")
    data.pop("password")
    preview = await test_client.get(f"/api/web/admin/users/{person_id}/account?user_login=EXISTING.MIXED", headers=ADMIN)
    assert preview.status == 200
    assert (await preview.json())["data"]["accounts"] == [
        {"user_login": "Existing.Mixed", "actor_role": "user", "is_active": True, "queue_ids": [], "group_ids": []}]
    response = await test_client.put(f"/api/web/admin/users/{person_id}/account", headers=ADMIN, json=data)
    assert response.status == 200
    assert (await response.json())["data"]["account"]["user_login"] == "Existing.Mixed"
    response = await test_client.put(f"/api/web/admin/users/{other_id}/account", headers=ADMIN, json=data)
    assert response.status == 409
    assert (await response.json())["error_code"] == "IDENTITY_COLLISION"
    preview = await test_client.get(f"/api/web/admin/users/{other_id}/account?user_login=existing.mixed", headers=ADMIN)
    assert preview.status == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("login,code", [("admin-test", "SELF_LOCKOUT"), ("last.admin", "LAST_ADMIN")])
async def test_protects_self_and_last_admin(test_client, test_engine, account_person, login, code):
    person_id, _, _ = account_person
    async with async_sessionmaker(test_engine)() as session:
        session.add(UiUser(user_login=login, password_hash="unchanged", actor_role="admin", is_active=True))
        await session.commit()
    response = await test_client.put(f"/api/web/admin/users/{person_id}/account", headers=ADMIN,
                                    json=body(user_login=login, actor_role="support"))
    assert response.status == 409
    assert (await response.json())["error_code"] == code
    async with async_sessionmaker(test_engine)() as session:
        assert (await session.get(UiUser, login)).actor_role == "admin"


@pytest.mark.asyncio
async def test_missing_person_and_read_failure_are_not_success(test_client, account_person, monkeypatch):
    from app.services.user_accounts import UserAccountsService

    response = await test_client.get("/api/web/admin/users/unknown/account", headers=ADMIN)
    assert response.status == 404

    async def broken_read(*args, **kwargs):
        raise RuntimeError("sensitive database detail")

    monkeypatch.setattr(UserAccountsService, "list_accounts", broken_read)
    response = await test_client.get(f"/api/web/admin/users/{account_person[0]}/account", headers=ADMIN)
    assert response.status == 503
    assert "sensitive" not in await response.text()


@pytest.mark.asyncio
async def test_cannot_create_local_login_when_database_auth_is_disabled(test_client, account_person, monkeypatch):
    import config

    monkeypatch.setattr(config, "AUTH_UI_DB_USERS_ENABLED", False)
    monkeypatch.setattr(config, "OIDC_ENABLED", False)
    response = await test_client.put(f"/api/web/admin/users/{account_person[0]}/account", headers=ADMIN, json=body())
    assert response.status == 409
    assert (await response.json())["error_code"] == "LOCAL_AUTH_DISABLED"


@pytest.mark.asyncio
async def test_mixed_case_login_reads_and_saves_canonical_effective_grants(test_client, test_engine, account_person):
    person_id, queue_id, group_id = account_person
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(UiUser(user_login="Existing.Mixed", password_hash="existing", actor_role="support", is_active=True))
        session.add(TicketQueueMember(queue_id=queue_id, actor_id="existing.mixed", role_in_queue="specialist"))
        session.add(AccessGroupMember(group_id=group_id, actor_id="Existing.Mixed"))
        await session.commit()
    path = f"/api/web/admin/users/{person_id}/account"
    response = await test_client.get(path + "?user_login=existing.mixed", headers=ADMIN)
    assert response.status == 200
    account = (await response.json())["data"]["accounts"][0]
    assert account["queue_ids"] == [queue_id]
    assert account["group_ids"] == [group_id]
    response = await test_client.put(path, headers=ADMIN, json={**account, "reason": "Preserve current access"})
    assert response.status == 200
    effective = await test_client.get("/api/web/admin/access/effective?actor_id=existing.mixed", headers=ADMIN)
    assert effective.status == 200
    access = (await effective.json())["data"]
    assert any(item["queue_id"] == queue_id for item in access["queues"])
    assert access["groups"]
    async with maker() as session:
        assert await session.get(AccessGroupMember, (group_id, "Existing.Mixed")) is not None
        member = (await session.execute(select(TicketQueueMember).where(
            TicketQueueMember.actor_id == "Existing.Mixed", TicketQueueMember.queue_id == queue_id))).scalar_one()
        assert member.role_in_queue == "specialist"


@pytest.mark.asyncio
async def test_sso_only_account_rejects_local_password_change(test_client, test_engine, account_person):
    async with async_sessionmaker(test_engine)() as session:
        session.add(UiUser(user_login="account.new", password_hash="unchanged", password_login_enabled=False,
                           actor_role="user", is_active=True))
        await session.commit()
    response = await test_client.put(f"/api/web/admin/users/{account_person[0]}/account", headers=ADMIN, json=body())
    assert response.status == 409
    assert (await response.json())["error_code"] == "PASSWORD_LOGIN_DISABLED"


@pytest.mark.asyncio
async def test_confirmed_oidc_binding_cannot_be_reparented_via_local_alias(test_client, test_engine, account_person):
    other_id = str(uuid.uuid4())
    async with async_sessionmaker(test_engine)() as session:
        session.add(RegistryPerson(person_id=other_id, display_name="Confirmed owner", status="active"))
        session.add(UiUser(user_login="account.new", password_hash="unchanged", actor_role="user", is_active=True))
        await session.flush()
        session.add(ConfirmedIdentityBinding(person_id=other_id, user_login="account.new",
            issuer="https://identity.example.test", subject="fixture-subject", ad_object_guid=str(uuid.uuid4()),
            confirmed_by="admin-test", verification_reference="fixture verified identity"))
        await session.commit()
    path = f"/api/web/admin/users/{account_person[0]}/account"
    response = await test_client.get(path + "?user_login=account.new", headers=ADMIN)
    assert response.status == 409
    data = body()
    data.pop("password")
    response = await test_client.put(path, headers=ADMIN, json=data)
    assert response.status == 409
    assert (await response.json())["error_code"] == "IDENTITY_COLLISION"


@pytest.mark.asyncio
async def test_multiple_linked_accounts_are_listed_and_only_explicit_selection_is_edited(test_client, test_engine, account_person):
    person_id, _, _ = account_person
    maker = async_sessionmaker(test_engine)
    async with maker() as session:
        for login in ("linked.first", "linked.second"):
            session.add(UiUser(user_login=login, password_hash="unchanged", actor_role="user", is_active=True))
            session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login,
                        normalized_identifier=login, verified=False, source="manual"))
        await session.commit()
    path = f"/api/web/admin/users/{person_id}/account"
    response = await test_client.get(path, headers=ADMIN)
    assert response.status == 200
    accounts = (await response.json())["data"]["accounts"]
    assert [item["user_login"] for item in accounts] == ["linked.first", "linked.second"]
    response = await test_client.put(path, headers=ADMIN, json={**accounts[1], "actor_role": "auditor", "reason": "Second account role"})
    assert response.status == 200
    async with maker() as session:
        assert (await session.get(UiUser, "linked.first")).actor_role == "user"
        assert (await session.get(UiUser, "linked.second")).actor_role == "auditor"
        identities = (await session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.person_id == person_id))).scalars().all()
        assert {row.identifier: row.verified for row in identities} == {"linked.first": False, "linked.second": True}


@pytest.mark.asyncio
async def test_mixed_case_grants_survive_real_oidc_and_password_actor_projections(test_engine, account_person, monkeypatch):
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request
    from cryptography.fernet import Fernet

    import auth.oidc as oidc
    import auth.service as auth_service_module
    import config
    from app.db.models import OidcFlow
    from app.repos.access_control_repo import AccessControlRepo
    from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
    from app.repos.ticket_events_repo import TicketEventsRepo
    from app.services.user_accounts import UserAccountsService
    from auth.middleware import WEB_SESSION_COOKIE_NAME, extract_auth_context
    from auth.service import AuthService
    from web_api.dto.user_account import UserAccountUpdate
    import app.repos.ticket_events_repo as ticket_repo_module
    import web_api.support_handlers as support_handlers

    person_id, queue_id, group_id = account_person
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login, issuer, subject, guid = "Oidc.Mixed", "https://sso.example.test", "mixed-subject", str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    for name, value in {"OIDC_ENABLED": True, "OIDC_ISSUER": issuer, "OIDC_AD_GUID_CLAIM": "ad_object_guid",
                        "OIDC_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                        "OIDC_REDIRECT_URI": "https://helpdesk.example.test/api/web/session/oidc/callback",
                        "ALLOW_INSECURE_DEV_DEFAULTS": False, "AUTH_UI_CONFIG_FALLBACK_ENABLED": False}.items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0)
    monkeypatch.setattr(ticket_repo_module, "unified_queue_enabled", lambda: False)
    monkeypatch.setattr(support_handlers, "unified_queue_enabled", lambda: False)
    async with maker() as session:
        session.add(UiUser(user_login=login, password_hash="unchanged", actor_role="support", is_active=True))
        inherited = TicketQueue(code="inherited-" + uuid.uuid4().hex[:8], name="Inherited queue", is_active=True)
        session.add(inherited)
        await session.flush()
        inherited_id = inherited.id
        session.add(AccessGroupQueueMember(group_id=group_id, queue_id=inherited_id))
        session.add(TicketQueueMember(queue_id=queue_id, actor_id=login.lower(), role_in_queue="queue_lead"))
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=login,
                    normalized_identifier=login.lower(), verified=True))
        session.add(ConfirmedIdentityBinding(person_id=person_id, user_login=login, issuer=issuer, subject=subject,
                    ad_object_guid=guid, confirmed_by="admin-test", verification_reference="Owner verified"))
        await session.flush()
        await UserAccountsService(session).save(person_id, UserAccountUpdate.model_validate({
            "user_login": login, "actor_role": "support", "is_active": True,
            "queue_ids": [queue_id], "group_ids": [group_id], "reason": "Save both login paths"}),
            actor_id="admin-test", actor_role="admin")
        session.add(OidcFlow(state_hash=oidc.digest("flow-state"), browser_hash=oidc.digest("flow-browser"),
                    nonce="flow-nonce", verifier_encrypted=oidc._cipher().encrypt(b"flow-verifier").decode(),
                    expires_at=now + timedelta(minutes=5)))
        await session.commit()

    @asynccontextmanager
    async def sessions():
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(oidc, "get_session", sessions)
    monkeypatch.setattr(auth_service_module, "get_session", sessions)
    monkeypatch.setattr(oidc, "_configured", lambda: None)
    monkeypatch.setattr(oidc, "check_rate_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(oidc, "metadata", AsyncMock(return_value={"token_endpoint": issuer + "/token", "jwks_uri": issuer + "/keys"}))
    monkeypatch.setattr(oidc, "_json", AsyncMock(return_value={}))
    monkeypatch.setattr(oidc, "validate_id_token", lambda *args: {"iss": issuer, "sub": subject,
                        "ad_object_guid": guid, "sid": "upstream-session", "exp": (now + timedelta(minutes=5)).timestamp()})
    monkeypatch.setattr(oidc, "_introspect", AsyncMock(return_value=True))

    @asynccontextmanager
    async def provider_client(**kwargs):
        yield SimpleNamespace(fetch_token=AsyncMock(return_value={"access_token": "fixture-access", "id_token": "fixture-id",
                              "expires_at": (now + timedelta(minutes=5)).timestamp()}))

    monkeypatch.setattr(oidc, "oauth_client", provider_client)
    callback = make_mocked_request("GET", "/api/web/session/oidc/callback?state=flow-state&code=fixture-code",
                                  headers={"Cookie": oidc.FLOW_COOKIE + "=flow-browser"})
    response = await oidc.handle_oidc_callback(callback)
    assert response.status == 302
    oidc_token = response.cookies[WEB_SESSION_COOKIE_NAME].value
    state = SimpleNamespace(users={})
    password_token = await AuthService(state).generate_ui_token(login, "support", expires_hours=1)
    app = web.Application()
    app["state"] = state
    actors = []
    for token in (password_token, oidc_token):
        request = make_mocked_request("GET", "/api/web/session", app=app,
                                      headers={"Cookie": WEB_SESSION_COOKIE_NAME + "=" + token})
        context = await extract_auth_context(request)
        assert context is not None
        actors.append(context.actor_id)
        async with maker() as session:
            assert await TicketAdminConfigRepo(session).get_effective_queue_member(queue_id, context.actor_id) is not None
            assert await TicketEventsRepo(session).is_actor_in_queue(queue_id, context.actor_id)
            assert await support_handlers._support_accessible_queue_ids(session, context) == {queue_id}
            access = AccessControlRepo(session)
            assert await access.get_actor_group_codes(context.actor_id)
            assert {row["queue_id"] for row in await access.get_actor_group_queues(context.actor_id)} == {inherited_id}
    assert actors == [login.lower(), login]
    async with maker() as session:
        from tickets.approval_policy import _resolve_approval_source
        from tickets.policy_action_dispatcher import _queue_members, _queue_leads

        assert await _queue_members(session, queue_id) == [login]
        assert await _queue_leads(session, queue_id) == [login]
        assert await _resolve_approval_source(session, SimpleNamespace(queue_id=queue_id), {"type": "queue_lead"}) == ("queue_lead", [login])
        users = await TicketEventsRepo(session).list_assignable_users_with_load(queue_id)
        assert [user["user_login"] for user in users] == [login]


@pytest.mark.asyncio
async def test_effective_membership_aliases_do_not_change_exact_mutations_or_non_ui_principals(test_engine, account_person, monkeypatch):
    from app.repos.access_control_repo import AccessControlRepo
    from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
    from app.repos.ticket_events_repo import TicketEventsRepo
    import app.repos.ticket_events_repo as ticket_repo_module

    monkeypatch.setattr(ticket_repo_module, "unified_queue_enabled", lambda: False)
    _, queue_id, group_id = account_person
    async with async_sessionmaker(test_engine)() as session:
        session.add(UiUser(user_login="Existing.Mixed", password_hash="unchanged", actor_role="support", is_active=True))
        for actor in ("Existing.Mixed", "Unknown.Actor"):
            session.add(TicketQueueMember(queue_id=queue_id, actor_id=actor))
            session.add(AccessGroupMember(group_id=group_id, actor_id=actor))
        await session.flush()
        queue_repo = TicketAdminConfigRepo(session)
        access = AccessControlRepo(session)
        assert await queue_repo.get_effective_queue_member(queue_id, "existing.mixed") is not None
        assert await access.get_actor_group_codes("existing.mixed")
        assert await queue_repo.get_queue_member(queue_id, "existing.mixed") is None
        assert not await queue_repo.delete_queue_member(queue_id, "existing.mixed")
        assert await queue_repo.get_queue_member(queue_id, "Existing.Mixed") is not None
        assert await queue_repo.get_effective_queue_member(queue_id, "Unknown.Actor") is not None
        assert await access.get_actor_group_codes("Unknown.Actor")
        for actor in ("EXISTING.MIXED", "unknown.actor"):
            assert await queue_repo.get_effective_queue_member(queue_id, actor) is None
            assert await access.get_actor_group_codes(actor) == []
            assert await access.get_actor_group_permissions(actor) == []
            assert await access.get_actor_group_queues(actor) == []
            assert not await TicketEventsRepo(session).is_actor_in_queue(queue_id, actor)


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("actor,users,expected", [
    ("Existing.Mixed", ["Existing.Mixed"], ("Existing.Mixed", "existing.mixed")),
    ("existing.mixed", ["Existing.Mixed"], ("Existing.Mixed", "existing.mixed")),
    ("EXISTING.MIXED", ["Existing.Mixed"], ("EXISTING.MIXED",)),
    ("Unknown.Actor", [], ("Unknown.Actor",)),
    ("same", ["Same", "same"], ()),
])
async def test_ui_membership_alias_resolution_is_bounded_and_fail_closed(actor, users, expected):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.repos.ui_actor_memberships import ui_actor_membership_ids

    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: users))))
    assert await ui_actor_membership_ids(session, actor) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["role", "password", "deactivate", "rollback"])
async def test_security_changes_revoke_tokens_in_same_transaction(test_client, test_engine, account_person, monkeypatch, change):
    from app.repos.access_control_repo import AccessControlRepo

    token_hash = "a" * 64
    maker = async_sessionmaker(test_engine)
    async with maker() as session:
        session.add(UiUser(user_login="account.new", password_hash="unchanged", actor_role="user", is_active=True))
        session.add(UiToken(token_hash=token_hash, token_prefix="fixture1", user_login="account.new", actor_role="user"))
        await session.commit()
    data = body(actor_role="user")
    if change == "role":
        data.pop("password")
        data["actor_role"] = "support"
    elif change == "deactivate":
        data.pop("password")
        data["is_active"] = False
    if change == "rollback":
        async def fail_audit(*args, **kwargs):
            raise RuntimeError("late save failure")
        monkeypatch.setattr(AccessControlRepo, "add_audit", fail_audit)
        data["actor_role"] = "support"
        data["is_active"] = False
    response = await test_client.put(f"/api/web/admin/users/{account_person[0]}/account", headers=ADMIN, json=data)
    assert response.status == (503 if change == "rollback" else 200)
    async with maker() as session:
        token = await session.get(UiToken, token_hash)
        assert (token.revoked_at is None) == (change == "rollback")
        if change == "rollback":
            user = await session.get(UiUser, "account.new")
            assert user.actor_role == "user" and user.is_active
            assert user.password_hash == "unchanged"


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["person", "queue", "group"])
async def test_rejects_archived_person_and_inactive_grant_targets(test_client, test_engine, account_person, target):
    person_id, queue_id, group_id = account_person
    async with async_sessionmaker(test_engine)() as session:
        if target == "person":
            (await session.get(RegistryPerson, person_id)).status = "archived"
        elif target == "queue":
            (await session.get(TicketQueue, queue_id)).is_active = False
        else:
            (await session.get(AccessGroup, group_id)).is_active = False
        await session.commit()
    response = await test_client.put(f"/api/web/admin/users/{person_id}/account", headers=ADMIN, json=body(queue_id, group_id))
    assert response.status in (400, 409)


@pytest.mark.asyncio
async def test_rolls_back_created_account_link_and_grants_if_audit_fails(test_client, test_engine, account_person, monkeypatch):
    from app.repos.access_control_repo import AccessControlRepo

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("injected late save failure")

    monkeypatch.setattr(AccessControlRepo, "add_audit", fail_audit)
    person_id, queue_id, group_id = account_person
    response = await test_client.put(f"/api/web/admin/users/{person_id}/account", headers=ADMIN, json=body(queue_id, group_id))
    assert response.status == 503
    assert PASSWORD not in await response.text()
    async with async_sessionmaker(test_engine)() as session:
        assert await session.get(UiUser, "account.new") is None
        assert not (await session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.person_id == person_id))).scalars().all()
        assert await session.get(AccessGroupMember, (group_id, "account.new")) is None
        assert not (await session.execute(select(TicketQueueMember).where(
            TicketQueueMember.actor_id == "account.new"))).scalars().all()
