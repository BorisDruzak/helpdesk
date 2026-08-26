"""Local ticket facade for Endpoint Module Platform operations."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError
from typing_extensions import Annotated

from app.db.models import Ticket
from app.repos.endpoint_operation_links_repo import EndpointOperationLinkConflict, EndpointOperationLinksRepo
from app.repos.operations_repo import OperationsRepo
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceResolution


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", re.ASCII)
ModuleCallerIdempotencyKey = Annotated[str, StringConstraints(strict=True, min_length=8, max_length=128)]


class EndpointModuleOperationError(RuntimeError):
    """Safe module-facade failure."""


class EndpointModuleOperationConflict(EndpointModuleOperationError):
    """The caller key represents a different immutable module operation."""


class EndpointModuleOperationUnavailable(EndpointModuleOperationError):
    """The ticket has no validated Endpoint device mapping."""


class _ImmutableDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointModuleOperationRequest(_ImmutableDTO):
    ticket_id: str
    module_key: Annotated[str, StringConstraints(strict=True, min_length=3, max_length=128)]
    module_version: Annotated[str, StringConstraints(strict=True, min_length=5, max_length=64)]
    inputs: dict[str, str | int] = Field(min_length=1, max_length=8)
    idempotency_key: ModuleCallerIdempotencyKey


class EndpointModuleOperationResult(_ImmutableDTO):
    operation_id: str
    status: str = "queued"
    trace_id: str
    endpoint_operation_ref: None = None


class EndpointModuleOperationAccessService(Protocol):
    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None: ...


class EndpointModuleOperationDeviceResolver(Protocol):
    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution: ...


class EndpointModuleOperationStore(Protocol):
    async def get_by_operation_id(self, operation_id: str) -> dict[str, Any] | None: ...

    async def create_pending(self, **values: Any) -> dict[str, Any]: ...


class StoredTicketEndpointModuleDeviceResolver:
    """Read the already verified Helpdesk mapping without importing diagnostic ports."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution:
        async with self._session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            endpoint_device_ref = getattr(ticket, "endpoint_device_ref", None) if ticket is not None else None
        if not isinstance(endpoint_device_ref, str) or not endpoint_device_ref.strip():
            return EndpointDeviceReferenceResolution(
                status="unresolved", code="ENDPOINT_DEVICE_MAPPING_MISSING"
            )
        return EndpointDeviceReferenceResolution(status="resolved", device_ref=endpoint_device_ref)


def _validated_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ValueError("endpoint module idempotency key must be 8-128 ASCII safe characters")
    return value


def deterministic_endpoint_module_operation_id(
    *, actor_id: str, ticket_id: str, endpoint_device_ref: str, module_key: str, module_version: str,
    idempotency_key: str,
) -> str:
    return str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"helpdesk:{actor_id}:{ticket_id}:{endpoint_device_ref}:{module_key}:{module_version}:{idempotency_key}",
    ))


def remote_endpoint_module_idempotency_key(operation_id: str) -> str:
    return f"helpdesk-endpoint-module:{operation_id}"


