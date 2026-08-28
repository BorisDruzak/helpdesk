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
EndpointModuleCapability: TypeAlias = Literal[
    "dns.resolve",
    "network.ping",
    "tcp.connect",
    "route.get",
    "adapter.list",
    "system.service_status",
]
EndpointModuleCapabilityPlatform: TypeAlias = Literal["linux_amd64", "windows_amd64"]
EndpointModuleCapabilityFeatureFlag: TypeAlias = Literal[
    "endpoint_network_primitives_enabled",
    "endpoint_read_only_primitives_enabled",
]
EndpointModuleCapabilityPolicy: TypeAlias = Literal["network_target_policy", "none"]
EndpointModuleCapabilityParameterType: TypeAlias = Literal["string", "integer", "enum"]
EndpointModuleCapabilityParameterSource: TypeAlias = Literal["input", "literal"]

_RELEASED_MODULE_CAPABILITY_SIGNATURES = {
    "dns.resolve": (
        "dns_resolve_parameters_v1", "dns_resolve_result_v1", ("linux_amd64", "windows_amd64"), "3.2.27",
        "safe_read", False, "endpoint_network_primitives_enabled", "network_target_policy",
        (("target", "string", True, ("input", "literal"), None, None, None, None, False), ("family", "enum", True, ("input", "literal"), ("any", "ipv4", "ipv6"), None, None, None, False)),
    ),
    "network.ping": (
        "network_ping_parameters_v1", "network_ping_result_v1", ("linux_amd64", "windows_amd64"), "3.2.27",
        "safe_read", False, "endpoint_network_primitives_enabled", "network_target_policy",
        (("target", "string", True, ("input", "literal"), None, None, None, None, False), ("count", "integer", True, ("input", "literal"), None, 1, 5, None, False), ("timeout_ms", "integer", True, ("input", "literal"), None, 100, 5000, None, False)),
    ),
    "tcp.connect": (
        "tcp_connect_parameters_v1", "tcp_connect_result_v1", ("linux_amd64", "windows_amd64"), "3.2.27",
        "safe_read", False, "endpoint_network_primitives_enabled", "network_target_policy",
        (("target", "string", True, ("input", "literal"), None, None, None, None, False), ("port", "integer", True, ("input", "literal"), None, 1, 65535, None, False), ("timeout_ms", "integer", True, ("input", "literal"), None, 100, 10000, None, False)),
    ),
    "route.get": (
        "route_get_parameters_v1", "route_get_result_v1", ("linux_amd64", "windows_amd64"), "3.2.29",
        "safe_read", False, "endpoint_read_only_primitives_enabled", "network_target_policy",
        (("target", "string", True, ("input", "literal"), None, None, None, None, False), ("port", "integer", True, ("input", "literal"), None, 1, 65535, None, False), ("family", "enum", True, ("input", "literal"), ("any", "ipv4", "ipv6"), None, None, None, False), ("timeout_ms", "integer", True, ("input", "literal"), None, 100, 5000, None, False)),
    ),
    "adapter.list": (
        "adapter_list_parameters_v1", "adapter_list_result_v1", ("linux_amd64", "windows_amd64"), "3.2.29",
        "safe_read", False, "endpoint_read_only_primitives_enabled", "none", (),
    ),
    "system.service_status": (
        "service_status_parameters_v1", "service_status_result_v1", ("linux_amd64", "windows_amd64"), "3.2.29",
        "safe_read", False, "endpoint_read_only_primitives_enabled", "none",
        (("service_key", "enum", True, ("literal",), ("endpoint_agent", "endpoint_agent_updater"), None, None, None, False),),
    ),
}

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


