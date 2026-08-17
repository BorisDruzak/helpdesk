"""Local, ticket-scoped facade for Endpoint diagnostic collection.

This module deliberately has no HTTP, WebSocket, outbox or tool-runtime
dependency.  The provider/router composes it only after its normal verified
actor and ticket checks have selected Endpoint execution.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, StringConstraints
from typing_extensions import Annotated

from app.db.models import DiagnosticSession, DiagnosticStep
from app.repos.endpoint_operation_links_repo import EndpointOperationLinkConflict, EndpointOperationLinksRepo
from app.repos.operations_repo import OperationsRepo
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceResolution


ENDPOINT_DIAGNOSTIC_CAPABILITY = "context.diagnostic.collect"
ENDPOINT_DIAGNOSTIC_REASON = "Диагностика по обращению"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$", re.ASCII)
EndpointCallerIdempotencyKey = Annotated[
    str,
    StringConstraints(strict=True, min_length=8, max_length=128),
]


class EndpointDiagnosticOperationError(RuntimeError):
    """Safe local-facade failure."""


class EndpointDiagnosticOperationConflict(EndpointDiagnosticOperationError):
    """A caller key already represents a different immutable operation."""


class EndpointDiagnosticOperationUnavailable(EndpointDiagnosticOperationError):
    """A ticket has no validated Endpoint device mapping."""


class _ImmutableDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointDiagnosticOperationRequest(_ImmutableDTO):
    ticket_id: str
    idempotency_key: EndpointCallerIdempotencyKey


class EndpointDiagnosticOperationResult(_ImmutableDTO):
    operation_id: str
    status: str = "queued"
    trace_id: str
    endpoint_operation_ref: None = None


@dataclass(frozen=True)
class EndpointDiagnosticOperationStored:
    operation_id: str
    ticket_id: str
    endpoint_device_ref: str
    status: str
    trace_id: str


class EndpointDiagnosticAccessService(Protocol):
    """Narrow verified actor/ticket authorization boundary.

    Concrete web/API code must adapt existing authenticated ticket access here;
    this facade intentionally does not infer roles or access from client data.
    """

    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None: ...


class EndpointDiagnosticDeviceResolver(Protocol):
    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution: ...


class EndpointDiagnosticOperationStore(Protocol):
    async def get_by_idempotency_key(self, key: str) -> EndpointDiagnosticOperationStored | dict[str, Any] | None: ...

    async def create_pending(self, **values: Any) -> EndpointDiagnosticOperationStored | dict[str, Any]: ...


def validate_endpoint_operation_idempotency_key(value: str) -> str:
    """Accept only an already-normalized, client supplied opaque caller key."""

    if not isinstance(value, str) or not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ValueError("endpoint diagnostic idempotency key must be 8-128 ASCII safe characters")
    return value


def deterministic_endpoint_operation_id(
    *, ticket_id: str, endpoint_device_ref: str, idempotency_key: str
) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"helpdesk:{ticket_id}:{endpoint_device_ref}:{ENDPOINT_DIAGNOSTIC_CAPABILITY}:{idempotency_key}",
        )
    )


class EndpointDiagnosticOperationService:
    """Creates only a local durable operation; remote work is reconciled later."""

    def __init__(
        self,
        *,
        access_service: EndpointDiagnosticAccessService,
        device_resolver: EndpointDiagnosticDeviceResolver,
        store: EndpointDiagnosticOperationStore,
        now: Callable[[], datetime] | None = None,
        new_trace_id: Callable[[], str] | None = None,
    ) -> None:
        self._access_service = access_service
        self._device_resolver = device_resolver
        self._store = store
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_trace_id = new_trace_id or (lambda: str(uuid.uuid4()))

    async def create(
        self, *, actor: object, request: EndpointDiagnosticOperationRequest
    ) -> EndpointDiagnosticOperationResult:
        key = validate_endpoint_operation_idempotency_key(request.idempotency_key)
        await self._access_service.require_ticket_operation_access(actor=actor, ticket_id=request.ticket_id)
        resolution = await self._device_resolver.resolve_ticket(request.ticket_id)
        if resolution.status != "resolved" or not resolution.device_ref:
            raise EndpointDiagnosticOperationUnavailable(
                getattr(resolution, "code", None) or "ENDPOINT_DEVICE_MAPPING_MISSING"
            )
        operation_id = deterministic_endpoint_operation_id(
            ticket_id=request.ticket_id,
            endpoint_device_ref=resolution.device_ref,
            idempotency_key=key,
        )
        existing = await self._store.get_by_idempotency_key(key)
        if existing is not None:
            return self._return_existing(
                existing,
                operation_id=operation_id,
                ticket_id=request.ticket_id,
                endpoint_device_ref=resolution.device_ref,
            )

        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("endpoint operation clock must return an aware datetime")
        created = await self._store.create_pending(
            operation_id=operation_id,
            ticket_id=request.ticket_id,
            # Kept only for Operation compatibility until the legacy projection is retired.
            legacy_device_id=resolution.device_ref,
            actor_id=str(getattr(actor, "actor_id", "")),
            actor_role=str(getattr(actor, "actor_role", "")),
            endpoint_device_ref=resolution.device_ref,
            idempotency_key=key,
            trace_id=self._new_trace_id(),
            created_at=now,
        )
        return self._return_existing(
            created,
            operation_id=operation_id,
            ticket_id=request.ticket_id,
            endpoint_device_ref=resolution.device_ref,
        )

    @staticmethod
    def _return_existing(
        existing: EndpointDiagnosticOperationStored | dict[str, Any],
        *,
        operation_id: str,
        ticket_id: str,
        endpoint_device_ref: str,
    ) -> EndpointDiagnosticOperationResult:
        def field(name: str) -> Any:
            return existing.get(name) if isinstance(existing, dict) else getattr(existing, name)

        if (
            field("operation_id") != operation_id
            or field("ticket_id") != ticket_id
            or field("endpoint_device_ref") != endpoint_device_ref
        ):
            raise EndpointDiagnosticOperationConflict(
                "endpoint diagnostic idempotency key conflicts with immutable identity"
            )
        return EndpointDiagnosticOperationResult(
            operation_id=operation_id,
            status=str(field("status") or "queued"),
            trace_id=str(field("trace_id") or ""),
        )


class SqlAlchemyEndpointDiagnosticOperationStore:
    """Short-transaction persistence adapter for the local facade.

    It contains no endpoint-port calls.  In particular, the reconciler always
    invokes remote HTTP after this store has committed its transaction.
    """

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def get_by_idempotency_key(self, key: str) -> EndpointDiagnosticOperationStored | None:
        async with self._session_factory() as session:
            link = await EndpointOperationLinksRepo(session).get_by_idempotency_key(key)
            if link is None:
                return None
            operation = await OperationsRepo(session).get_by_operation_id(link.operation_id)
            if operation is None:
                raise EndpointDiagnosticOperationConflict("endpoint link has no local operation")
            return EndpointDiagnosticOperationStored(
                operation_id=operation.operation_id,
                ticket_id=str(operation.ticket_id),
                endpoint_device_ref=link.endpoint_device_ref,
                status=operation.status,
                trace_id=operation.trace_id,
            )

    async def create_pending(self, **values: Any) -> EndpointDiagnosticOperationStored:
        async with self._session_factory() as session:
            async with session.begin():
                operations = OperationsRepo(session)
                operation = await operations.create_operation(
                    operation_id=values["operation_id"],
                    device_id=values["legacy_device_id"],
                    ticket_id=values["ticket_id"],
                    kind="endpoint_operation",
                    tool_name=ENDPOINT_DIAGNOSTIC_CAPABILITY,
                    actor_role=values["actor_role"],
                    trace_id=values["trace_id"],
                    status="queued",
                    phase="endpoint_create_pending",
                )
                diagnostic_session = DiagnosticSession(
                    id=str(uuid.uuid4()),
                    ticket_id=values["ticket_id"],
                    status="draft",
                    trigger_source="endpoint_platform",
                    started_by_user_id=values["actor_id"] or None,
                )
                session.add(diagnostic_session)
                await session.flush()
                diagnostic_step = DiagnosticStep(
                    id=str(uuid.uuid4()),
                    session_id=diagnostic_session.id,
                    ticket_id=values["ticket_id"],
                    step_type="endpoint_operation",
                    provider_id="endpoint_platform",
                    capability_id=ENDPOINT_DIAGNOSTIC_CAPABILITY,
                    operation_id=operation.operation_id,
                    status="pending",
                )
                session.add(diagnostic_step)
                await session.flush()
                try:
                    await EndpointOperationLinksRepo(session).create_pending(
                        operation_id=operation.operation_id,
                        endpoint_device_ref=values["endpoint_device_ref"],
                        create_idempotency_key=values["idempotency_key"],
                        next_attempt_at=values["created_at"],
                        diagnostic_session_id=diagnostic_session.id,
                        diagnostic_step_id=diagnostic_step.id,
                    )
                except EndpointOperationLinkConflict as exc:
                    raise EndpointDiagnosticOperationConflict(str(exc)) from exc
                return EndpointDiagnosticOperationStored(
                    operation_id=operation.operation_id,
                    ticket_id=str(operation.ticket_id),
                    endpoint_device_ref=values["endpoint_device_ref"],
                    status=operation.status,
                    trace_id=operation.trace_id,
                )
