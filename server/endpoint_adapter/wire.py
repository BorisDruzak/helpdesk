"""Strict Endpoint Operations API v1 wire models; never expose these through EndpointPort."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class DeviceCapabilitiesWireV1(_Wire):
    schema_version: Literal["endpoint_device_capabilities_v1"]
    device_id: UUID
    capabilities: list[CapabilityWireV1] = Field(max_length=32)


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
    reason: str = Field(min_length=1, max_length=256)
    warnings: list[str] = Field(max_length=16)
    processes: list[DiagnosticProcessWireV1] = Field(max_length=64)
    log_excerpt: str | None = Field(default=None, max_length=8192)


class OperationResponseWireV1(_Wire):
    operation: OperationWireV1
    result: DiagnosticResultWireV1 | None