class EndpointModuleOperationService:
    """Persists only the local request; a separate reconciler performs HTTPS work."""

    def __init__(
        self,
        *,
        access_service: EndpointModuleOperationAccessService,
        device_resolver: EndpointModuleOperationDeviceResolver,
        store: EndpointModuleOperationStore,
        now: Callable[[], datetime] | None = None,
        new_trace_id: Callable[[], str] | None = None,
    ) -> None:
        self._access_service = access_service
        self._device_resolver = device_resolver
        self._store = store
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_trace_id = new_trace_id or (lambda: str(uuid.uuid4()))

    async def create(self, *, actor: object, request: EndpointModuleOperationRequest) -> EndpointModuleOperationResult:
        key = _validated_idempotency_key(request.idempotency_key)
        await self._access_service.require_ticket_operation_access(actor=actor, ticket_id=request.ticket_id)
        resolution = await self._device_resolver.resolve_ticket(request.ticket_id)
        if resolution.status != "resolved" or not resolution.device_ref:
            raise EndpointModuleOperationUnavailable(getattr(resolution, "code", None) or "ENDPOINT_DEVICE_MAPPING_MISSING")
        actor_id = str(getattr(actor, "actor_id", ""))
        if not actor_id:
            raise EndpointModuleOperationUnavailable("ENDPOINT_ACTOR_MISSING")
        operation_id = deterministic_endpoint_module_operation_id(
            actor_id=actor_id, ticket_id=request.ticket_id, endpoint_device_ref=resolution.device_ref,
            module_key=request.module_key, module_version=request.module_version, idempotency_key=key,
        )
        existing = await self._store.get_by_operation_id(operation_id)
        if existing is not None:
            return self._return_existing(existing, operation_id=operation_id, request=request, endpoint_device_ref=resolution.device_ref)
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("endpoint module operation clock must return an aware datetime")
        created = await self._store.create_pending(
            operation_id=operation_id, ticket_id=request.ticket_id, actor_id=actor_id,
            actor_role=str(getattr(actor, "actor_role", "")), endpoint_device_ref=resolution.device_ref,
            module_key=request.module_key, module_version=request.module_version, inputs=dict(request.inputs),
            idempotency_key=remote_endpoint_module_idempotency_key(operation_id),
            caller_idempotency_key=key, trace_id=self._new_trace_id(), created_at=now,
        )
        return self._return_existing(created, operation_id=operation_id, request=request, endpoint_device_ref=resolution.device_ref)

    @staticmethod
    def _return_existing(existing: dict[str, Any], *, operation_id: str, request: EndpointModuleOperationRequest, endpoint_device_ref: str) -> EndpointModuleOperationResult:
        if (
            existing.get("operation_id") != operation_id or existing.get("ticket_id") != request.ticket_id
            or existing.get("endpoint_device_ref") != endpoint_device_ref or existing.get("module_key") != request.module_key
            or existing.get("module_version") != request.module_version or existing.get("inputs") != dict(request.inputs)
        ):
            raise EndpointModuleOperationConflict("endpoint module idempotency key conflicts with immutable identity")
        return EndpointModuleOperationResult(operation_id=operation_id, status=str(existing.get("status") or "queued"), trace_id=str(existing.get("trace_id") or ""))


class SqlAlchemyEndpointModuleOperationStore:
    """Short-transaction store; remote Endpoint calls belong only to the reconciler."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def get_by_operation_id(self, operation_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            link = await EndpointOperationLinksRepo(session).get_by_operation_id(operation_id)
            if link is None:
                return None
            operation = await OperationsRepo(session).get_by_operation_id(operation_id)
            if operation is None:
                raise EndpointModuleOperationConflict("module link has no local operation")
            return {
                "operation_id": operation.operation_id, "ticket_id": str(operation.ticket_id),
                "endpoint_device_ref": link.endpoint_device_ref, "module_key": link.module_key,
                "module_version": link.module_version, "inputs": dict(link.module_inputs_snapshot_json or {}),
                "status": operation.status, "trace_id": operation.trace_id,
            }

    async def create_pending(self, **values: Any) -> dict[str, Any]:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    ticket = await session.get(Ticket, values["ticket_id"], with_for_update=True)
                    if ticket is None:
                        raise EndpointModuleOperationUnavailable("ENDPOINT_TICKET_NOT_FOUND")
                    operation = await OperationsRepo(session).create_operation(
                        operation_id=values["operation_id"], device_id=getattr(ticket, "device_id", None),
                        ticket_id=values["ticket_id"], kind="endpoint_module_operation",
                        tool_name="endpoint.module.operation", actor_role=values["actor_role"],
                        trace_id=values["trace_id"], status="queued", phase="endpoint_module_create_pending",
                    )
                    await EndpointOperationLinksRepo(session).create_module_pending(
                        operation_id=operation.operation_id, endpoint_device_ref=values["endpoint_device_ref"],
                        module_key=values["module_key"], module_version=values["module_version"],
                        inputs=values["inputs"], create_idempotency_key=values["idempotency_key"],
                        caller_actor_id=values["actor_id"], caller_idempotency_key=values["caller_idempotency_key"],
                        next_attempt_at=values["created_at"],
                    )
                    return {
                        "operation_id": operation.operation_id, "ticket_id": str(operation.ticket_id),
                        "endpoint_device_ref": values["endpoint_device_ref"], "module_key": values["module_key"],
                        "module_version": values["module_version"], "inputs": dict(values["inputs"]),
                        "status": operation.status, "trace_id": operation.trace_id,
                    }
        except EndpointOperationLinkConflict as exc:
            raise EndpointModuleOperationConflict(str(exc)) from exc
        except IntegrityError as exc:
            existing = await self.get_by_operation_id(values["operation_id"])
            if existing is not None:
                return existing
            raise EndpointModuleOperationConflict("module operation persistence conflict") from exc
