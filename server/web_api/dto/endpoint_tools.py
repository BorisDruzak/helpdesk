"""Closed browser DTOs; service credentials and editable recipes are excluded."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, AwareDatetime
from domain_ports.endpoint_module_contracts_generated import ModuleOperationDetailV1
from domain_ports.endpoint import EndpointDiagnosticResultProjection
from domain_ports.endpoint_context import EndpointContextSnapshot
from diagnostics.endpoint_tool_parameters import ToolInputV1, FixedSettingV1


class _DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EndpointToolRunCreateV1(_DTO):
    schema_version: Literal["endpoint_tool_run_create_v1"]
    expected_device_ref: UUID
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    version: str = Field(max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    inputs: dict[str, StrictStr | StrictInt] = Field(default_factory=dict, max_length=8)
    caller_key: str = Field(min_length=1, max_length=128)


class EndpointToolBatchCreateV1(_DTO):
    schema_version: Literal["endpoint_tool_batch_create_v1"]
    expected_device_ref: UUID
    caller_key: str = Field(min_length=1, max_length=128)


class EndpointToolAttachV1(_DTO):
    schema_version: Literal["endpoint_tool_attach_v1"]
    step_sequence: StrictInt = Field(ge=0,le=7)


class EndpointToolItemV1(_DTO):
    module_key: str
    version: str
    title: str
    availability: Literal["available", "unavailable", "unknown"]
    reason_code: str | None
    input_controls: tuple[ToolInputV1, ...] = ()
    fixed_settings: tuple[FixedSettingV1, ...] = ()
    capabilities: tuple[str, ...] = ()


class EndpointToolCatalogPayloadV1(_DTO):
    schema_version: Literal["endpoint_tool_catalog_v1"] = "endpoint_tool_catalog_v1"
    ticket_id: str
    device_ref: str
    enabled: bool
    can_run: bool
    observed_at: AwareDatetime
    items: tuple[EndpointToolItemV1, ...] = Field(max_length=100)
    next_cursor: str | None
    profiles: tuple[str, ...]


class EndpointToolRunPayloadV1(_DTO):
    schema_version: Literal["endpoint_tool_run_v1"] = "endpoint_tool_run_v1"
    run_id: str
    ticket_id: str
    device_ref: str
    kind: Literal["module", "context_collection", "diagnostic"]
    module_key: str | None
    version: str | None
    profile: str | None
    inputs: dict[str, StrictStr | StrictInt]
    status: Literal["create_pending", "queued", "delivered", "acknowledged", "running", "succeeded", "failed", "canceled", "expired"]
    remote_ref: str | None
    safe_result: ModuleOperationDetailV1 | EndpointContextSnapshot | EndpointDiagnosticResultProjection | None
    error_code: str | None
    created_at: AwareDatetime
    batch_id: str | None
    attached_steps: tuple[StrictInt, ...] = Field(default=(),max_length=8)


class EndpointToolBatchPayloadV1(_DTO):
    schema_version: Literal["endpoint_tool_batch_v1"] = "endpoint_tool_batch_v1"
    batch_id: str
    ticket_id: str
    status: Literal["running", "succeeded", "partial", "failed"]
    runs: tuple[EndpointToolRunPayloadV1, ...] = Field(min_length=6, max_length=6)
