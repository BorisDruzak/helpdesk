"""Helpdesk's explicit confirmed person authority, independent of OIDC transport."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import (ConfirmedIdentityBinding, IdentityMigrationCandidate, RegistryPerson,
                           RegistryPersonIdentity, UiUser, UiUserAudit)
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.ui_users_repo import VALID_ROLES


class IdentityError(Exception):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


def parse_identity(issuer, subject, ad_object_guid):
    if not isinstance(issuer, str) or not 1 <= len(issuer) <= 500:
        raise ValueError("invalid_issuer")
    url = urlsplit(issuer)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or issuer != issuer.strip():
        raise ValueError("invalid_issuer")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or any(ord(c) < 32 for c in subject):
        raise ValueError("invalid_subject")
    if not isinstance(ad_object_guid, str) or str(UUID(ad_object_guid)) != ad_object_guid:
        raise ValueError("invalid_ad_object_guid")
    return issuer, subject, ad_object_guid


class IdentityService:
    def __init__(self, session):
        self.session = session

    async def _active(self, binding):
        if binding.revoked_at is not None:
            raise IdentityError("identity_revoked", 403)
        person = await self.session.get(RegistryPerson, binding.person_id)
        user = await self.session.get(UiUser, binding.user_login)
        if not person or person.status != "active" or (person.metadata_json or {}).get("merged_into") or not user or not user.is_active or user.actor_role not in VALID_ROLES:
            raise IdentityError("identity_inactive", 403)
        # Legacy ownership remains independently explicit and verified.
        alias = (await self.session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.provider == "ui_login",
            func.lower(RegistryPersonIdentity.normalized_identifier) == user.user_login.lower(),
        ))).scalar_one_or_none()
        if alias is None or alias.person_id != person.person_id or not alias.verified or any((alias.metadata_json or {}).get(k) for k in ("collision_person_id", "merge_conflict")):
            raise IdentityError("verified_ui_login_required")
        return person, user

    async def resolve_binding(self, issuer, subject, ad_object_guid):
        issuer, subject, ad_object_guid = parse_identity(issuer, subject, ad_object_guid)
        rows = (await self.session.execute(select(ConfirmedIdentityBinding).where(or_(
            (ConfirmedIdentityBinding.issuer == issuer) & (ConfirmedIdentityBinding.subject == subject),
            ConfirmedIdentityBinding.ad_object_guid == ad_object_guid,
        )))).scalars().all()
        if not rows:
            pending = (await self.session.execute(select(IdentityMigrationCandidate.candidate_id).where(
                ((IdentityMigrationCandidate.issuer == issuer) & (IdentityMigrationCandidate.subject == subject)) |
                (IdentityMigrationCandidate.ad_object_guid == ad_object_guid)
            ).limit(1))).first()
            raise IdentityError("identity_unconfirmed" if pending else "identity_unknown", 409 if pending else 404)
        if len(rows) != 1 or (rows[0].issuer, rows[0].subject, rows[0].ad_object_guid) != (issuer, subject, ad_object_guid):
            raise IdentityError("identity_conflict")
        await self._active(rows[0])
        return rows[0]

    async def resolve(self, issuer, subject, ad_object_guid):
        binding = await self.resolve_binding(issuer, subject, ad_object_guid)
        person, _ = await self._active(binding)
        return dict(version=1, person_id=person.person_id, issuer=binding.issuer, subject=binding.subject,
                    ad_object_guid=binding.ad_object_guid, state="active", department_id=person.department_id)

    async def propose(self, *, person_id, user_login, issuer, subject, ad_object_guid, actor_id):
        issuer, subject, ad_object_guid = parse_identity(issuer, subject, ad_object_guid)
        if not actor_id or not person_id or not user_login or len(user_login) > 100:
            raise ValueError("invalid_candidate")
        candidate = IdentityMigrationCandidate(person_id=person_id, user_login=user_login, issuer=issuer,
            subject=subject, ad_object_guid=ad_object_guid, created_by=actor_id, state="pending")
        self.session.add(candidate)
        await self.session.commit()
        return candidate

    def _audit(self, binding, action, actor_id, reference=None):
        if not actor_id:
            raise ValueError("actor_required")
        self.session.add(UiUserAudit(user_login=binding.user_login, action=action, actor_id=actor_id,
            details_json={"binding_id": binding.binding_id, "person_id": binding.person_id, "verification_reference": reference}))

    async def confirm(self, candidate_id, *, actor_id, verification_reference):
        if not actor_id or not isinstance(verification_reference, str) or not verification_reference.strip() or len(verification_reference) > 1000:
            raise ValueError("verification_reference_required")
        candidate = (await self.session.execute(select(IdentityMigrationCandidate).where(
            IdentityMigrationCandidate.candidate_id == candidate_id).with_for_update())).scalar_one_or_none()
        if not candidate or candidate.state != "pending":
            raise IdentityError("candidate_not_pending")
        # Serialize against merges and other account migration operations.
        await self.session.execute(select(RegistryPerson).where(RegistryPerson.person_id == candidate.person_id).with_for_update())
        await self.session.execute(select(UiUser).where(UiUser.user_login == candidate.user_login).with_for_update())
        binding = ConfirmedIdentityBinding(person_id=candidate.person_id, user_login=candidate.user_login,
            issuer=candidate.issuer, subject=candidate.subject, ad_object_guid=candidate.ad_object_guid,
            confirmed_by=actor_id, verification_reference=verification_reference)
        await self._active(binding)
        try:
            self.session.add(binding)
            await self.session.flush()
            candidate.state = "confirmed"
            self._audit(binding, "sso_identity_confirmed", actor_id, verification_reference)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            await self.session.execute(update(IdentityMigrationCandidate).where(IdentityMigrationCandidate.candidate_id == candidate_id).values(state="conflict"))
            await self.session.commit()
            raise IdentityError("identity_conflict") from None
        return binding

    async def revoke(self, binding_id, *, actor_id):
        binding = await self.session.get(ConfirmedIdentityBinding, binding_id)
        if not binding:
            raise IdentityError("identity_unknown", 404)
        binding.revoked_at, binding.revoked_by = datetime.now(timezone.utc), actor_id
        self._audit(binding, "sso_identity_revoked", actor_id)
        await AuthTokensRepo(self.session).revoke_active_ui_tokens_for_user(binding.user_login, commit=False)
        await self.session.commit()

    async def migrate_password(self, binding_id, *, actor_id, verification_reference):
        if not verification_reference or len(verification_reference) > 1000:
            raise ValueError("verification_reference_required")
        binding = await self.session.get(ConfirmedIdentityBinding, binding_id)
        if not binding:
            raise IdentityError("identity_unknown", 404)
        _, user = await self._active(binding)
        # A reference alone cannot prove SSO worked: require an issued persisted OIDC session.
        from app.db.models import OidcSession, UiToken
        from auth.oidc import validate_oidc_session
        pilot = (await self.session.execute(select(UiToken).join(OidcSession, UiToken.token_hash == OidcSession.token_hash).where(
            OidcSession.binding_id == binding_id, OidcSession.max_expires_at > datetime.now(timezone.utc),
            UiToken.auth_method == "oidc", UiToken.expires_at > datetime.now(timezone.utc), UiToken.revoked_at.is_(None)
        ).order_by(UiToken.created_at.desc()).limit(1))).scalar_one_or_none()
        if not pilot or not await validate_oidc_session(self.session, pilot, user):
            raise IdentityError("verified_sso_session_required")
        user.password_login_enabled = False
        # Migration must also remove authority already issued through the password path.
        await self.session.execute(update(UiToken).where(UiToken.user_login == user.user_login,
            UiToken.auth_method == "password", UiToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
        self._audit(binding, "sso_password_login_disabled", actor_id, verification_reference)
        await self.session.commit()
