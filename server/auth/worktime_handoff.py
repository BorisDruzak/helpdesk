"""Closed WorkTime handoff v1, bound to the original live Helpdesk authority."""
import base64
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from urllib.parse import urlsplit, parse_qs

import config
from sqlalchemy import select
from app.db.models import WorktimeAuthorizationCode, WorktimeSessionLease, UiUserAudit
from auth.worktime_authority import HandoffError, active_source, active_person


def digest(value):return hashlib.sha256(value.encode('ascii')).hexdigest()


def require_opaque(value, *, verifier=False):
    pattern=r'[A-Za-z0-9._~-]{43,128}' if verifier else r'[A-Za-z0-9_-]{43,128}'
    if not isinstance(value,str) or re.fullmatch(pattern,value) is None:raise HandoffError('invalid_protocol_value',400)
    return value


def pkce_challenge(value):
    require_opaque(value,verifier=True)
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


def fixed_worktime_endpoints(origin,portal):
    expected={'https://helpdesk.sosnadmin.local':'https://endpoint.sosnadmin.local',
        'https://helpdesk-staging.sosnadmin.local':'https://endpoint-staging.sosnadmin.local'}.get(origin)
    if expected is None or portal!=expected+'/employee':raise HandoffError('handoff_unavailable',503)
    return expected,expected+'/auth/worktime/helpdesk/callback'


def configured_callback():
    if not getattr(config,'WORKTIME_HANDOFF_ENABLED',False):raise HandoffError('handoff_disabled',404)
    if not config.WEB_SESSION_COOKIE_SECURE or not config.WEB_CSRF_SAME_ORIGIN_ENABLED:raise HandoffError('handoff_unavailable',503)
    return fixed_worktime_endpoints(config.SERVER_PUBLIC_BASE_URL,config.WORKTIME_PORTAL_URL)[1]


def safe_worktime_continuation(value):
    """Only this closed internal continuation survives an optional AD round trip."""
    try:
        if not isinstance(value,str) or len(value)>1800:return '/app'
        target=urlsplit(value)
        if target.scheme or target.netloc or target.fragment or target.path!='/app/worktime/connect':return '/app'
        params=parse_qs(target.query,strict_parsing=True,keep_blank_values=True)
        if set(params)!={'state','code_challenge','code_challenge_method','redirect_uri'} or any(len(items)!=1 for items in params.values()):return '/app'
        if params['redirect_uri'][0]!=configured_callback() or params['code_challenge_method']!=['S256']:return '/app'
        require_opaque(params['state'][0]);require_opaque(params['code_challenge'][0])
        if len(params['code_challenge'][0])!=43:return '/app'
        return value
    except (HandoffError,ValueError,TypeError):return '/app'


def person_payload(person):
    return {'version':1,'state':'active','person_id':str(person.person_id),'department_id':str(person.department_id) if person.department_id else None}


class WorktimeHandoffService:
    def __init__(self,session,*,now=None):self.session=session;self.now=now or datetime.now(timezone.utc)

    async def authorize(self,source_hash,challenge,callback):
        if callback!=configured_callback():raise HandoffError('invalid_callback',400)
        if len(require_opaque(challenge))!=43:raise HandoffError('invalid_challenge',400)
        token,person=await active_source(self.session,source_hash)
        code=secrets.token_urlsafe(32)
        self.session.add(WorktimeAuthorizationCode(code_hash=digest(code),source_token_hash=token.token_hash,
            person_id=person.person_id,challenge=challenge,callback=callback,expires_at=self.now+timedelta(seconds=60)))
        self.session.add(UiUserAudit(user_login=token.user_login,action='worktime.code_issued',actor_id=token.user_login,details_json={'person_id':str(person.person_id)}))
        await self.session.flush()
        return code

    async def exchange(self,code,verifier,callback):
        if callback!=configured_callback():raise HandoffError('invalid_callback',400)
        require_opaque(code);challenge=pkce_challenge(verifier)
        row=await self.session.scalar(select(WorktimeAuthorizationCode).where(WorktimeAuthorizationCode.code_hash==digest(code)).with_for_update().execution_options(populate_existing=True))
        if row is None or row.consumed_at is not None or row.expires_at<=self.now or row.callback!=callback or not secrets.compare_digest(row.challenge,challenge):
            raise HandoffError('invalid_grant',400)
        token,person=await active_source(self.session,row.source_token_hash)
        if person.person_id!=row.person_id:raise HandoffError()
        handle=secrets.token_urlsafe(32)
        expiry=min(token.expires_at or self.now+timedelta(hours=8),self.now+timedelta(hours=8))
        row.consumed_at=self.now
        self.session.add(WorktimeSessionLease(handle_hash=digest(handle),source_token_hash=token.token_hash,person_id=person.person_id,expires_at=expiry))
        self.session.add(UiUserAudit(user_login=token.user_login,action='worktime.lease_issued',actor_id='endpoint-worktime',details_json={'person_id':str(person.person_id)}))
        await self.session.flush()
        return {'version':1,'handle':handle,'person_id':str(person.person_id),'department_id':str(person.department_id) if person.department_id else None,'expires_at':expiry.isoformat()}

    async def introspect(self,handle):
        configured_callback();require_opaque(handle)
        lease=await self.session.get(WorktimeSessionLease,digest(handle))
        if lease is None or lease.expires_at<=self.now:raise HandoffError()
        token,person=await active_source(self.session,lease.source_token_hash)
        if person.person_id!=lease.person_id:raise HandoffError()
        return dict(person_payload(person),expires_at=min(lease.expires_at,token.expires_at or lease.expires_at).isoformat())

    async def resolve_person(self,person_id):
        configured_callback()
        try:
            if str(UUID(person_id))!=person_id:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise HandoffError('invalid_person',400) from None
        return person_payload(await active_person(self.session,person_id))
