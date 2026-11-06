"""Admin person/account commands; the caller owns the complete transaction.

Do not call committing UiUsersRepo update/password methods in this service.
All failures must escape the get_session context before being translated to HTTP.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import (
    AccessGroup, AccessGroupMember, ConfirmedIdentityBinding, RegistryPerson, RegistryPersonIdentity,
    TicketQueue, TicketQueueMember, UiUser, UiUserAudit,
)
from app.repos.access_control_repo import AccessControlRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.registration_repo import RegistrationRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ui_users_repo import UiUsersRepo, normalize_user_login
from auth.password_service import PasswordPolicyError, hash_password, validate_password_policy
from registry.admin_operations_service import RegistryAdminOperationsService
from web_api.dto.user_account import UserAccountUpdate


class AccountError(Exception):
    def __init__(self, message: str, code: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class UserAccountsService:
    def __init__(self, session):
        self.session = session

    async def _person(self, person_id: str, *, lock: bool = False):
        statement = select(RegistryPerson).where(RegistryPerson.person_id == person_id)
        if lock:
            statement = statement.with_for_update()
        person = (await self.session.execute(statement)).scalar_one_or_none()
        if person is None:
            raise AccountError("Сотрудник не найден", "PERSON_NOT_FOUND", 404)
        return person

    async def _users(self, login: str, *, lock: bool = False):
        statement = select(UiUser).where(func.lower(func.trim(UiUser.user_login)) == normalize_user_login(login))
        if lock:
            statement = statement.with_for_update()
        users = list((await self.session.execute(statement)).scalars().all())
        if len(users) > 1:
            raise AccountError("Найдено несколько учетных записей с одинаковым логином", "AMBIGUOUS_LOGIN", 409)
        return users

    async def snapshot(self, user) -> dict:
        actor_ids = (user.user_login, normalize_user_login(user.user_login))
        queues = (await self.session.execute(select(TicketQueueMember.queue_id).where(
            TicketQueueMember.actor_id.in_(actor_ids)))).scalars().all()
        groups = (await self.session.execute(select(AccessGroupMember.group_id).where(
            AccessGroupMember.actor_id.in_(actor_ids)))).scalars().all()
        return {"user_login": user.user_login, "actor_role": user.actor_role, "is_active": bool(user.is_active),
                "queue_ids": sorted(set(queues)), "group_ids": sorted(set(groups))}

    async def _check_confirmed_owner(self, person_id: str, login: str, *, lock: bool = False) -> None:
        statement = select(ConfirmedIdentityBinding).where(
            func.lower(func.trim(ConfirmedIdentityBinding.user_login)) == normalize_user_login(login))
        if lock:
            statement = statement.with_for_update()
        bindings = (await self.session.execute(statement)).scalars().all()
        if any(binding.person_id != person_id for binding in bindings):
            raise AccountError("Логин уже связан с другим сотрудником", "IDENTITY_COLLISION", 409)

    async def _save_grants(self, actor_id: str, queue_ids: set[int], group_ids: set[int]) -> None:
        # Preserve both supported token spellings during reads, but store only
        # one membership for the exact UiUser login, avoiding duplicate operators.
        actor_ids = (actor_id, normalize_user_login(actor_id))
        queues = list((await self.session.execute(select(TicketQueueMember).where(
            TicketQueueMember.actor_id.in_(actor_ids)).with_for_update())).scalars().all())
        canonical_queues = {row.queue_id for row in queues if row.actor_id == actor_id}
        roles = {row.queue_id: row.role_in_queue for row in queues}
        roles.update({row.queue_id: row.role_in_queue for row in queues if row.actor_id == actor_id})
        repo = TicketAdminConfigRepo(self.session)
        for row in queues:
            if row.queue_id not in queue_ids or row.actor_id != actor_id:
                await repo.delete_queue_member(row.queue_id, row.actor_id)
        for queue_id in sorted(queue_ids - canonical_queues):
            await repo.put_queue_member(queue_id, actor_id, role_in_queue=roles.get(queue_id))
        groups = list((await self.session.execute(select(AccessGroupMember).where(
            AccessGroupMember.actor_id.in_(actor_ids)).with_for_update())).scalars().all())
        canonical_groups = {row.group_id for row in groups if row.actor_id == actor_id}
        for row in groups:
            if row.group_id not in group_ids or row.actor_id != actor_id:
                await self.session.delete(row)
        await self.session.flush()
        for group_id in sorted(group_ids - canonical_groups):
            self.session.add(AccessGroupMember(group_id=group_id, actor_id=actor_id))
        await self.session.flush()

    async def list_accounts(self, person_id: str, *, user_login: str | None = None) -> list[dict]:
        await self._person(person_id)
        if user_login is not None:
            users = await self._users(user_login)
            if not users:
                raise AccountError("Учетная запись не найдена", "USER_NOT_FOUND", 404)
            owners = (await self.session.execute(select(RegistryPersonIdentity.person_id).where(
                RegistryPersonIdentity.provider == "ui_login",
                func.lower(func.trim(RegistryPersonIdentity.normalized_identifier)) == normalize_user_login(user_login)
            ))).scalars().all()
            if any(owner != person_id for owner in owners):
                raise AccountError("Логин уже связан с другим сотрудником", "IDENTITY_COLLISION", 409)
            await self._check_confirmed_owner(person_id, user_login)
            return [await self.snapshot(users[0])]
        identities = (await self.session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.person_id == person_id, RegistryPersonIdentity.provider == "ui_login"
        ).order_by(RegistryPersonIdentity.normalized_identifier))).scalars().all()
        accounts = []
        for identity in identities:
            users = await self._users(identity.normalized_identifier)
            if users:
                await self._check_confirmed_owner(person_id, users[0].user_login)
                accounts.append(await self.snapshot(users[0]))
        return accounts

    async def save(self, person_id: str, payload: UserAccountUpdate, *, actor_id: str, actor_role: str) -> dict:
        person = await self._person(person_id, lock=True)
        if person.status != "active":
            raise AccountError("Учетная запись доступна только для действующего сотрудника", "PERSON_INACTIVE", 409)
        login = normalize_user_login(payload.user_login)
        # Consistent admin lock order prevents two commands from removing the last
        # active administrator concurrently. Legacy admin APIs keep their own rules.
        admins = list((await self.session.execute(select(UiUser).where(
            UiUser.actor_role == "admin", UiUser.is_active.is_(True)
        ).order_by(UiUser.user_login).with_for_update())).scalars().all())
        users = await self._users(login, lock=True)
        user = users[0] if users else None
        await self._check_confirmed_owner(person_id, login, lock=True)
        identities = list((await self.session.execute(select(RegistryPersonIdentity).where(
            RegistryPersonIdentity.provider == "ui_login",
            func.lower(func.trim(RegistryPersonIdentity.normalized_identifier)) == login
        ).with_for_update())).scalars().all())
        if any(identity.person_id != person_id for identity in identities):
            raise AccountError("Логин уже связан с другим сотрудником", "IDENTITY_COLLISION", 409)
        if len(identities) > 1:
            raise AccountError("Неоднозначная привязка логина", "AMBIGUOUS_LOGIN", 409)
        removing_admin = payload.actor_role != "admin" or not payload.is_active
        if normalize_user_login(actor_id) == login and removing_admin:
            raise AccountError("Нельзя отключить свою учетную запись или снять свою роль администратора", "SELF_LOCKOUT", 409)
        if user and user.actor_role == "admin" and user.is_active and removing_admin and len(admins) <= 1:
            raise AccountError("Нельзя отключить последнего администратора", "LAST_ADMIN", 409)
        queue_ids, group_ids = set(payload.queue_ids), set(payload.group_ids)
        for model, ids, code, message in (
            (TicketQueue, queue_ids, "INVALID_QUEUE", "Выберите действующие очереди"),
            (AccessGroup, group_ids, "INVALID_GROUP", "Выберите действующие группы доступа"),
        ):
            if ids:
                targets = (await self.session.execute(select(model).where(model.id.in_(sorted(ids)))
                           .order_by(model.id).with_for_update())).scalars().all()
                if len(targets) != len(ids) or any(not row.is_active for row in targets):
                    raise AccountError(message, code)
        password = payload.password.get_secret_value() if payload.password is not None else None
        from config import AUTH_UI_DB_USERS_ENABLED, OIDC_ENABLED

        if (user is None or password is not None) and not (AUTH_UI_DB_USERS_ENABLED or OIDC_ENABLED):
            raise AccountError("Вход с учетными записями базы данных отключен", "LOCAL_AUTH_DISABLED", 409)
        if user is not None and password is not None and not user.password_login_enabled:
            raise AccountError("Для этой учетной записи вход с локальным паролем отключен", "PASSWORD_LOGIN_DISABLED", 409)
        if user is None and password is None:
            raise AccountError("Для новой учетной записи требуется пароль", "PASSWORD_REQUIRED")
        if password is not None:
            try:
                validate_password_policy(password, login=login)
            except PasswordPolicyError as exc:
                raise AccountError(str(exc), "PASSWORD_POLICY_ERROR") from None
        reason = payload.reason.replace(password, "[REDACTED]") if password else payload.reason
        before = await self.snapshot(user) if user else None
        if user is None:
            user = await UiUsersRepo(self.session).create_user(
                login, hash_password(password), actor_role=payload.actor_role, actor_id=actor_id, commit=False)
        else:
            user.actor_role = payload.actor_role
            if password is not None:
                user.password_hash = hash_password(password)
                user.failed_attempts = 0
                user.locked_until = None
        user.is_active = payload.is_active
        if not payload.is_active or password is not None or (before and before["actor_role"] != payload.actor_role):
            await AuthTokensRepo(self.session).revoke_active_ui_tokens_for_user(user.user_login, commit=False)
        if identities:
            # Older identity rows may have noncanonical casing. Correct this
            # only after ownership validation, before the canonical repo lookup.
            identities[0].normalized_identifier = login
            await self.session.flush()
        identity = await RegistrationRepo(self.session).create_or_update_person_identity(
            person_id=person_id, provider="ui_login", identifier=user.user_login, verified=True,
            source="admin_manual", metadata={"reason": reason, "ui_user_login": user.user_login})
        if identity is None or identity.person_id != person_id:
            raise AccountError("Логин уже связан с другим сотрудником", "IDENTITY_COLLISION", 409)
        await self._save_grants(user.user_login, queue_ids, group_ids)
        after = await self.snapshot(user)
        details = {"person_id": person_id, "reason": reason, "before": before, "after": after}
        self.session.add(UiUserAudit(user_login=user.user_login, actor_id=actor_id,
                                     action="person_account_saved", details_json=details))
        await AccessControlRepo(self.session).add_audit(
            entity_type="user_account", entity_id=user.user_login, action="person_account_saved",
            actor_id=actor_id, actor_role=actor_role, before_json=before,
            after_json={**after, "person_id": person_id, "reason": reason})
        await RegistryAdminOperationsService(self.session).append_event(
            object_type="identity", object_id=identity.identity_id, event_type="identity_updated",
            actor_id=actor_id, actor_role=actor_role, reason=reason, related_person_id=person_id, payload=details)
        return after
