"""Strict Endpoint Operations API v1 wire models; never expose these through EndpointPort."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeviceBindingVerifiedWireV1(_Wire):
    status: Literal["verified"]
    device_id: UUID
    hostname: str | None = Field(max_length=256)
    platform: Literal["windows", "linux", "unknown"]


class DeviceSummaryWireV1(_Wire):
    schema_version: Literal["endpoint_device_summary_v1"]
    device_id: UUID
    display_name: str = Field(min_length=1, max_length=256)
    retired: bool
    last_seen_at: datetime | None


class CapabilityWireV1(_Wire):
    capability: Literal["context.diagnostic.collect"]
    available: bool
    transport: Literal["gateway_wss"]
    risk: Literal["read_only"]
    consent_required: Literal[False]
    parameter_schema_version: Literal["diagnostic_collection_parameters_v1"]


class OtherCapabilityWireV1(_Wire):
    """Published provider descriptors validated but not exposed for Helpdesk execution."""

    capability: Literal[
        'dns.resolve',
        'network.ping',
        'tcp.connect',
        'route.get',
        'adapter.list',
        'system.service_status',
        'system.resource_snapshot',
        'process.list',
        'process.find',
        'service.list',
        'service.status',
        'printer.list',
        'printer.status',
        'printer.queue.summary',
        'software.list',
        'software.find',
        'filesystem.free_space',
        'filesystem.path_exists',
        'filesystem.file_metadata',
        'eventlog.query',
        'eventlog.recent_errors',
    ]
    available: bool
    transport: Literal["gateway_wss"]
    risk: Literal["read_only", "safe_read", "controlled_read"]
    consent_required: Literal[False]
    parameter_schema_version: Literal[
        'dns_resolve_parameters_v1',
        'network_ping_parameters_v1',
        'tcp_connect_parameters_v1',
        'route_get_parameters_v1',
        'adapter_list_parameters_v1',
        'service_status_parameters_v1',
        'system_resource_snapshot_parameters_v1',
        'process_list_parameters_v1',
        'process_find_parameters_v1',
        'service_list_parameters_v1',
        'service_status_v2_parameters_v1',
        'printer_list_parameters_v1',
        'printer_status_parameters_v1',
        'printer_queue_summary_parameters_v1',
        'software_list_parameters_v1',
        'software_find_parameters_v1',
        'filesystem_free_space_parameters_v1',
        'filesystem_path_exists_parameters_v1',
        'filesystem_file_metadata_parameters_v1',
        'eventlog_query_parameters_v1',
        'eventlog_recent_errors_parameters_v1',
    ]


class DeviceCapabilitiesWireV1(_Wire):
    schema_version: Literal["endpoint_device_capabilities_v1"]
    device_id: UUID
    capabilities: list[Annotated[CapabilityWireV1 | OtherCapabilityWireV1, Field(discriminator="capability")]] = Field(max_length=32)


class DiagnosticParametersWireV1(_Wire):
    """Provider-owned wording; Helpdesk keeps its localized internal DTO."""

    reason: Literal["Collect bounded diagnostic context"] = "Collect bounded diagnostic context"


class OperationCreateWireV1(_Wire):
    schema_version: Literal["endpoint_operation_create_v1"]
    capability: Literal["context.diagnostic.collect"]
    parameters: DiagnosticParametersWireV1


class OperationWireV1(_Wire):
    schema_version: Literal["endpoint_operation_v1"]
    operation_id: UUID
    device_id: UUID
    capability: Literal["context.diagnostic.collect"]
    status: Literal["queued", "delivered", "acknowledged", "running", "succeeded", "failed", "canceled", "expired"]
    created_at: datetime
    deadline_at: datetime
    completed_at: datetime | None
    result_available: bool
    warnings: list[str] = Field(max_length=16)


class DiagnosticProcessWireV1(_Wire):
    name: str = Field(min_length=1, max_length=128)
    state: Literal["running", "sleeping", "stopped", "unknown"]


class DiagnosticResultWireV1(_Wire):
    schema_version: Literal["endpoint_diagnostic_result_v1"]
    profile: Literal["diagnostic_v1"]
    collected_at: datetime
    reason: Literal["Collect bounded diagnostic context"]
    warnings: list[str] = Field(max_length=16)
    processes: list[DiagnosticProcessWireV1] = Field(max_length=64)
    log_excerpt: str | None = Field(default=None, max_length=8192)


class OperationResponseWireV1(_Wire):
    operation: OperationWireV1
    result: DiagnosticResultWireV1 | None
