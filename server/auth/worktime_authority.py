"""Database-only source authority; never accepts legacy in-memory tokens."""
from sqlalchemy import select, func
from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.ui_users_repo import VALID_ROLES
from app.repos.registration_repo import normalize_identifier, is_person_active
from auth.service import AuthService
from requester.identity_service import RequesterIdentityResolver
from registry.profile_schema_service import RequesterProfileSchemaService


class HandoffError(Exception):
    def __init__(self, code='invalid_authority', status=401):
        self.code=code;self.status=status
        super().__init__(code)


async def complete_person(session,login):
    resolver=RequesterIdentityResolver(session)
    person=await resolver.resolve_person_for_web_user(login)
    schema=await RequesterProfileSchemaService(session).get_schema()
    if person is None or resolver.build_profile_completion(person,profile_schema=schema).get('complete') is not True:
        raise HandoffError('profile_incomplete',403)
    return person


async def active_source(session, token_hash):
    token=await AuthTokensRepo(session).verify_ui_token_hash(token_hash,commit=False)
    if token is None or token.auth_method not in {'password','oidc'}:
        raise HandoffError()
    user=await session.get(UiUser,token.user_login)
    if user is None or not user.is_active or user.actor_role not in VALID_ROLES:
        raise HandoffError()
    if token.auth_method=='password' and not user.password_login_enabled:
        raise HandoffError()
    if await AuthService._registry_person_block_for_ui_user(session,user.user_login):
        raise HandoffError()
    if token.auth_method=='oidc':
        from auth.oidc import validate_oidc_session, OidcAuthorityUnavailable
        try:
            if not await validate_oidc_session(session,token,user,raise_unavailable=True):raise HandoffError()
        except OidcAuthorityUnavailable:
            raise HandoffError('source_unavailable',503) from None
    identity=await session.scalar(select(RegistryPersonIdentity).where(
        RegistryPersonIdentity.provider=='ui_login',RegistryPersonIdentity.verified.is_(True),
        RegistryPersonIdentity.normalized_identifier==normalize_identifier('ui_login',user.user_login)))
    if identity is None:raise HandoffError('profile_incomplete',403)
    person=await complete_person(session,user.user_login)
    if person.person_id!=identity.person_id or not is_person_active(person):raise HandoffError()
    return token,person


async def active_person(session, person_id):
    person=await session.get(RegistryPerson,person_id)
    if not is_person_active(person):raise HandoffError('person_unavailable',403)
    users=(await session.scalars(select(UiUser).join(RegistryPersonIdentity,
        func.lower(UiUser.user_login)==RegistryPersonIdentity.normalized_identifier).where(
        RegistryPersonIdentity.person_id==person_id,RegistryPersonIdentity.provider=='ui_login',
        RegistryPersonIdentity.verified.is_(True),UiUser.is_active.is_(True)))).all()
    for user in users:
        if user.actor_role not in VALID_ROLES:continue
        if await AuthService._registry_person_block_for_ui_user(session,user.user_login):continue
        try:resolved=await complete_person(session,user.user_login)
        except HandoffError:continue
        if resolved.person_id==person_id:return person
    raise HandoffError('person_unavailable',403)
