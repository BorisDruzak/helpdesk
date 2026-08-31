"""Closed wire DTOs for the Endpoint Module capability catalog v1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _CatalogWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModuleCapabilityParameterWireV1(_CatalogWireModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value_type: Literal["string", "integer", "enum"]
    required: bool
    allowed_sources: list[Literal["input", "literal"]] = Field(min_length=1, max_length=2)
    enum_values: list[str] | None = Field(default=None, max_length=8)
    minimum: int | None = None
    maximum: int | None = None
    default_literal: str | int | None = None
    secret: Literal[False]


class ModuleCapabilityDescriptorWireV1(_CatalogWireModel):
    capability: Literal[
        "dns.resolve",
        "network.ping",
        "tcp.connect",
        "route.get",
        "adapter.list",
        "system.service_status",
    ]
    parameter_schema_version: str = Field(min_length=1, max_length=128)
    result_schema_version: str = Field(min_length=1, max_length=128)
    platforms: list[Literal["linux_amd64", "windows_amd64"]] = Field(min_length=1, max_length=2)
    minimum_agent_version: str = Field(min_length=5, max_length=64, pattern=r"^\d+\.\d+\.\d+$")
    risk: Literal["safe_read"]
    consent_required: Literal[False]
    feature_flag: Literal[
        "endpoint_network_primitives_enabled",
        "endpoint_read_only_primitives_enabled",
    ]
    policy: Literal["network_target_policy", "none"]
    parameters: list[ModuleCapabilityParameterWireV1] = Field(max_length=4)


class ModuleCapabilityCatalogWireV1(_CatalogWireModel):
    schema_version: Literal["endpoint_module_capability_catalog_v1"]
    items: list[ModuleCapabilityDescriptorWireV1] = Field(min_length=6, max_length=6)
