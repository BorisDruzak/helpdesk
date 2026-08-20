"""Typed, fail-closed contracts for the external Endpoint domain."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, TypeAlias, runtime_checkable
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, model_validator


# Opaque Endpoint references are transport values. Helpdesk must never parse,
# trim, case-fold, or otherwise derive semantics from them.
OpaqueEndpointRef: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=128),
]
SafeEndpointCode: TypeAlias = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]
SafeEndpointText: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=8192),
]
EndpointDisplayName: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=256),
]
EndpointProcessName: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128),
]
EndpointLogExcerpt: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=8192),
]

MAX_ENDPOINT_CAPABILITIES = 32
MAX_ENDPOINT_WARNING_CODES = 16
MAX_ENDPOINT_DIAGNOSTIC_PROCESSES = 64


class _ImmutableEndpointDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointDeviceRef(_ImmutableEndpointDTO):
    external_id: OpaqueEndpointRef


class EndpointOperationRef(_ImmutableEndpointDTO):
    external_id: OpaqueEndpointRef


class EndpointAvailability(_ImmutableEndpointDTO):
    status: Literal[
        "available",
        "unavailable",
        "invalid_projection",
        "unauthorized",
        "forbidden",
        "not_found",
        "conflict",
    ]
    code: SafeEndpointCode | None = None


class EndpointUnavailable(_ImmutableEndpointDTO):
    status: Literal["unavailable"] = "unavailable"
    code: SafeEndpointCode = "endpoint_unavailable"
    retryable: bool = True


class EndpointInvalidProjection(_ImmutableEndpointDTO):
    status: Literal["invalid_projection"] = "invalid_projection"
    code: SafeEndpointCode = "endpoint_invalid_projection"


class EndpointUnauthorized(_ImmutableEndpointDTO):
    status: Literal["unauthorized"] = "unauthorized"
    code: SafeEndpointCode = "endpoint_unauthorized"


class EndpointForbidden(_ImmutableEndpointDTO):
    status: Literal["forbidden"] = "forbidden"
    code: SafeEndpointCode = "endpoint_forbidden"


class EndpointNotFound(_ImmutableEndpointDTO):
    status: Literal["not_found"] = "not_found"
    code: SafeEndpointCode = "endpoint_not_found"


class EndpointConflict(_ImmutableEndpointDTO):
    status: Literal["conflict"] = "conflict"
    code: SafeEndpointCode = "endpoint_conflict"


EndpointAvailabilityOutcome: TypeAlias = EndpointAvailability
EndpointFailureOutcome: TypeAlias = (
    EndpointUnavailable
    | EndpointInvalidProjection
    | EndpointUnauthorized
    | EndpointForbidden
    | EndpointNotFound
    | EndpointConflict
)


class EndpointDeviceProjection(_ImmutableEndpointDTO):
    device: EndpointDeviceRef
    display_name: EndpointDisplayName
    retired: bool
    last_seen_at: AwareDatetime | None
    source: Literal["external_authoritative"] = "external_authoritative"


class EndpointCapabilityProjection(_ImmutableEndpointDTO):
    capability: Literal["context.diagnostic.collect"] = "context.diagnostic.collect"
    available: bool = True
    transport: Literal["gateway_wss"] = "gateway_wss"
    risk: Literal["read_only"] = "read_only"
    consent_required: Literal[False] = False
    parameter_schema_version: Literal["diagnostic_collection_parameters_v1"] = (
        "diagnostic_collection_parameters_v1"
    )
    last_observed_at: AwareDatetime | None = None


class EndpointCapabilitiesProjection(_ImmutableEndpointDTO):
    device: EndpointDeviceRef
    items: tuple[EndpointCapabilityProjection, ...] = ()
    source: Literal["external_authoritative"] = "external_authoritative"

    @model_validator(mode="after")
    def validate_bounded_items(self) -> "EndpointCapabilitiesProjection":
        if len(self.items) > MAX_ENDPOINT_CAPABILITIES:
            raise ValueError("endpoint capabilities exceed maximum item count")
        return self


class EndpointOperationCorrelation(_ImmutableEndpointDTO):
    schema_version: Literal["endpoint_operation_correlation_v1"] = "endpoint_operation_correlation_v1"
    source_system: Literal["helpdesk"] = "helpdesk"
    source_entity_type: Literal["ticket"] = "ticket"
    source_entity_id: OpaqueEndpointRef
    request_id: UUID


class EndpointDiagnosticParameters(_ImmutableEndpointDTO):
    reason: Literal["Диагностика по обращению"] = "Диагностика по обращению"


class EndpointOperationCreateRequest(_ImmutableEndpointDTO):
    schema_version: Literal["endpoint_operation_create_v1"] = "endpoint_operation_create_v1"
    capability: Literal["context.diagnostic.collect"] = "context.diagnostic.collect"
    parameters: EndpointDiagnosticParameters
    correlation: EndpointOperationCorrelation | None = None


class EndpointOperationProjection(_ImmutableEndpointDTO):
    operation: EndpointOperationRef
    device: EndpointDeviceRef
    capability: Literal["context.diagnostic.collect"] = "context.diagnostic.collect"
    status: Literal[
        "queued",
        "delivered",
        "acknowledged",
        "running",
        "succeeded",
        "failed",
        "canceled",
        "expired",
    ] = "queued"
    created_at: AwareDatetime
    deadline_at: AwareDatetime | None
    completed_at: AwareDatetime | None
    correlation: EndpointOperationCorrelation | None = None
    result_available: bool = False
    safe_result: "EndpointDiagnosticResultProjection | None" = None
    warning_codes: tuple[SafeEndpointCode, ...] = ()

    @model_validator(mode="after")
    def validate_operation_projection(self) -> "EndpointOperationProjection":
        if len(self.warning_codes) > MAX_ENDPOINT_WARNING_CODES:
            raise ValueError("endpoint operation warnings exceed maximum item count")
        if self.result_available != (self.safe_result is not None):
            raise ValueError("endpoint result_available must match safe result presence")
        if self.safe_result is not None and self.status not in {
            "succeeded",
            "failed",
            "canceled",
            "expired",
        }:
            raise ValueError("endpoint safe result requires terminal operation status")
        if self.deadline_at is not None and self.deadline_at < self.created_at:
            raise ValueError("endpoint operation deadline cannot precede creation")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("endpoint operation completion cannot precede creation")
        return self


class EndpointDiagnosticProcessProjection(_ImmutableEndpointDTO):
    name: EndpointProcessName
    state: Literal["running", "sleeping", "stopped", "unknown"]


class EndpointDiagnosticResultProjection(_ImmutableEndpointDTO):
    profile: Literal["diagnostic_v1"] = "diagnostic_v1"
    collected_at: AwareDatetime
    reason: Literal["Диагностика по обращению"] = "Диагностика по обращению"
    warnings: tuple[SafeEndpointCode, ...] = ()
    processes: tuple[EndpointDiagnosticProcessProjection, ...] = ()
    log_excerpt: EndpointLogExcerpt | None = None

    @model_validator(mode="after")
    def validate_bounded_result(self) -> "EndpointDiagnosticResultProjection":
        if len(self.warnings) > MAX_ENDPOINT_WARNING_CODES:
            raise ValueError("endpoint diagnostic warnings exceed maximum item count")
        if len(self.processes) > MAX_ENDPOINT_DIAGNOSTIC_PROCESSES:
            raise ValueError("endpoint diagnostic processes exceed maximum item count")
        return self


EndpointOperationProjection.model_rebuild()


EndpointDeviceOutcome: TypeAlias = EndpointDeviceProjection | EndpointFailureOutcome
EndpointCapabilitiesOutcome: TypeAlias = EndpointCapabilitiesProjection | EndpointFailureOutcome
EndpointOperationCreateOutcome: TypeAlias = EndpointOperationProjection | EndpointFailureOutcome
EndpointOperationReadOutcome: TypeAlias = EndpointOperationProjection | EndpointFailureOutcome


@runtime_checkable
class EndpointPort(Protocol):
    async def availability(self) -> EndpointAvailabilityOutcome: ...

    async def read_device(self, device: EndpointDeviceRef) -> EndpointDeviceOutcome: ...

    async def list_capabilities(
        self,
        device: EndpointDeviceRef,
    ) -> EndpointCapabilitiesOutcome: ...

    async def create_operation(
        self,
        device: EndpointDeviceRef,
        request: EndpointOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointOperationCreateOutcome: ...

    async def read_operation(
        self,
        operation: EndpointOperationRef,
    ) -> EndpointOperationReadOutcome: ...
