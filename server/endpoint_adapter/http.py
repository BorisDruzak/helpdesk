"""Fail-closed HTTP transport for Endpoint Operations API v1."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import json
from pathlib import Path
import ssl
from typing import Any, TypeVar
from urllib.parse import quote, urlsplit
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, ValidationError

from .wire import (
    DeviceCapabilitiesWireV1,
    DeviceSummaryWireV1,
    OperationCreateWireV1,
    OperationResponseWireV1,
)

try:
    from domain_ports.endpoint import (
        EndpointAvailability,
        EndpointCapabilitiesOutcome,
        EndpointCapabilitiesProjection,
        EndpointConflict,
        EndpointDeviceOutcome,
        EndpointDeviceProjection,
        EndpointDeviceRef,
        EndpointForbidden,
        EndpointInvalidProjection,
        EndpointNotFound,
        EndpointOperationCreateOutcome,
        EndpointOperationCreateRequest,
        EndpointOperationProjection,
        EndpointOperationReadOutcome,
        EndpointOperationRef,
        EndpointPort,
        EndpointUnauthorized,
        EndpointUnavailable,
        OpaqueEndpointRef,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"domain_ports", "domain_ports.endpoint"}:
        raise
    from server.domain_ports.endpoint import (
        EndpointAvailability,
        EndpointCapabilitiesOutcome,
        EndpointCapabilitiesProjection,
        EndpointConflict,
        EndpointDeviceOutcome,
        EndpointDeviceProjection,
        EndpointDeviceRef,
        EndpointForbidden,
        EndpointInvalidProjection,
        EndpointNotFound,
        EndpointOperationCreateOutcome,
        EndpointOperationCreateRequest,
        EndpointOperationProjection,
        EndpointOperationReadOutcome,
        EndpointOperationRef,
        EndpointPort,
        EndpointUnauthorized,
        EndpointUnavailable,
        OpaqueEndpointRef,
    )


_T = TypeVar("_T", bound=BaseModel)
_TRANSPORT_UNAVAILABLE = EndpointUnavailable()
_HTTP_FAILURES: dict[int, type[BaseModel]] = {
    401: EndpointUnauthorized,
    403: EndpointForbidden,
    404: EndpointNotFound,
    409: EndpointConflict,
}


def _new_correlation_id() -> str:
    return str(uuid4())


def _path_ref(value: str) -> str:
    return quote(value, safe="")


class ExternalEndpointHttpAdapter(EndpointPort):
    """HTTPS-only Endpoint Operations API v1 client.

    The adapter has no database, ticket, WebSocket or logging dependencies.
    It sends external identifiers only as quoted path components and accepts a
    response only when the transport correlation and typed safe projection are
    exact.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        ca_file: str,
        timeout_seconds: float,
        correlation_id_factory: Callable[[], str] = _new_correlation_id,
        allow_insecure_test_url: bool = False,
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._service_token = str(service_token or "")
        self._ca_file = str(ca_file or "")
        self._timeout_seconds = max(0.05, min(float(timeout_seconds), 10.0))
        self._correlation_id_factory = correlation_id_factory
        self._allow_insecure_test_url = bool(allow_insecure_test_url)

    @property
    def configured(self) -> bool:
        parsed = self._parsed_base_url()
        if parsed is None or not self._service_token.strip():
            return False
        if parsed.scheme == "http":
            return self._allow_insecure_test_url
        return bool(self._ca_file and Path(self._ca_file).is_file() and self._ssl_context())

    def _parsed_base_url(self) -> Any | None:
        try:
            parsed = urlsplit(self._base_url)
            hostname = parsed.hostname
            parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and not self._allow_insecure_test_url)
        ):
            return None
        return parsed

    def _ssl_context(self) -> ssl.SSLContext | None:
        parsed = self._parsed_base_url()
        if parsed is None or parsed.scheme != "https":
            return None
        try:
            return ssl.create_default_context(cafile=self._ca_file)
        except (OSError, ssl.SSLError):
            return None

    def _headers(self, correlation_id: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._service_token}",
            "X-Correlation-ID": correlation_id,
        }

    @staticmethod
    def _valid_header_value(value: object) -> bool:
        return isinstance(value, str) and bool(value) and not any(
            ord(char) < 32 or ord(char) == 127 for char in value
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: frozenset[int],
        body: Mapping[str, object] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object] | BaseModel:
        if not self.configured:
            return EndpointUnavailable(code="endpoint_external_unconfigured")
        correlation_id = str(self._correlation_id_factory() or "")
        if not self._valid_header_value(correlation_id):
            return EndpointInvalidProjection()
        headers = self._headers(correlation_id)
        if extra_headers:
            if any(not self._valid_header_value(value) for value in extra_headers.values()):
                return EndpointInvalidProjection()
            headers.update(extra_headers)
        parsed_base_url = self._parsed_base_url()
        if parsed_base_url is None:
            return EndpointUnavailable(code="endpoint_external_unconfigured")
        ssl_context = self._ssl_context()
        if parsed_base_url.scheme == "https" and ssl_context is None:
            return EndpointUnavailable(code="endpoint_external_ca_invalid")
        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    f"{self._base_url}{path}",
                    json=body,
                    headers=headers,
                    allow_redirects=False,
                    ssl=ssl_context,
                ) as response:
                    if response.headers.get("X-Correlation-ID") != correlation_id:
                        return EndpointInvalidProjection()
                    if response.status in _HTTP_FAILURES:
                        return _HTTP_FAILURES[response.status]()
                    if response.status == 422:
                        return EndpointInvalidProjection()
                    if response.status == 429 or response.status >= 500 or response.status not in expected_statuses:
                        return _TRANSPORT_UNAVAILABLE
                    try:
                        envelope = await response.json(content_type=None)
                    except (aiohttp.ClientError, json.JSONDecodeError, ValueError):
                        return EndpointInvalidProjection()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            return _TRANSPORT_UNAVAILABLE
        if not isinstance(envelope, Mapping) or set(envelope) != {"data"} or not isinstance(envelope.get("data"), Mapping):
            return EndpointInvalidProjection()
        return dict(envelope["data"])

    @staticmethod
    def _parse_projection(
        payload: Mapping[str, object] | BaseModel,
        *,
        model: type[_T],
        expected_keys: frozenset[str],
        add_source: bool = False,
    ) -> _T | BaseModel:
        if not isinstance(payload, Mapping):
            return payload
        if set(payload) != expected_keys:
            return EndpointInvalidProjection()
        prepared = dict(payload)
        if add_source:
            prepared["source"] = "external_authoritative"
        try:
            return model.model_validate(prepared)
        except ValidationError:
            return EndpointInvalidProjection()

    async def availability(self) -> EndpointAvailability:
        if not self.configured:
            return EndpointAvailability(status="unavailable", code="endpoint_external_unconfigured")
        return EndpointAvailability(status="available", code="endpoint_external")

    async def read_device(self, device: EndpointDeviceRef) -> EndpointDeviceOutcome:
        payload = await self._request(
                "GET",
                f"/api/v1/devices/{_path_ref(device.external_id)}",
                expected_statuses=frozenset({200}),
            )
        if not isinstance(payload, Mapping):
            return payload  # type: ignore[return-value]
        try:
            wire = DeviceSummaryWireV1.model_validate(payload)
            result = EndpointDeviceProjection(device=EndpointDeviceRef(external_id=str(wire.device_id)), display_name=wire.display_name, retired=wire.retired, last_seen_at=wire.last_seen_at)
        except ValidationError:
            return EndpointInvalidProjection()
        if result.device != device:
            return EndpointInvalidProjection()
        return result  # type: ignore[return-value]

    async def list_capabilities(self, device: EndpointDeviceRef) -> EndpointCapabilitiesOutcome:
        payload = await self._request(
                "GET",
                f"/api/v1/devices/{_path_ref(device.external_id)}/capabilities",
                expected_statuses=frozenset({200}),
            )
        if not isinstance(payload, Mapping):
            return payload  # type: ignore[return-value]
        try:
            wire = DeviceCapabilitiesWireV1.model_validate(payload)
            result = EndpointCapabilitiesProjection(device=EndpointDeviceRef(external_id=str(wire.device_id)), items=tuple(item.model_dump() for item in wire.capabilities))
        except ValidationError:
            return EndpointInvalidProjection()
        if result.device != device:
            return EndpointInvalidProjection()
        return result  # type: ignore[return-value]

    async def create_operation(
        self,
        device: EndpointDeviceRef,
        request: EndpointOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointOperationCreateOutcome:
        wire_request = OperationCreateWireV1(
            schema_version=request.schema_version,
            capability=request.capability,
            parameters={},
        )
        payload = await self._request(
                "POST",
                f"/api/v1/devices/{_path_ref(device.external_id)}/operations",
                expected_statuses=frozenset({200, 201}),
                body=wire_request.model_dump(mode="json"),
                extra_headers={"Idempotency-Key": idempotency_key},
            )
        result = self._operation_projection(payload, correlation=request.correlation)
        if isinstance(result, EndpointOperationProjection) and result.device != device:
            return EndpointInvalidProjection()
        return result  # type: ignore[return-value]

    async def read_operation(self, operation: EndpointOperationRef) -> EndpointOperationReadOutcome:
        payload = await self._request(
                "GET",
                f"/api/v1/operations/{_path_ref(operation.external_id)}",
                expected_statuses=frozenset({200}),
            )
        result = self._operation_projection(payload, correlation=None)
        if isinstance(result, EndpointOperationProjection) and result.operation != operation:
            return EndpointInvalidProjection()
        return result  # type: ignore[return-value]

    @staticmethod
    def _operation_projection(payload: Mapping[str, object] | BaseModel, *, correlation: object | None) -> EndpointOperationProjection | BaseModel:
        if not isinstance(payload, Mapping):
            return payload
        try:
            wire = OperationResponseWireV1.model_validate(payload)
            if wire.operation.status == "succeeded" and wire.result is None:
                return EndpointInvalidProjection()
            if wire.operation.result_available != (wire.result is not None):
                return EndpointInvalidProjection()
            return EndpointOperationProjection(
                operation=EndpointOperationRef(external_id=str(wire.operation.operation_id)),
                device=EndpointDeviceRef(external_id=str(wire.operation.device_id)),
                capability=wire.operation.capability,
                status=wire.operation.status,
                created_at=wire.operation.created_at,
                deadline_at=wire.operation.deadline_at,
                completed_at=wire.operation.completed_at,
                correlation=correlation,
                result_available=wire.operation.result_available,
                safe_result=None if wire.result is None else {
                    "profile": wire.result.profile,
                    "collected_at": wire.result.collected_at,
                    "reason": "Диагностика по обращению",
                    "warnings": tuple(wire.result.warnings),
                    "processes": tuple(item.model_dump() for item in wire.result.processes),
                    "log_excerpt": wire.result.log_excerpt,
                },
                warning_codes=tuple(wire.operation.warnings),
            )
        except ValidationError:
            return EndpointInvalidProjection()
