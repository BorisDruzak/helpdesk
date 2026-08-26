"""Strict wire DTOs for the Endpoint Module Platform v1 adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModuleSummaryWireV1(_WireModel):
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    display_name: str = Field(min_length=1, max_length=128)


class ModuleVersionViewWireV1(_WireModel):
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    display_name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    state: Literal[
        "draft",
        "validation_failed",
        "validated",
        "lab_accepted",
        "published",
        "deprecated",
        "revoked",
    ]
    recipe: dict[str, object]


class ModuleVersionCreatedWireV1(_WireModel):
    module_version_id: UUID
    state: Literal["draft", "validation_failed", "validated", "lab_accepted", "published", "deprecated", "revoked"]


class ModuleVersionStateWireV1(_WireModel):
    schema_version: Literal["module_version_state_v1"]
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    state: Literal["draft", "validation_failed", "validated", "lab_accepted", "published", "deprecated", "revoked"]


class ModuleValidationWireV1(_WireModel):
    schema_version: Literal["module_validation_run_v1"]
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    status: Literal["succeeded", "failed"]
    error_codes: tuple[str, ...] = Field(max_length=32)
    warning_codes: tuple[str, ...] = Field(max_length=32)
    completed_at: datetime


class ModuleOperationCreateWireV1(_WireModel):
    schema_version: Literal["endpoint_module_operation_create_v1"] = "endpoint_module_operation_create_v1"
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    inputs: dict[str, str | int] = Field(min_length=1, max_length=8)


class ModuleOperationWireV1(_WireModel):
    schema_version: Literal["endpoint_module_operation_v1"] = "endpoint_module_operation_v1"
    operation_id: UUID
    device_id: UUID
    module_key: str = Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}$")
    version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    status: Literal[
        "queued",
        "delivered",
        "acknowledged",
        "running",
        "succeeded",
        "failed",
        "canceled",
        "expired",
    ]
    created_at: datetime
    deadline_at: datetime
    completed_at: datetime | None = None


class ModuleOperationStepWireV1(_WireModel):
    sequence: int = Field(ge=0, le=7)
    capability: Literal["dns.resolve", "network.ping", "tcp.connect"]
    status: Literal[
        "queued",
        "delivered",
        "acknowledged",
        "running",
        "succeeded",
        "failed",
        "canceled",
        "expired",
    ]
    error_code: str | None = Field(default=None, min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]{1,63}$")
    safe_result: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_safe_result(self) -> "ModuleOperationStepWireV1":
        if self.safe_result is None:
            return self
        schema_version = self.safe_result.get("schema_version")
        allowed_fields = {
            "dns_resolve_result_v1": {
                "schema_version", "target", "canonical_name", "addresses", "address_count",
                "status", "error_code", "collected_at",
            },
            "network_ping_result_v1": {
                "schema_version", "target", "resolved_ip", "transmitted", "received",
                "packet_loss_percent", "min_ms", "avg_ms", "max_ms", "reachable", "status",
                "error_code", "collected_at",
            },
            "tcp_connect_result_v1": {
                "schema_version", "target", "resolved_ip", "port", "reachable", "latency_ms",
                "status", "error_code", "collected_at",
            },
        }
        if not isinstance(schema_version, str) or schema_version not in allowed_fields:
            raise ValueError("unknown module step result schema")
        if not set(self.safe_result).issubset(allowed_fields[schema_version]):
            raise ValueError("unknown module step result fields")
        for key, value in self.safe_result.items():
            if key == "addresses":
                if not isinstance(value, list) or len(value) > 16:
                    raise ValueError("invalid module DNS addresses")
                if any(
                    not isinstance(item, Mapping)
                    or set(item) != {"family", "address"}
                    or not all(isinstance(part, str) for part in item.values())
                    for item in value
                ):
                    raise ValueError("invalid module DNS address")
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                raise ValueError("invalid module safe result value")
        return self


class ModuleOperationDetailWireV1(ModuleOperationWireV1):
    steps: tuple[ModuleOperationStepWireV1, ...] = Field(min_length=1, max_length=8)
