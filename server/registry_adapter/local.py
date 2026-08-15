"""Local compatibility adapter for the RegistryPort boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import logging
import re
from types import SimpleNamespace
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

try:
    from domain_ports.registry import RegistryAvailability
    from domain_ports.registry_contracts import (
        AccountStatusOutcome,
        AccountStatusProjection,
        ActiveBindingOutcome,
        ActiveBindingProjection,
        AudienceProjection,
        AudienceProjectionOutcome,
        AudienceRef,
        BindingRef,
        BindingRevocationRequest,
        DeviceContextOutcome,
        DeviceContextProjection,
        DeviceRef,
        InventoryQualityOutcome,
        InventoryQualityProjection,
        DirectoryPersonProjection,
        DirectorySearchOutcome,
        DirectorySearchProjection,
        DirectorySearchText,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryHistoryEventProjection,
        RegistryInvalidProjection,
        RegistryNotFound,
        RegistryReadActor,
        RegistryUnavailable,
        RequesterRef,
        RequesterHistoryOutcome,
        RequesterHistoryProjection,
        RequesterProfileOutcome,
        RequesterProfileProjection,
        RequesterSnapshot,
        RequesterSnapshotOutcome,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"domain_ports", "domain_ports.registry"}:
        raise
    from server.domain_ports.registry import RegistryAvailability
    from server.domain_ports.registry_contracts import (
        AccountStatusOutcome,
        AccountStatusProjection,
        ActiveBindingOutcome,
        ActiveBindingProjection,
        AudienceProjection,
        AudienceProjectionOutcome,
        AudienceRef,
        BindingRef,
        BindingRevocationRequest,
        DeviceContextOutcome,
        DeviceContextProjection,
        DeviceRef,
        InventoryQualityOutcome,
        InventoryQualityProjection,
        DirectoryPersonProjection,
        DirectorySearchOutcome,
        DirectorySearchProjection,
        DirectorySearchText,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryHistoryEventProjection,
        RegistryInvalidProjection,
        RegistryNotFound,
        RegistryReadActor,
        RegistryUnavailable,
        RequesterRef,
        RequesterHistoryOutcome,
        RequesterHistoryProjection,
        RequesterProfileOutcome,
        RequesterProfileProjection,
        RequesterSnapshot,
        RequesterSnapshotOutcome,
    )


_SAFE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,119}$")
_MAX_RICH_PROJECTION_ITEMS = 100
_MAX_DIRECTORY_ITEMS = 50
logger = logging.getLogger(__name__)
_READ_FAILED = object()


def _safe_code(value: object) -> str | None:
    code = str(value or "").strip().lower()
    return code if _SAFE_CODE_RE.fullmatch(code) else None


class LocalRegistryAdapter:
    """Translate the current local Registry into neutral, redacted DTOs.

    A supplied SQLAlchemy session remains caller-owned and contributes only
    its bind; each port read opens an adapter-owned session so it cannot flush
    or abort the caller's unit of work. Without one, each operation opens a
    normal application session lazily; constructing the container therefore
    has no database side effect.

    Local command services do not yet honor caller-provided operation IDs.
    Command methods intentionally return ``registry_command_not_composed``
    rather than invoking non-idempotent local side effects.
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[Any]:
        if self._session is not None:
            yield self._session
            return
        from app.db import get_session

        async with get_session() as session:
            yield session

    @asynccontextmanager
    async def _isolated_read_scope(self) -> AsyncIterator[Any]:
        """Run port reads outside the caller-owned SQLAlchemy unit of work."""

        if isinstance(self._session, AsyncSession):
            bind = self._session.bind
            if isinstance(bind, AsyncConnection):
                bind = bind.engine
            if not isinstance(bind, AsyncEngine):
                raise RuntimeError("caller-owned registry session has no independent async engine")
            async with AsyncSession(bind=bind, expire_on_commit=False, autoflush=False) as session:
                yield session
            return

        async with self._session_scope() as session:
            yield session

    async def _read(self, operation: str, reader: Any) -> object:
        try:
            async with self._isolated_read_scope() as session:
                return await reader(session)
        except Exception:
            # The caller-owned session remains usable after the savepoint rolls
            # back. Do not include an exception, identifier or SQL statement in
            # this boundary diagnostic.
            logger.warning("registry_port_local_read_failed operation=%s", operation)
            return _READ_FAILED

    @staticmethod
    def _is_inactive_person(person: object | None) -> bool:
        return str(getattr(person, "status", "active") or "active").strip().lower() in {
            "archived",
            "disabled",
            "inactive",
            "merged",
        }

    @staticmethod
    def _actor_may_read_person(actor: RegistryReadActor, person: PersonRef) -> bool:
        if actor.role in {"admin", "support"}:
            return True
        return actor.requester is not None and actor.requester.external_id == person.external_id

    @staticmethod
    def _bounded_limit(limit: int, *, maximum: int) -> int | None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return None
        return min(limit, maximum)

    @staticmethod
    def _safe_label(value: object) -> str | None:
        text = str(value or "").strip()
        return text if 0 < len(text) <= 256 else None

    async def _person_labels(self, session: Any, person: object) -> tuple[str | None, str | None]:
        from app.repos.registry_repo import RegistryRepo

        repo = RegistryRepo(session)
        department = await repo.get_department(getattr(person, "department_id", None))
        location = await repo.get_location(getattr(person, "location_id", None))
        return (
            self._safe_label(getattr(department, "name", None)),
            self._safe_label(getattr(location, "display_name", None)),
        )

    @staticmethod
    def _requester_snapshot_from_person(person: object | None) -> RequesterSnapshot | None:
        if person is None:
            return None
        person_ref = str(getattr(person, "person_id", "") or "")
        display_name = str(getattr(person, "display_name", "") or "")
        status = _safe_code(getattr(person, "status", None))
        if not person_ref or status is None or status in {"archived", "disabled", "inactive", "merged"}:
            return None
        try:
            return RequesterSnapshot(
                person=PersonRef(external_id=person_ref),
                display_name=display_name,
            )
        except ValueError:
            return None

    @classmethod
    def _requester_profile_from_person(
        cls,
        *,
        person: object | None,
        department_label: str | None,
        location_label: str | None,
    ) -> RequesterProfileProjection | None:
        snapshot = cls._requester_snapshot_from_person(person)
        status = _safe_code(getattr(person, "status", None))
        if snapshot is None or status is None:
            return None
        try:
            return RequesterProfileProjection(
                requester=RequesterRef(external_id=snapshot.person.external_id),
                display_name=snapshot.display_name,
                department_label=department_label,
                location_label=location_label,
                status=status,
                source="local_authoritative",
            )
        except ValueError:
            return None

    @classmethod
    def _active_binding_projection(
        cls,
        *,
        binding: object | None,
        person: object | None,
    ) -> ActiveBindingProjection | None:
        snapshot = cls._requester_snapshot_from_person(person)
        if binding is None or snapshot is None:
            return None
        try:
            return ActiveBindingProjection(
                device=DeviceRef(external_id=str(getattr(binding, "device_id", "") or "")),
                binding=BindingRef(external_id=str(getattr(binding, "binding_id", "") or "")),
                requester=RequesterRef(external_id=snapshot.person.external_id),
                requester_snapshot=snapshot,
                relationship_type=str(getattr(binding, "relationship_type", "") or ""),
                source="local_authoritative",
            )
        except ValueError:
            return None

    async def availability(self) -> RegistryAvailability:
        return RegistryAvailability(status="available", code="registry_local")

    async def requester_snapshot(self, person: PersonRef) -> RequesterSnapshotOutcome:
        async def reader(session: Any) -> object | None:
            from app.repos.registry_repo import RegistryRepo

            return await RegistryRepo(session).get_person(person.external_id)

        row = await self._read("requester_snapshot", reader)
        if row is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if row is None or self._is_inactive_person(row):
            return RegistryNotFound(code="registry_requester_not_found")
        snapshot = self._requester_snapshot_from_person(row)
        if snapshot is None:
            return RegistryInvalidProjection()
        return snapshot

    async def active_binding(self, device: DeviceRef) -> ActiveBindingOutcome:
        async def reader(session: Any) -> object:
            from app.repos.registration_repo import RegistrationRepo
            from app.repos.registry_repo import RegistryRepo

            registration_repo = RegistrationRepo(session)
            binding = await registration_repo.get_active_primary_binding(device.external_id)
            if binding is None:
                active = await registration_repo.list_active_bindings_for_device(device.external_id)
                binding = next(
                    (
                        row
                        for row in active
                        if str(getattr(row, "relationship_type", "") or "")
                        in {"shared_user", "responsible"}
                    ),
                    None,
                )
            if binding is None:
                return RegistryNotFound(code="registry_active_binding_not_found")
            person = await RegistryRepo(session).get_person(getattr(binding, "person_id", None))
            return binding, person

        loaded = await self._read("active_binding", reader)
        if loaded is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if isinstance(loaded, RegistryNotFound):
            return loaded
        binding, person = loaded
        projection = self._active_binding_projection(binding=binding, person=person)
        if projection is None:
            return RegistryInvalidProjection()
        if projection.device.external_id != device.external_id:
            return RegistryInvalidProjection()
        return projection

    async def account_status(self, device: DeviceRef) -> AccountStatusOutcome:
        async def reader(session: Any) -> object:
            from registry.registration_service import RegistrationService

            return await RegistrationService(session).get_device_registration_status(device.external_id)

        payload = await self._read("account_status", reader)
        if payload is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if not isinstance(payload, dict):
            return RegistryInvalidProjection()

        active_binding = None
        binding_payload = payload.get("active_binding")
        person_payload = payload.get("active_person")
        if isinstance(binding_payload, dict) and isinstance(person_payload, dict):
            active_binding = self._active_binding_projection(
                binding=SimpleNamespace(**binding_payload),
                person=SimpleNamespace(**person_payload),
            )
            if active_binding is None:
                return RegistryInvalidProjection()
            if active_binding.device.external_id != device.external_id:
                return RegistryInvalidProjection()

        status = _safe_code(payload.get("status"))
        if status is None:
            return RegistryInvalidProjection()
        return AccountStatusProjection(
            device=device,
            status=status,
            active_binding=active_binding,
            requires_user_action=bool(payload.get("requires_user_action")),
            requires_admin_action=bool(payload.get("requires_admin_action")),
            code=_safe_code(payload.get("conflict_reason")),
            source="local_authoritative",
        )

    async def audience_projection(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
    ) -> AudienceProjectionOutcome:
        if not self._actor_may_read_person(actor, person):
            return RegistryUnavailable(code="registry_actor_forbidden")

        async def reader(session: Any) -> object:
            from app.db.models import RegistryPerson
            from registry.effective_identity_service import EffectiveIdentityService

            person_row = await session.get(RegistryPerson, person.external_id)
            if person_row is None or self._is_inactive_person(person_row):
                return RegistryNotFound(code="registry_requester_not_found")
            if self._requester_snapshot_from_person(person_row) is None:
                return RegistryInvalidProjection()
            return (
                await EffectiveIdentityService(session).resolve_person_audience(
                    person.external_id,
                    actor_id=actor.actor.external_id,
                    actor_role=actor.role,
                )
            ).to_dict()

        payload = await self._read("audience_projection", reader)
        if payload is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if isinstance(payload, (RegistryNotFound, RegistryInvalidProjection)):
            return payload
        if not isinstance(payload, dict):
            return RegistryInvalidProjection()

        raw_audiences = payload.get("audience_groups") or []
        raw_warnings = payload.get("warnings") or []
        if (
            not isinstance(raw_audiences, (list, tuple))
            or not isinstance(raw_warnings, (list, tuple))
            or len(raw_audiences) > _MAX_RICH_PROJECTION_ITEMS
            or len(raw_warnings) > _MAX_RICH_PROJECTION_ITEMS
        ):
            return RegistryInvalidProjection()

        audiences: list[AudienceRef] = []
        for item in raw_audiences:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("code") or item.get("audience_group_id") or "")
            if not external_id:
                continue
            try:
                audiences.append(AudienceRef(external_id=external_id))
            except ValueError:
                return RegistryInvalidProjection()
        warning_codes = tuple(
            code
            for item in raw_warnings
            if isinstance(item, dict) and (code := _safe_code(item.get("code"))) is not None
        )
        return AudienceProjection(
            requester=RequesterRef(external_id=person.external_id),
            audiences=tuple(audiences),
            warning_codes=warning_codes,
            source="local_authoritative",
        )

    async def requester_profile(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
    ) -> RequesterProfileOutcome:
        if not self._actor_may_read_person(actor, person):
            return RegistryUnavailable(code="registry_actor_forbidden")

        async def reader(session: Any) -> object:
            from app.repos.registry_repo import RegistryRepo

            row = await RegistryRepo(session).get_person(person.external_id)
            if row is None or self._is_inactive_person(row):
                return RegistryNotFound(code="registry_requester_not_found")
            labels = await self._person_labels(session, row)
            return row, labels

        loaded = await self._read("requester_profile", reader)
        if loaded is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if isinstance(loaded, RegistryNotFound):
            return loaded
        row, (department_label, location_label) = loaded
        projection = self._requester_profile_from_person(
            person=row,
            department_label=department_label,
            location_label=location_label,
        )
        if projection is None or projection.requester.external_id != person.external_id:
            return RegistryInvalidProjection()
        return projection

    async def search_people(
        self,
        query: DirectorySearchText,
        *,
        actor: RegistryReadActor,
        limit: int = 20,
    ) -> DirectorySearchOutcome:
        if actor.role not in {"admin", "support"}:
            return RegistryUnavailable(code="registry_actor_forbidden")
        clean_query = str(query or "").strip()
        bounded_limit = self._bounded_limit(limit, maximum=_MAX_DIRECTORY_ITEMS)
        if not clean_query or len(clean_query) > 120 or bounded_limit is None:
            return RegistryInvalidProjection(code="registry_projection_invalid")

        async def reader(session: Any) -> object:
            from app.repos.registry_repo import RegistryRepo

            return await RegistryRepo(session).search_people(
                query=clean_query,
                limit=bounded_limit,
            )

        rows = await self._read("search_people", reader)
        if rows is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if not isinstance(rows, list):
            return RegistryInvalidProjection()

        items: list[DirectoryPersonProjection] = []
        for row in rows:
            if self._is_inactive_person(row):
                continue
            display_name = self._safe_label(getattr(row, "display_name", None))
            status = _safe_code(getattr(row, "status", None))
            if status is None:
                return RegistryInvalidProjection()
            if display_name is None:
                continue
            try:
                items.append(
                    DirectoryPersonProjection(
                        requester=RequesterRef(external_id=str(getattr(row, "person_id", "") or "")),
                        display_name=display_name,
                        status=status,
                        source="local_authoritative",
                    )
                )
            except ValueError:
                return RegistryInvalidProjection()
            if len(items) >= bounded_limit:
                break
        return DirectorySearchProjection(items=tuple(items), source="local_authoritative")

    async def device_context(self, device: DeviceRef) -> DeviceContextOutcome:
        async def reader(session: Any) -> object:
            from app.repos.registry_repo import RegistryRepo

            repo = RegistryRepo(session)
            asset = await repo.get_asset_by_device_id(device.external_id)
            if asset is None:
                return RegistryNotFound(code="registry_device_not_found")
            assigned_person = await repo.get_person(getattr(asset, "assigned_person_id", None))
            department = await repo.get_department(getattr(asset, "department_id", None))
            location = await repo.get_location(getattr(asset, "location_id", None))
            return asset, assigned_person, department, location

        loaded = await self._read("device_context", reader)
        if loaded is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if isinstance(loaded, RegistryNotFound):
            return loaded
        asset, assigned_person, department, location = loaded
        if str(getattr(asset, "device_id", "") or "") != device.external_id:
            return RegistryInvalidProjection()
        snapshot = self._requester_snapshot_from_person(assigned_person)
        if getattr(asset, "assigned_person_id", None) and snapshot is None:
            return RegistryInvalidProjection()
        asset_type = _safe_code(getattr(asset, "asset_type", None))
        asset_status = _safe_code(getattr(asset, "status", None))
        if asset_type is None or asset_status is None:
            return RegistryInvalidProjection()
        try:
            return DeviceContextProjection(
                device=device,
                display_name=self._safe_label(getattr(asset, "name", None)) or "Unnamed device",
                asset_type=asset_type,
                asset_status=asset_status,
                requester=(RequesterRef(external_id=snapshot.person.external_id) if snapshot else None),
                requester_snapshot=snapshot,
                department_label=self._safe_label(getattr(department, "name", None)),
                location_label=self._safe_label(getattr(location, "display_name", None)),
                source="local_authoritative",
            )
        except ValueError:
            return RegistryInvalidProjection()

    async def inventory_quality(self) -> InventoryQualityOutcome:
        async def reader(session: Any) -> object:
            from sqlalchemy import and_, func, select

            from app.db.models import RegistryAsset

            return await session.scalar(
                select(func.count()).select_from(RegistryAsset).where(
                    and_(
                        RegistryAsset.asset_type == "pc",
                        RegistryAsset.status == "active",
                        RegistryAsset.location_id.is_(None),
                    )
                )
            )

        count = await self._read("inventory_quality", reader)
        if count is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if count is None:
            count = 0
        if isinstance(count, bool) or not isinstance(count, int):
            return RegistryInvalidProjection()
        try:
            return InventoryQualityProjection(
                active_pc_without_location_count=count,
                source="local_authoritative",
            )
        except ValueError:
            return RegistryInvalidProjection()

    async def requester_history(
        self,
        person: PersonRef,
        *,
        actor: RegistryReadActor,
        limit: int = 50,
    ) -> RequesterHistoryOutcome:
        if not self._actor_may_read_person(actor, person):
            return RegistryUnavailable(code="registry_actor_forbidden")
        bounded_limit = self._bounded_limit(limit, maximum=_MAX_RICH_PROJECTION_ITEMS)
        if bounded_limit is None:
            return RegistryInvalidProjection()

        async def reader(session: Any) -> object:
            from sqlalchemy import desc, select

            from app.db.models import DeviceAccountSession, DeviceUserBinding, RegistryPerson

            person_row = await session.get(RegistryPerson, person.external_id)
            if person_row is None or self._is_inactive_person(person_row):
                return RegistryNotFound(code="registry_requester_not_found")
            if self._requester_snapshot_from_person(person_row) is None:
                return RegistryInvalidProjection()
            bindings = (
                await session.execute(
                    select(DeviceUserBinding)
                    .where(DeviceUserBinding.person_id == person.external_id)
                    .order_by(desc(DeviceUserBinding.created_at))
                    .limit(bounded_limit)
                )
            ).scalars().all()
            sessions: list[object] = []
            if actor.role in {"admin", "support"}:
                sessions = (
                    await session.execute(
                        select(DeviceAccountSession)
                        .where(DeviceAccountSession.person_id == person.external_id)
                        .order_by(desc(DeviceAccountSession.created_at))
                        .limit(bounded_limit)
                    )
                ).scalars().all()
            return bindings, sessions

        loaded = await self._read("requester_history", reader)
        if loaded is _READ_FAILED:
            return RegistryUnavailable(code="registry_read_unavailable")
        if isinstance(loaded, RegistryNotFound):
            return loaded
        bindings, sessions = loaded
        items: list[RegistryHistoryEventProjection] = []
        try:
            for binding in bindings:
                occurred_at = getattr(binding, "created_at", None)
                if not isinstance(occurred_at, datetime):
                    return RegistryInvalidProjection()
                items.append(
                    RegistryHistoryEventProjection(
                        event_type="device_binding",
                        occurred_at=occurred_at,
                        device=DeviceRef(external_id=str(getattr(binding, "device_id", "") or "")),
                        relationship_type=_safe_code(getattr(binding, "relationship_type", None)),
                        status=_safe_code(getattr(binding, "status", None)),
                        source="local_authoritative",
                    )
                )
            for session in sessions:
                occurred_at = getattr(session, "created_at", None)
                if not isinstance(occurred_at, datetime):
                    return RegistryInvalidProjection()
                items.append(
                    RegistryHistoryEventProjection(
                        event_type="account_session",
                        occurred_at=occurred_at,
                        device=DeviceRef(external_id=str(getattr(session, "device_id", "") or "")),
                        status=_safe_code(getattr(session, "verification_status", None)),
                        source="local_authoritative",
                    )
                )
        except ValueError:
            return RegistryInvalidProjection()
        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return RequesterHistoryProjection(
            requester=RequesterRef(external_id=person.external_id),
            items=tuple(items[:bounded_limit]),
            source="local_authoritative",
        )

    @staticmethod
    def _command_not_composed(operation_id: str) -> RegistryCommandResult:
        return RegistryCommandResult(
            operation_id=operation_id,
            status="unavailable",
            code="registry_command_not_composed",
            idempotency_status="not_evaluated",
        )

    async def request_registration(self, request: RegistrationRequest) -> RegistryCommandResult:
        return self._command_not_composed(request.operation_id)

    async def approve_registration(
        self,
        request: RegistrationApprovalRequest,
    ) -> RegistryCommandResult:
        return self._command_not_composed(request.operation_id)

    async def revoke_binding(self, request: BindingRevocationRequest) -> RegistryCommandResult:
        return self._command_not_composed(request.operation_id)
