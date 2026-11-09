import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import config
from app.db.models import RegistryDepartment, RegistryLocation, RegistryPerson, RegistryPersonIdentity, UiToken, UiUser
from auth.password_service import hash_password
from auth.worktime_handoff import HandoffError, WorktimeHandoffService, pkce_challenge

pytestmark=[pytest.mark.asyncio,pytest.mark.db_cleanup('registry_access')]
CALLBACK='https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/callback'


async def seeded(test_engine,monkeypatch):
    monkeypatch.setattr(config,'WORKTIME_HANDOFF_ENABLED',True,raising=False)
    monkeypatch.setattr(config,'SERVER_PUBLIC_BASE_URL','https://helpdesk-staging.sosnadmin.local')
    monkeypatch.setattr(config,'WORKTIME_PORTAL_URL','https://endpoint-staging.sosnadmin.local/employee')
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    raw=secrets.token_hex(32);digest=hashlib.sha256(raw.encode()).hexdigest()
    async with maker.begin() as session:
        department,location,person=(str(uuid.uuid4()) for _ in range(3))
        login='handoff-'+uuid.uuid4().hex
        session.add_all([RegistryDepartment(department_id=department,name='Handoff isolated fixture',status='active',source='test',metadata_json={}),
            RegistryLocation(location_id=location,building='Handoff isolated fixture',display_name='Handoff isolated fixture',status='active',source='test',metadata_json={})])
        await session.flush()
        # The selective production port retains the old registration UI. Build
        # an owned complete fixture through the existing registry models, never
        # import the unrelated staging requester-registration implementation.
        session.add_all([RegistryPerson(person_id=person,display_name='Handoff isolated fixture',full_name='Handoff isolated fixture',department_id=department,location_id=location,phone='0000',status='active',source='test',metadata_json={}),
            UiUser(user_login=login,password_hash=hash_password('Synthetic-handoff-fixture-43!'),actor_role='user',is_active=True)])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person,provider='ui_login',identifier=login,normalized_identifier=login,verified=True))
        session.add(UiToken(token_hash=digest,token_prefix=raw[:8],user_login=login,actor_role='user',auth_method='password',expires_at=datetime.now(timezone.utc)+timedelta(hours=2)))
    return maker,digest,login


async def test_code_is_one_use_with_pkce_and_live_source_revocation(test_engine,monkeypatch):
    maker,digest,login=await seeded(test_engine,monkeypatch);verifier=secrets.token_urlsafe(32)
    async with maker.begin() as session:
        code=await WorktimeHandoffService(session).authorize(digest,pkce_challenge(verifier),CALLBACK)
    async with maker.begin() as session:
        with pytest.raises(HandoffError):await WorktimeHandoffService(session).exchange(code,secrets.token_urlsafe(32),CALLBACK)
    async def exchange():
        try:
            async with maker.begin() as session:return await WorktimeHandoffService(session).exchange(code,verifier,CALLBACK)
        except HandoffError:return None
    results=await asyncio.gather(exchange(),exchange());assert sum(value is not None for value in results)==1
    result=next(value for value in results if value)
    assert set(result)=={'version','handle','person_id','department_id','expires_at'}
    async with maker.begin() as session:
        lease=await WorktimeHandoffService(session).introspect(result['handle']);assert lease['person_id']==result['person_id']
        token=await session.get(UiToken,digest);token.revoked_at=datetime.now(timezone.utc)
    async with maker.begin() as session:
        with pytest.raises(HandoffError) as error:await WorktimeHandoffService(session).introspect(result['handle'])
        assert error.value.status==401


async def test_disabled_password_authority_and_expired_codes_fail(test_engine,monkeypatch):
    maker,digest,login=await seeded(test_engine,monkeypatch);verifier=secrets.token_urlsafe(32)
    now=datetime.now(timezone.utc)
    async with maker.begin() as session:
        code=await WorktimeHandoffService(session,now=now).authorize(digest,pkce_challenge(verifier),CALLBACK)
    async with maker.begin() as session:
        with pytest.raises(HandoffError):await WorktimeHandoffService(session,now=now+timedelta(minutes=2)).exchange(code,verifier,CALLBACK)
        user=await session.get(UiUser,login);user.password_login_enabled=False
    async with maker.begin() as session:
        with pytest.raises(HandoffError):await WorktimeHandoffService(session).authorize(digest,pkce_challenge(verifier),CALLBACK)


async def test_incomplete_profile_and_relinked_alias_revoke_existing_lease(test_engine,monkeypatch):
    from sqlalchemy import select
    maker,digest,login=await seeded(test_engine,monkeypatch);verifier=secrets.token_urlsafe(32)
    monkeypatch.setattr(config,'PROFILE_COMPLETION_REQUIRED',False)
    async with maker.begin() as session:
        code=await WorktimeHandoffService(session).authorize(digest,pkce_challenge(verifier),CALLBACK)
        lease=await WorktimeHandoffService(session).exchange(code,verifier,CALLBACK)
        person=await session.get(RegistryPerson,lease['person_id']);person.phone=None
    async with maker.begin() as session:
        with pytest.raises(HandoffError) as error:await WorktimeHandoffService(session).introspect(lease['handle'])
        assert error.value.code=='profile_incomplete'
        person=await session.get(RegistryPerson,lease['person_id']);person.phone='0000'
        alias=await session.scalar(select(RegistryPersonIdentity).where(RegistryPersonIdentity.provider=='ui_login',RegistryPersonIdentity.person_id==person.person_id))
        alias.verified=False
    async with maker.begin() as session:
        with pytest.raises(HandoffError):await WorktimeHandoffService(session).introspect(lease['handle'])