class EndpointModuleCapabilityParameterDescriptor(_ImmutableEndpointModuleDTO):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: ModuleInputName
    value_type: EndpointModuleCapabilityParameterType
    required: bool
    allowed_sources: tuple[EndpointModuleCapabilityParameterSource, ...] = Field(
        min_length=1,
        max_length=2,
    )
    enum_values: tuple[str, ...] | None = Field(max_length=8)
    minimum: int | None
    maximum: int | None
    default_literal: str | int | None
    secret: Literal[False]

    @model_validator(mode="after")
    def validate_descriptor_shape(self) -> "EndpointModuleCapabilityParameterDescriptor":
        if len(set(self.allowed_sources)) != len(self.allowed_sources):
            raise ValueError("parameter allowed_sources must not contain duplicates")
        if self.value_type == "enum":
            if not self.enum_values or len(set(self.enum_values)) != len(self.enum_values):
                raise ValueError("enum parameter must declare unique enum_values")
            if self.minimum is not None or self.maximum is not None:
                raise ValueError("enum parameter must not declare numeric bounds")
        elif self.enum_values is not None:
            raise ValueError("only enum parameters may declare enum_values")
        if self.value_type != "integer" and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("only integer parameters may declare numeric bounds")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum must not exceed maximum")
        if self.default_literal is not None:
            expected = int if self.value_type == "integer" else str
            if type(self.default_literal) is not expected:
                raise ValueError("parameter default_literal type is invalid")
            if self.value_type == "enum" and self.default_literal not in self.enum_values:
                raise ValueError("enum default_literal must be declared")
        return self


class EndpointModuleCapabilityDescriptor(_ImmutableEndpointModuleDTO):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability: EndpointModuleCapability
    parameter_schema_version: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128),
    ]
    result_schema_version: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128),
    ]
    platforms: tuple[EndpointModuleCapabilityPlatform, ...] = Field(min_length=1, max_length=2)
    minimum_agent_version: ModuleVersion
    risk: Literal["safe_read"]
    consent_required: Literal[False]
    feature_flag: EndpointModuleCapabilityFeatureFlag
    policy: EndpointModuleCapabilityPolicy
    parameters: tuple[EndpointModuleCapabilityParameterDescriptor, ...] = Field(max_length=4)

    @model_validator(mode="after")
    def validate_descriptor_names(self) -> "EndpointModuleCapabilityDescriptor":
        if len(set(self.platforms)) != len(self.platforms):
            raise ValueError("capability platforms must be unique")
        if len({parameter.name for parameter in self.parameters}) != len(self.parameters):
            raise ValueError("capability parameter names must be unique")
        signature = (
            self.parameter_schema_version,
            self.result_schema_version,
            self.platforms,
            self.minimum_agent_version,
            self.risk,
            self.consent_required,
            self.feature_flag,
            self.policy,
            tuple(
                (
                    parameter.name,
                    parameter.value_type,
                    parameter.required,
                    parameter.allowed_sources,
                    parameter.enum_values,
                    parameter.minimum,
                    parameter.maximum,
                    parameter.default_literal,
                    parameter.secret,
                )
                for parameter in self.parameters
            ),
        )
        if signature != _RELEASED_MODULE_CAPABILITY_SIGNATURES[self.capability]:
            raise ValueError("capability metadata must match the released Endpoint catalog")
        return self


class EndpointModuleCapabilityCatalog(_ImmutableEndpointModuleDTO):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["endpoint_module_capability_catalog_v1"]
    items: tuple[EndpointModuleCapabilityDescriptor, ...] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_fixed_capabilities(self) -> "EndpointModuleCapabilityCatalog":
        expected = {
            "dns.resolve",
            "network.ping",
            "tcp.connect",
            "route.get",
            "adapter.list",
            "system.service_status",
        }
        if {item.capability for item in self.items} != expected:
            raise ValueError("catalog must contain each fixed module capability exactly once")
        return self


class EndpointModuleVersionProjection(_ImmutableEndpointModuleDTO):
    version: EndpointModuleVersionRef
    display_name: ModuleDisplayName
    state: EndpointModuleVersionState
    source: Literal["external_authoritative"] = "external_authoritative"


class EndpointModuleRecipeInput(_ImmutableEndpointModuleDTO):
    name: ModuleInputName
    value_type: Literal["string", "integer"]


class EndpointModuleInputBinding(_ImmutableEndpointModuleDTO):
    kind: Literal["input"]
    name: ModuleInputName


class EndpointModuleLiteralBinding(_ImmutableEndpointModuleDTO):
    kind: Literal["literal"]
    value: str | int


EndpointModuleParameterBinding: TypeAlias = Annotated[
    EndpointModuleInputBinding | EndpointModuleLiteralBinding,
    Field(discriminator="kind"),
]


class EndpointModuleRecipeStep(_ImmutableEndpointModuleDTO):
    step_id: ModuleInputName
    capability: Literal["dns.resolve", "network.ping", "tcp.connect"]
    parameters: dict[ModuleInputName, EndpointModuleParameterBinding] = Field(min_length=1, max_length=3)


