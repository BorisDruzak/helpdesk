from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from auth.worktime_handoff import HandoffError, fixed_worktime_endpoints, pkce_challenge, require_opaque
from app.repos.auth_tokens_repo import AuthTokensRepo

pytestmark = pytest.mark.no_db


def test_fixed_environment_pair_and_pkce_reference_vector():
    assert fixed_worktime_endpoints('https://helpdesk-staging.sosnadmin.local', 'https://endpoint-staging.sosnadmin.local/employee') == (
        'https://endpoint-staging.sosnadmin.local', 'https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/callback')
    assert pkce_challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk') == 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'


@pytest.mark.parametrize('portal', ['https://endpoint.sosnadmin.local/employee', 'https://endpoint-staging.sosnadmin.local.evil.test/employee', 'https://endpoint-staging.sosnadmin.local/employee?person_id=other', 'http://endpoint-staging.sosnadmin.local/employee'])
def test_environment_mismatch_and_request_supplied_targets_fail(portal):
    with pytest.raises(HandoffError):
        fixed_worktime_endpoints('https://helpdesk-staging.sosnadmin.local', portal)


@pytest.mark.parametrize('value', ['', 'a'*42, 'a'*129, 'a'*43+'\n', 'ы'*43])
def test_malformed_protocol_secrets_fail_without_echo(value):
    with pytest.raises(HandoffError) as error:
        require_opaque(value)
    assert value not in str(error.value) if value else True


@pytest.mark.asyncio
async def test_stored_source_hash_retains_rotation_grace_without_committing():
    now=datetime.now(timezone.utc)
    record=SimpleNamespace(token_hash='a'*64,revoked_at=None,expires_at=now+timedelta(hours=1),replaced_by_token_hash='b'*64,rotated_at=now-timedelta(minutes=6))
    session=SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda:record)),commit=AsyncMock(),flush=AsyncMock())
    repo=AuthTokensRepo(session)
    assert await repo.verify_ui_token_hash('a'*64,commit=False) is None
    record.rotated_at=now-timedelta(minutes=1)
    assert await repo.verify_ui_token_hash('a'*64,commit=False) is record
    session.commit.assert_not_called()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_worktime_completion_is_independent_of_optional_ticket_profile_gate(monkeypatch):
    from auth import worktime_authority as authority
    resolver=SimpleNamespace(resolve_person_for_web_user=AsyncMock(return_value=object()),build_profile_completion=lambda *args,**kwargs:{'complete':False,'blocks':{'ticket_create':False}})
    monkeypatch.setattr(authority,'RequesterIdentityResolver',lambda session:resolver)
    monkeypatch.setattr(authority,'RequesterProfileSchemaService',lambda session:SimpleNamespace(get_schema=AsyncMock(return_value={})))
    with pytest.raises(HandoffError) as error:await authority.complete_person(object(),'fixture')
    assert error.value.code=='profile_incomplete'
