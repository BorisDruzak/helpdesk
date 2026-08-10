"""Local compatibility adapter for the RegistryPort boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
import re
from types import SimpleNamespace
from typing import Any, AsyncIterator

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
        DeviceRef,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryNotFound,
        RegistryUnavailable,
        RequesterRef,
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
        DeviceRef,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryNotFound,
        RegistryUnavailable,
        RequesterRef,
        RequesterSnapshot,
        RequesterSnapshotOutcome,
    )


_SAFE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,119}$")


def _safe_code(value: object) -> str | None:
    code = str(value or "").strip().lower()
    return code if _SAFE_CODE_RE.fullmatch(code) else None


class LocalRegistryAdapter:
    """Translate the current local Registry into neutral, redacted DTOs.

    A supplied session remains caller-owned. Without one, each operation opens
    a normal application session lazily; constructing the container therefore
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

    @staticmethod
    def _requester_snapshot_from_person(person: object | None) -> RequesterSnapshot | None:
        if person is None:
            return None
        person_ref = str(getattr(person, "person_id", "") or "")
        display_name = str(getattr(person, "display_name", "") or "")
        status = str(getattr(person, "status", "active") or "active").strip().lower()
        if not person_ref or status in {"archived", "disabled", "inactive", "merged"}:
            return None
        try:
            return RequesterSnapshot(
                person=PersonRef(external_id=person_ref),
                display_name=display_name,
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
        try:
            async with self._session_scope() as session:
                from app.repos.registry_repo import RegistryRepo

                row = await RegistryRepo(session).get_person(person.external_id)
        except Exception:
            return RegistryUnavailable(code="registry_read_unavailable")
        snapshot = self._requester_snapshot_from_person(row)
        if snapshot is None:
            return RegistryNotFound(code="registry_requester_not_found")
        return snapshot

    async def active_binding(self, device: DeviceRef) -> ActiveBindingOutcome:
        try:
            async with self._session_scope() as session:
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
        except Exception:
            return RegistryUnavailable(code="registry_read_unavailable")
        projection = self._active_binding_projection(binding=binding, person=person)
        if projection is None:
            return RegistryUnavailable(code="registry_projection_invalid")
        return projection

    async def account_status(self, device: DeviceRef) -> AccountStatusOutcome:
        try:
            async with self._session_scope() as session:
                from registry.registration_service import RegistrationService

                payload = await RegistrationService(session).get_device_registration_status(
                    device.external_id
                )
        except Exception:
            return RegistryUnavailable(code="registry_read_unavailable")

        active_binding = None
        binding_payload = payload.get("active_binding")
        person_payload = payload.get("active_person")
        if isinstance(binding_payload, dict) and isinstance(person_payload, dict):
            active_binding = self._active_binding_projection(
                binding=SimpleNamespace(**binding_payload),
                person=SimpleNamespace(**person_payload),
            )
            if active_binding is None:
                return RegistryUnavailable(code="registry_projection_invalid")

        status = _safe_code(payload.get("status"))
        if status is None:
            return RegistryUnavailable(code="registry_projection_invalid")
        return AccountStatusProjection(
            device=device,
            status=status,
            active_binding=active_binding,
            requires_user_action=bool(payload.get("requires_user_action")),
            requires_admin_action=bool(payload.get("requires_admin_action")),
            code=_safe_code(payload.get("conflict_reason")),
            source="local_authoritative",
        )

    async def audience_projection(self, person: PersonRef) -> AudienceProjectionOutcome:
        try:
            async with self._session_scope() as session:
                from app.db.models import RegistryPerson
                from registry.effective_identity_service import EffectiveIdentityService

                person_row = await session.get(RegistryPerson, person.external_id)
                if self._requester_snapshot_from_person(person_row) is None:
                    return RegistryNotFound(code="registry_requester_not_found")
                payload = (
                    await EffectiveIdentityService(session).resolve_person_audience(
                        person.external_id,
                        actor_id=None,
                        actor_role="user",
                    )
                ).to_dict()
        except Exception:
            return RegistryUnavailable(code="registry_read_unavailable")

        audiences: list[AudienceRef] = []
        for item in payload.get("audience_groups") or []:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("code") or item.get("audience_group_id") or "")
            if not external_id:
                continue
            try:
                audiences.append(AudienceRef(external_id=external_id))
            except ValueError:
                return RegistryUnavailable(code="registry_projection_invalid")
        warning_codes = tuple(
            code
            for item in payload.get("warnings") or []
            if isinstance(item, dict) and (code := _safe_code(item.get("code"))) is not None
        )
        return AudienceProjection(
            requester=RequesterRef(external_id=person.external_id),
            audiences=tuple(audiences),
            warning_codes=warning_codes,
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