class EndpointModuleRecipe(_ImmutableEndpointModuleDTO):
    schema_version: Literal["endpoint_recipe_module_v1"] = "endpoint_recipe_module_v1"
    module_key: ModuleKey
    supported_platforms: tuple[Literal["linux_amd64", "windows_amd64"], ...] = Field(min_length=1, max_length=2)
    inputs: tuple[EndpointModuleRecipeInput, ...] = Field(default=(), max_length=8)
    steps: tuple[EndpointModuleRecipeStep, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_declarative_names(self) -> "EndpointModuleRecipe":
        if len(set(self.supported_platforms)) != len(self.supported_platforms):
            raise ValueError("recipe platforms must be unique")
        if len({item.name for item in self.inputs}) != len(self.inputs):
            raise ValueError("recipe input names must be unique")
        if len({item.step_id for item in self.steps}) != len(self.steps):
            raise ValueError("recipe step names must be unique")
        return self


class EndpointModuleVersionCreateRequest(_ImmutableEndpointModuleDTO):
    schema_version: Literal["module_version_create_v1"] = "module_version_create_v1"
    display_name: ModuleDisplayName
    version: ModuleVersion
    recipe: EndpointModuleRecipe


class EndpointModuleValidationProjection(_ImmutableEndpointModuleDTO):
    module_version: EndpointModuleVersionRef
    status: Literal["succeeded", "failed"]
    error_codes: tuple[SafeEndpointCode, ...] = Field(max_length=32)
    warning_codes: tuple[SafeEndpointCode, ...] = Field(max_length=32)
    completed_at: AwareDatetime


class EndpointModuleVersionStateProjection(_ImmutableEndpointModuleDTO):
    version: EndpointModuleVersionRef
    state: EndpointModuleVersionState


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
    capability: EndpointModuleCapability
    status: Literal["succeeded", "failed", "canceled", "expired"]
    error_code: SafeEndpointCode | None
    safe_values: dict[SafeEndpointCode, ModuleSafeScalar] = Field(default_factory=dict, max_length=8)
    safe_result: dict[str, object] | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def validate_safe_result_identity(self) -> "EndpointModuleOperationStepProjection":
        if self.safe_result is None:
            return self
        schema_version = self.safe_result.get("schema_version")
        if not isinstance(schema_version, str) or not schema_version:
            raise ValueError("module step safe result requires a schema discriminator")
        return self


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
EndpointModuleCapabilityCatalogOutcome: TypeAlias = EndpointModuleCapabilityCatalog | EndpointModuleFailureOutcome
EndpointModuleReadOutcome: TypeAlias = EndpointModuleDefinitionProjection | EndpointModuleFailureOutcome
EndpointModuleVersionReadOutcome: TypeAlias = EndpointModuleVersionProjection | EndpointModuleFailureOutcome
EndpointModuleOperationCreateOutcome: TypeAlias = EndpointModuleOperationProjection | EndpointModuleFailureOutcome
EndpointModuleOperationReadOutcome: TypeAlias = EndpointModuleOperationProjection | EndpointModuleFailureOutcome
EndpointModuleVersionCreateOutcome: TypeAlias = EndpointModuleVersionProjection | EndpointModuleFailureOutcome
EndpointModuleValidationOutcome: TypeAlias = EndpointModuleValidationProjection | EndpointModuleFailureOutcome
EndpointModuleVersionStateOutcome: TypeAlias = EndpointModuleVersionStateProjection | EndpointModuleFailureOutcome


@runtime_checkable
class EndpointModulePort(Protocol):
    async def availability(self) -> EndpointModuleAvailability: ...

    async def list_recipe_capabilities(self) -> EndpointModuleCapabilityCatalogOutcome: ...

    async def list_modules(self) -> EndpointModuleListOutcome: ...

    async def read_module(self, module: EndpointModuleRef) -> EndpointModuleReadOutcome: ...

    async def read_module_version(
        self,
        version: EndpointModuleVersionRef,
    ) -> EndpointModuleVersionReadOutcome: ...

    async def create_module_version(
        self, request: EndpointModuleVersionCreateRequest
    ) -> EndpointModuleVersionCreateOutcome: ...

    async def validate_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleValidationOutcome: ...

    async def publish_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleVersionStateOutcome: ...

    async def deprecate_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleVersionStateOutcome: ...

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
