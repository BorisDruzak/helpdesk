import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, RegistryPersonIdentity, UiToken, UiUser, UiUserAudit
from scripts.helpdesk_staging_user_cleanup import apply_to_session, build_plan

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("registry_access")]


async def test_cleanup_preserves_protected_users_history_and_audits_revocation(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        # This file uses only the isolated migration fixture, no HTTP client/user seeds.
        assert list((await session.execute(select(UiUser))).scalars()) == []
        roles = {"admin": "admin", "admin-2": "admin", "bdryzhak": "user", "studio.user": "support"}
        session.add_all([UiUser(user_login=login, password_hash="unchanged-test-hash", actor_role=role, is_active=True) for login, role in roles.items()])
        session.add(RegistryPerson(person_id="fixture-admin-person", display_name="Тестовый Пользователь 1", full_name="Тестовый Пользователь 1", status="self_reported", source="manual"))
        await session.flush()
        session.add(RegistryPersonIdentity(identity_id="fixture-admin-identity", person_id="fixture-admin-person", provider="ui_login", identifier="admin", normalized_identifier="admin", verified=True))
        session.add(UiToken(token_hash="synthetic-cleanup-token-hash", token_prefix="fixture", user_login="studio.user", actor_role="support"))
        await session.commit()
        users = list((await session.execute(select(UiUser))).scalars())
        plan = build_plan(users)
        with pytest.raises(ValueError, match="state changed"):
            await apply_to_session(session, "wrong-plan")
        await session.rollback()
        result = await apply_to_session(session, plan["fingerprint"])
        assert result["revoked_ui_tokens"] == 1 and result["admin_fixture_label_removed"]
        await session.commit()
        all_users = list((await session.execute(select(UiUser))).scalars())
        assert len(all_users) == 4
        assert sorted(u.user_login for u in all_users if u.is_active) == ["admin", "admin-2", "bdryzhak"]
        assert all(u.password_hash == "unchanged-test-hash" and u.actor_role == roles[u.user_login] for u in all_users)
        person = await session.get(RegistryPerson, "fixture-admin-person")
        assert person.display_name == "admin" and person.full_name is None
        assert (await session.get(RegistryPersonIdentity, "fixture-admin-identity")).person_id == person.person_id
        token = await session.get(UiToken, "synthetic-cleanup-token-hash")
        assert token.revoked_at is not None
        audits = list((await session.execute(select(UiUserAudit).where(UiUserAudit.user_login == "studio.user"))).scalars())
        assert len(audits) == 1 and audits[0].action == "disabled_by_staging_cleanup"
        # A repeated fresh plan is harmless; no new audit or identity change.
        again = await apply_to_session(session, build_plan(all_users)["fingerprint"])
        assert again["active_to_disable"] == 0 and again["revoked_ui_tokens"] == 0
        assert again["admin_fixture_label_removed"] is False
        await session.rollback()
