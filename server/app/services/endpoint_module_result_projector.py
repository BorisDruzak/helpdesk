"""Closed privacy projection for typed Endpoint module capability results."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import ipaddress
import re
from typing import Annotated, Literal, TypeAlias, TypeVar

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)


_HOSTNAME_PATTERN = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*\.?\Z"
)
_INTERFACE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,127}$"
_ERROR_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
_NetworkTarget: TypeAlias = Annotated[str, Field(strict=True, min_length=1, max_length=253)]
_InterfaceName: TypeAlias = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=128, pattern=_INTERFACE_NAME_PATTERN),
]
_ErrorCode: TypeAlias = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=64, pattern=_ERROR_CODE_PATTERN),
]
_Latency: TypeAlias = Annotated[float, Field(strict=True, ge=0, le=60_000)]


class EndpointModuleResultProjectionError(ValueError):
    """The capability result cannot cross the Helpdesk evidence boundary."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _validate_network_target(value: str) -> str:
    if value != value.strip() or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("network target must be trimmed and control-character-free")
    if "://" in value or "/" in value or "@" in value:
        raise ValueError("network target must be a hostname or IP address")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if _HOSTNAME_PATTERN.fullmatch(value) is None:
            raise ValueError("network target must be a hostname or IP address") from None
        return value


def _validate_ip(value: str, *, version: int | None = None) -> str:
    if "%" in value:
        raise ValueError("IP address must not include a scope identifier")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise ValueError("value must be an IP address") from error
    if version is not None and address.version != version:
        raise ValueError("IP address family is invalid")
    return str(address)


class _ResultModel(_StrictModel):
    status: Literal["succeeded", "failed"]
    error_code: _ErrorCode | None
    collected_at: AwareDatetime

    @model_validator(mode="after")
    def validate_status_error(self) -> "_ResultModel":
        if self.status == "succeeded" and self.error_code is not None:
            raise ValueError("successful result must not contain error_code")
        if self.status == "failed" and self.error_code is None:
            raise ValueError("failed result must contain error_code")
        return self


class _DnsAddress(_StrictModel):
    family: Literal["ipv4", "ipv6"]
    address: Annotated[str, Field(strict=True, min_length=2, max_length=45)]

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        return _validate_ip(value)

    @model_validator(mode="after")
    def validate_family(self) -> "_DnsAddress":
        expected = 4 if self.family == "ipv4" else 6
        if ipaddress.ip_address(self.address).version != expected:
            raise ValueError("DNS address family must match address")
        return self


class _DnsResolveResult(_ResultModel):
    schema_version: Literal["dns_resolve_result_v1"]
    target: _NetworkTarget
    canonical_name: Annotated[str, Field(strict=True, min_length=1, max_length=253)] | None
    addresses: tuple[_DnsAddress, ...] = Field(max_length=16)
    address_count: Annotated[StrictInt, Field(ge=0, le=16)]

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        return _validate_network_target(value)

    @field_validator("canonical_name")
    @classmethod
    def validate_canonical_name(cls, value: str | None) -> str | None:
        return None if value is None else _validate_network_target(value)

    @model_validator(mode="after")
    def validate_address_count(self) -> "_DnsResolveResult":
        if self.address_count != len(self.addresses):
            raise ValueError("address_count must match addresses")
        return self


