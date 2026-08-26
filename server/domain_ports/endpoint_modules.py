"""Typed, fail-closed contracts for Endpoint Module Platform v1."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Protocol, TypeAlias, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .endpoint import OpaqueEndpointRef, SafeEndpointCode


ModuleKey: TypeAlias = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$",
    ),
]
ModuleVersion: TypeAlias = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=5,
        max_length=64,
        pattern=r"^\d+\.\d+\.\d+$",
    ),
]
ModuleDisplayName: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128),
]
ModuleInputName: TypeAlias = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]{0,63}$",
    ),
]
ModuleSafeScalar: TypeAlias = Annotated[
    str | int | float | bool,
    Field(union_mode="left_to_right"),
]

MAX_MODULE_OPERATION_STEPS = 8
MAX_MODULE_SAFE_VALUES = 8


class _ImmutableEndpointModuleDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointModuleVersionState(str, Enum):
    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    VALIDATED = "validated"
    LAB_ACCEPTED = "lab_accepted"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


class EndpointModuleRef(_ImmutableEndpointModuleDTO):
    module_key: ModuleKey


class EndpointModuleVersionRef(_ImmutableEndpointModuleDTO):
    module: EndpointModuleRef
    version: ModuleVersion


class EndpointModuleAvailability(_ImmutableEndpointModuleDTO):
    status: Literal["available", "unavailable"]
    code: SafeEndpointCode | None = None


class EndpointModuleUnavailable(_ImmutableEndpointModuleDTO):
    status: Literal["unavailable"] = "unavailable"
    code: SafeEndpointCode = "endpoint_module_unavailable"
    retryable: bool = True


class EndpointModuleInvalidProjection(_ImmutableEndpointModuleDTO):
    status: Literal["invalid_projection"] = "invalid_projection"
    code: SafeEndpointCode = "endpoint_module_invalid_projection"


class EndpointModuleNotFound(_ImmutableEndpointModuleDTO):
    status: Literal["not_found"] = "not_found"
    code: SafeEndpointCode = "endpoint_module_not_found"


EndpointModuleFailureOutcome: TypeAlias = (
    EndpointModuleUnavailable | EndpointModuleInvalidProjection | EndpointModuleNotFound
)


class EndpointModuleDefinitionProjection(_ImmutableEndpointModuleDTO):
    module: EndpointModuleRef
    display_name: ModuleDisplayName
    latest_version: EndpointModuleVersionRef
    latest_state: EndpointModuleVersionState
    source: Literal["external_authoritative"] = "external_authoritative"


class EndpointModuleCatalogProjection(_ImmutableEndpointModuleDTO):
    module: EndpointModuleRef
    display_name: ModuleDisplayName
    source: Literal["external_authoritative"] = "external_authoritative"


class EndpointModuleVersionProjection(_ImmutableEndpointModuleDTO):
    version: EndpointModuleVersionRef
    display_name: ModuleDisplayName
    state: EndpointModuleVersionState
    source: Literal["external_authoritative"] = "external_authoritative"


class EndpointModuleOperationRef(_ImmutableEndpointModuleDTO):
    external_id: OpaqueEndpointRef


class EndpointModuleOperationCreateRequest(_ImmutableEndpointModuleDTO):
    schema_version: Literal["endpoint_module_operation_create_v1"] = (
        "endpoint_module_operation_create_v1"
    )
    module_version: EndpointModuleVersionRef
    device_external_id: OpaqueEndpointRef
    inputs: dict[ModuleInputName, ModuleSafeScalar] = Field(default_factory=dict, max_length=8)


class EndpointModuleOperationStepProjection(_ImmutableEndpointModuleDTO):
    sequence: int = Field(ge=0, le=7)
    capability: Literal["dns.resolve", "network.ping", "tcp.connect"]
    status: Literal["succeeded", "failed", "canceled", "expired"]
    error_code: SafeEndpointCode | None
    safe_values: dict[SafeEndpointCode, ModuleSafeScalar] = Field(default_factory=dict, max_length=8)


class EndpointModuleOperationProjection(_ImmutableEndpointModuleDTO):
    operation: EndpointModuleOperationRef
    module_version: EndpointModuleVersionRef
    device_external_id: OpaqueEndpointRef
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
    result_available: bool = False
    safe_result: tuple[EndpointModuleOperationStepProjection, ...] = ()
    warning_codes: tuple[SafeEndpointCode, ...] = ()

    @model_validator(mode="after")
    def validate_safe_result(self) -> "EndpointModuleOperationProjection":
        if len(self.safe_result) > MAX_MODULE_OPERATION_STEPS:
            raise ValueError("module operation steps exceed maximum item count")
        if len(self.warning_codes) > MAX_MODULE_SAFE_VALUES:
            raise ValueError("module operation warnings exceed maximum item count")
        if self.result_available != bool(self.safe_result):
            raise ValueError("module result_available must match safe result presence")
        if self.safe_result and self.status not in {"succeeded", "failed", "canceled", "expired"}:
            raise ValueError("module safe result requires terminal operation status")
        if self.deadline_at is not None and self.deadline_at < self.created_at:
            raise ValueError("module operation deadline cannot precede creation")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("module operation completion cannot precede creation")
        return self


EndpointModuleListOutcome: TypeAlias = tuple[EndpointModuleCatalogProjection, ...] | EndpointModuleFailureOutcome
EndpointModuleReadOutcome: TypeAlias = EndpointModuleDefinitionProjection | EndpointModuleFailureOutcome
EndpointModuleVersionReadOutcome: TypeAlias = EndpointModuleVersionProjection | EndpointModuleFailureOutcome
EndpointModuleOperationCreateOutcome: TypeAlias = EndpointModuleOperationProjection | EndpointModuleFailureOutcome
EndpointModuleOperationReadOutcome: TypeAlias = EndpointModuleOperationProjection | EndpointModuleFailureOutcome


@runtime_checkable
class EndpointModulePort(Protocol):
    async def availability(self) -> EndpointModuleAvailability: ...

    async def list_modules(self) -> EndpointModuleListOutcome: ...

    async def read_module(self, module: EndpointModuleRef) -> EndpointModuleReadOutcome: ...

    async def read_module_version(
        self,
        version: EndpointModuleVersionRef,
    ) -> EndpointModuleVersionReadOutcome: ...

    async def create_operation(
        self,
        request: EndpointModuleOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointModuleOperationCreateOutcome: ...

    async def read_operation(
        self,
        operation: EndpointModuleOperationRef,
    ) -> EndpointModuleOperationReadOutcome: ...