class _NetworkPingResult(_ResultModel):
    schema_version: Literal["network_ping_result_v1"]
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    transmitted: Annotated[StrictInt, Field(ge=0, le=5)]
    received: Annotated[StrictInt, Field(ge=0, le=5)]
    packet_loss_percent: Annotated[float, Field(strict=True, ge=0, le=100)]
    min_ms: _Latency | None
    avg_ms: _Latency | None
    max_ms: _Latency | None
    reachable: StrictBool

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        return _validate_network_target(value)

    @field_validator("resolved_ip")
    @classmethod
    def validate_resolved_ip(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ip(value)

    @model_validator(mode="after")
    def validate_measurements(self) -> "_NetworkPingResult":
        if self.received > self.transmitted:
            raise ValueError("received packets must not exceed transmitted packets")
        timings = (self.min_ms, self.avg_ms, self.max_ms)
        if self.received == 0 and (self.reachable or any(item is not None for item in timings)):
            raise ValueError("unreachable ping must not contain timings")
        if self.received > 0 and (
            not self.reachable
            or any(item is None for item in timings)
            or not self.min_ms <= self.avg_ms <= self.max_ms  # type: ignore[operator]
        ):
            raise ValueError("reachable ping must contain ordered timings")
        return self


class _TcpConnectResult(_ResultModel):
    schema_version: Literal["tcp_connect_result_v1"]
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    port: Annotated[StrictInt, Field(ge=1, le=65_535)]
    reachable: StrictBool
    latency_ms: _Latency | None

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        return _validate_network_target(value)

    @field_validator("resolved_ip")
    @classmethod
    def validate_resolved_ip(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ip(value)

    @model_validator(mode="after")
    def validate_reachability(self) -> "_TcpConnectResult":
        if self.reachable != (self.latency_ms is not None):
            raise ValueError("TCP reachability must match latency presence")
        return self


class _RouteGetResult(_ResultModel):
    schema_version: Literal["route_get_result_v1"]
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None = None
    family: Literal["ipv4", "ipv6"] | None = None
    port: Annotated[StrictInt, Field(ge=1, le=65_535)]
    source_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None = None
    interface_name: _InterfaceName | None = None
    strategy: Literal["udp_socket_inference"] = "udp_socket_inference"

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        return _validate_network_target(value)

    @field_validator("resolved_ip", "source_ip")
    @classmethod
    def validate_ip(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ip(value)

    @model_validator(mode="after")
    def validate_route_shape(self) -> "_RouteGetResult":
        if self.status == "succeeded":
            if self.resolved_ip is None or self.family is None or self.source_ip is None:
                raise ValueError("successful route result must contain inferred route values")
            expected = 4 if self.family == "ipv4" else 6
            if ipaddress.ip_address(self.resolved_ip).version != expected:
                raise ValueError("route family must match resolved IP")
        elif any(
            value is not None
            for value in (self.resolved_ip, self.family, self.source_ip, self.interface_name)
        ):
            raise ValueError("failed route result must contain only a stable error code")
        return self


class _AdapterItem(_StrictModel):
    name: _InterfaceName
    state: Literal["up", "down", "unknown"]
    kind: Literal["ethernet", "wifi", "loopback", "tunnel", "virtual", "unknown"]
    primary: StrictBool
    ipv4_addresses: tuple[Annotated[str, Field(strict=True)], ...] = Field(max_length=4)
    ipv6_addresses: tuple[Annotated[str, Field(strict=True)], ...] = Field(max_length=4)
    mtu: Annotated[StrictInt, Field(ge=0, le=65_535)]
    speed_mbps: Annotated[StrictInt, Field(ge=0, le=1_000_000)]

    @field_validator("ipv4_addresses")
    @classmethod
    def validate_ipv4_addresses(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_ip(value, version=4) for value in values)

    @field_validator("ipv6_addresses")
    @classmethod
    def validate_ipv6_addresses(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_ip(value, version=6) for value in values)


class _AdapterListResult(_ResultModel):
    schema_version: Literal["adapter_list_result_v1"]
    adapters: tuple[_AdapterItem, ...] = Field(max_length=32)
    adapter_count: Annotated[StrictInt, Field(ge=0, le=32)]
    up_count: Annotated[StrictInt, Field(ge=0, le=32)]

    @model_validator(mode="after")
    def validate_adapter_shape(self) -> "_AdapterListResult":
        if self.adapter_count != len(self.adapters):
            raise ValueError("adapter_count must match adapters")
        if self.up_count != sum(item.state == "up" for item in self.adapters):
            raise ValueError("up_count must match adapters")
        if len({item.name for item in self.adapters}) != len(self.adapters):
            raise ValueError("adapter names must be unique")
        return self


class _ServiceStatusResult(_ResultModel):
    schema_version: Literal["service_status_result_v1"]
    service_key: Literal["endpoint_agent", "endpoint_agent_updater"]
    installed: StrictBool
    state: Literal["running", "stopped", "paused", "failed", "not_found", "unknown"]
    start_mode: Literal["automatic", "manual", "disabled", "unknown"]


class _DnsSummary(_StrictModel):
    target: _NetworkTarget
    canonical_name: Annotated[str, Field(strict=True, min_length=1, max_length=253)] | None
    address_count: Annotated[StrictInt, Field(ge=0, le=16)]
    first_ipv4: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    first_ipv6: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None


class _PingSummary(_StrictModel):
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    loss: Annotated[float, Field(strict=True, ge=0, le=100)]
    min: _Latency | None
    avg: _Latency | None
    max: _Latency | None
    reachable: StrictBool


class _TcpSummary(_StrictModel):
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    port: Annotated[StrictInt, Field(ge=1, le=65_535)]
    reachable: StrictBool
    latency: _Latency | None


class _RouteSummary(_StrictModel):
    target: _NetworkTarget
    resolved_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    family: Literal["ipv4", "ipv6"] | None
    port: Annotated[StrictInt, Field(ge=1, le=65_535)]
    source_ip: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    interface_name: _InterfaceName | None
    strategy: Literal["udp_socket_inference"]


class _AdapterSummary(_StrictModel):
    count: Annotated[StrictInt, Field(ge=0, le=32)]
    up_count: Annotated[StrictInt, Field(ge=0, le=32)]
    primary_name: _InterfaceName | None
    primary_ipv4: Annotated[str, Field(strict=True, min_length=2, max_length=45)] | None
    has_ipv6: StrictBool
    has_wifi: StrictBool
    has_tunnel: StrictBool


class _ServiceSummary(_StrictModel):
    service_key: Literal["endpoint_agent", "endpoint_agent_updater"]
    installed: StrictBool
    state: Literal["running", "stopped", "paused", "failed", "not_found", "unknown"]
    start_mode: Literal["automatic", "manual", "disabled", "unknown"]


class _SnapshotStepBase(_StrictModel):
    sequence: Annotated[StrictInt, Field(ge=0, le=7)]
    status: Literal["succeeded", "failed", "canceled", "expired"]
    error_code: _ErrorCode | None


class _DnsSnapshotStep(_SnapshotStepBase):
    capability: Literal["dns.resolve"]
    summary: _DnsSummary


class _PingSnapshotStep(_SnapshotStepBase):
    capability: Literal["network.ping"]
    summary: _PingSummary


class _TcpSnapshotStep(_SnapshotStepBase):
    capability: Literal["tcp.connect"]
    summary: _TcpSummary


class _RouteSnapshotStep(_SnapshotStepBase):
    capability: Literal["route.get"]
    summary: _RouteSummary


class _AdapterSnapshotStep(_SnapshotStepBase):
    capability: Literal["adapter.list"]
    summary: _AdapterSummary


class _ServiceSnapshotStep(_SnapshotStepBase):
    capability: Literal["system.service_status"]
    summary: _ServiceSummary


EndpointModuleResultStepSnapshotV2: TypeAlias = Annotated[
    _DnsSnapshotStep
    | _PingSnapshotStep
    | _TcpSnapshotStep
    | _RouteSnapshotStep
    | _AdapterSnapshotStep
    | _ServiceSnapshotStep,
    Field(discriminator="capability"),
]


class EndpointModuleResultSnapshotV2(_StrictModel):
    """Versioned Helpdesk-owned evidence snapshot for one module result."""

    schema_version: Literal["endpoint_module_result_snapshot_v2"]
    steps: tuple[EndpointModuleResultStepSnapshotV2, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_step_sequences(self) -> "EndpointModuleResultSnapshotV2":
        sequences = [step.sequence for step in self.steps]
        if len(set(sequences)) != len(sequences):
            raise ValueError("module result step sequences must be unique")
        if sequences != sorted(sequences):
            raise ValueError("module result steps must be ordered by sequence")
        return self


_ResultModelT = TypeVar("_ResultModelT", bound=_ResultModel)


def _validated(
    model: type[_ResultModelT],
    result: Mapping[str, object],
) -> _ResultModelT:
    return model.model_validate(result)


def _project_dns_resolve(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_DnsResolveResult, result)
    return {
        "target": value.target,
        "canonical_name": value.canonical_name,
        "address_count": value.address_count,
        "first_ipv4": next(
            (item.address for item in value.addresses if item.family == "ipv4"), None
        ),
        "first_ipv6": next(
            (item.address for item in value.addresses if item.family == "ipv6"), None
        ),
    }


def _project_network_ping(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_NetworkPingResult, result)
    return {
        "target": value.target,
        "resolved_ip": value.resolved_ip,
        "loss": value.packet_loss_percent,
        "min": value.min_ms,
        "avg": value.avg_ms,
        "max": value.max_ms,
        "reachable": value.reachable,
    }


def _project_tcp_connect(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_TcpConnectResult, result)
    return {
        "target": value.target,
        "resolved_ip": value.resolved_ip,
        "port": value.port,
        "reachable": value.reachable,
        "latency": value.latency_ms,
    }


def _project_route_get(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_RouteGetResult, result)
    return {
        "target": value.target,
        "resolved_ip": value.resolved_ip,
        "family": value.family,
        "port": value.port,
        "source_ip": value.source_ip,
        "interface_name": value.interface_name,
        "strategy": value.strategy,
    }


def _project_adapter_list(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_AdapterListResult, result)
    primary = next((item for item in value.adapters if item.primary), None)
    return {
        "count": value.adapter_count,
        "up_count": value.up_count,
        "primary_name": primary.name if primary is not None else None,
        "primary_ipv4": (
            primary.ipv4_addresses[0]
            if primary is not None and primary.ipv4_addresses
            else None
        ),
        "has_ipv6": any(item.ipv6_addresses for item in value.adapters),
        "has_wifi": any(item.kind == "wifi" for item in value.adapters),
        "has_tunnel": any(item.kind == "tunnel" for item in value.adapters),
    }


def _project_service_status(result: Mapping[str, object]) -> dict[str, object | None]:
    value = _validated(_ServiceStatusResult, result)
    return {
        "service_key": value.service_key,
        "installed": value.installed,
        "state": value.state,
        "start_mode": value.start_mode,
    }


_Projector: TypeAlias = Callable[[Mapping[str, object]], dict[str, object | None]]

PROJECTORS: Mapping[str, _Projector] = {
    "dns.resolve": _project_dns_resolve,
    "network.ping": _project_network_ping,
    "tcp.connect": _project_tcp_connect,
    "route.get": _project_route_get,
    "adapter.list": _project_adapter_list,
    "system.service_status": _project_service_status,
}


def project_module_result(
    capability: str,
    result: Mapping[str, object],
) -> dict[str, object | None]:
    """Validate one closed Endpoint result schema and return its safe summary."""

    projector = PROJECTORS.get(capability)
    if projector is None:
        raise EndpointModuleResultProjectionError("unsupported Endpoint module capability")
    try:
        return projector(result)
    except (TypeError, ValidationError, ValueError) as error:
        raise EndpointModuleResultProjectionError(
            "invalid Endpoint module capability result"
        ) from error


__all__ = [
    "EndpointModuleResultProjectionError",
    "EndpointModuleResultSnapshotV2",
    "EndpointModuleResultStepSnapshotV2",
    "PROJECTORS",
    "project_module_result",
]
