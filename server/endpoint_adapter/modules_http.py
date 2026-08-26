"""Fail-closed HTTPS client for Endpoint Module Platform v1."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

import aiohttp
from pydantic import ValidationError

from .modules_wire import (
    ModuleOperationCreateWireV1,
    ModuleOperationDetailWireV1,
    ModuleOperationWireV1,
    ModuleSummaryWireV1,
    ModuleValidationWireV1,
    ModuleVersionCreatedWireV1,
    ModuleVersionStateWireV1,
    ModuleVersionViewWireV1,
)

try:
    from domain_ports.endpoint_modules import (
        EndpointModuleAvailability,
        EndpointModuleCatalogProjection,
        EndpointModuleDefinitionProjection,
        EndpointModuleInvalidProjection,
        EndpointModuleListOutcome,
        EndpointModuleNotFound,
        EndpointModuleOperationCreateOutcome,
        EndpointModuleOperationCreateRequest,
        EndpointModuleOperationProjection,
        EndpointModuleOperationReadOutcome,
        EndpointModuleOperationRef,
        EndpointModuleOperationStepProjection,
        EndpointModulePort,
        EndpointModuleReadOutcome,
        EndpointModuleRef,
        EndpointModuleUnavailable,
        EndpointModuleVersionProjection,
        EndpointModuleValidationOutcome,
        EndpointModuleValidationProjection,
        EndpointModuleVersionCreateOutcome,
        EndpointModuleVersionCreateRequest,
        EndpointModuleVersionStateOutcome,
        EndpointModuleVersionStateProjection,
        EndpointModuleVersionReadOutcome,
        EndpointModuleVersionRef,
    )
    from domain_ports.endpoint import OpaqueEndpointRef
except ModuleNotFoundError as exc:
    if exc.name not in {"domain_ports", "domain_ports.endpoint", "domain_ports.endpoint_modules"}:
        raise
    from server.domain_ports.endpoint import OpaqueEndpointRef
    from server.domain_ports.endpoint_modules import (
        EndpointModuleAvailability,
        EndpointModuleCatalogProjection,
        EndpointModuleDefinitionProjection,
        EndpointModuleInvalidProjection,
        EndpointModuleListOutcome,
        EndpointModuleNotFound,
        EndpointModuleOperationCreateOutcome,
        EndpointModuleOperationCreateRequest,
        EndpointModuleOperationProjection,
        EndpointModuleOperationReadOutcome,
        EndpointModuleOperationRef,
        EndpointModuleOperationStepProjection,
        EndpointModulePort,
        EndpointModuleReadOutcome,
        EndpointModuleRef,
        EndpointModuleUnavailable,
        EndpointModuleVersionProjection,
        EndpointModuleValidationOutcome,
        EndpointModuleValidationProjection,
        EndpointModuleVersionCreateOutcome,
        EndpointModuleVersionCreateRequest,
        EndpointModuleVersionStateOutcome,
        EndpointModuleVersionStateProjection,
        EndpointModuleVersionReadOutcome,
        EndpointModuleVersionRef,
    )


def _new_correlation_id() -> str:
    return str(uuid4())


def _path_ref(value: str) -> str:
    return quote(value, safe="")


class ExternalEndpointModuleHttpAdapter(EndpointModulePort):
    """Typed HTTPS-only Module Platform client with no Helpdesk dependencies."""

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
        return parsed.scheme == "http" or bool(
            self._ca_file and Path(self._ca_file).is_file() and self._ssl_context()
        )

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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: frozenset[int],
        body: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> object | EndpointModuleUnavailable | EndpointModuleInvalidProjection | EndpointModuleNotFound:
        if not self.configured:
            return EndpointModuleUnavailable(code="endpoint_module_external_unconfigured")
        correlation_id = str(self._correlation_id_factory() or "")
        if not correlation_id or any(ord(char) < 32 or ord(char) == 127 for char in correlation_id):
            return EndpointModuleInvalidProjection()
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._service_token}",
            "X-Correlation-ID": correlation_id,
        }
        if idempotency_key is not None:
            if not idempotency_key or any(ord(char) < 32 or ord(char) == 127 for char in idempotency_key):
                return EndpointModuleInvalidProjection()
            headers["Idempotency-Key"] = idempotency_key
        ssl_context = self._ssl_context()
        if self._parsed_base_url() is None or (self._base_url.startswith("https") and ssl_context is None):
            return EndpointModuleUnavailable(code="endpoint_module_external_ca_invalid")
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
                        return EndpointModuleInvalidProjection()
                    if response.status == 404:
                        return EndpointModuleNotFound()
                    if response.status in {401, 403, 409, 422}:
                        return EndpointModuleInvalidProjection()
                    if response.status == 429 or response.status >= 500 or response.status not in expected_statuses:
                        return EndpointModuleUnavailable(code="endpoint_module_transport_unavailable")
                    try:
                        envelope = await response.json(content_type=None)
                    except (aiohttp.ClientError, json.JSONDecodeError, ValueError):
                        return EndpointModuleInvalidProjection()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            return EndpointModuleUnavailable(code="endpoint_module_transport_unavailable")
        if not isinstance(envelope, Mapping) or set(envelope) != {"data"}:
            return EndpointModuleInvalidProjection()
        return envelope["data"]

    async def availability(self) -> EndpointModuleAvailability:
        if not self.configured:
            return EndpointModuleAvailability(status="unavailable", code="endpoint_module_external_unconfigured")
        return EndpointModuleAvailability(status="available", code="endpoint_module_external")

    async def list_modules(self) -> EndpointModuleListOutcome:
        payload = await self._request("GET", "/api/v1/modules", expected_statuses=frozenset({200}))
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        if not isinstance(payload, list):
            return EndpointModuleInvalidProjection()
        try:
            return tuple(
                EndpointModuleCatalogProjection(
                    module=EndpointModuleRef(module_key=wire.module_key),
                    display_name=wire.display_name,
                )
                for wire in (ModuleSummaryWireV1.model_validate(item) for item in payload)
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()

    async def read_module(self, module: EndpointModuleRef) -> EndpointModuleReadOutcome:
        payload = await self._request(
            "GET",
            f"/api/v1/modules/{_path_ref(module.module_key)}",
            expected_statuses=frozenset({200}),
        )
        result = self._version_projection(payload, expected_module=module)
        if not isinstance(result, EndpointModuleVersionProjection):
            return result
        return EndpointModuleDefinitionProjection(
            module=result.version.module,
            display_name=result.display_name,
            latest_version=result.version,
            latest_state=result.state,
        )

    async def read_module_version(
        self,
        version: EndpointModuleVersionRef,
    ) -> EndpointModuleVersionReadOutcome:
        payload = await self._request(
            "GET",
            f"/api/v1/modules/{_path_ref(version.module.module_key)}/versions/{_path_ref(version.version)}",
            expected_statuses=frozenset({200}),
        )
        result = self._version_projection(payload, expected_module=version.module)
        if isinstance(result, EndpointModuleVersionProjection) and result.version != version:
            return EndpointModuleInvalidProjection()
        return result

    async def create_module_version(
        self, request: EndpointModuleVersionCreateRequest
    ) -> EndpointModuleVersionCreateOutcome:
        payload = await self._request(
            "POST", "/api/v1/modules/versions", expected_statuses=frozenset({201}),
            body=request.model_dump(mode="json"),
        )
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleVersionCreatedWireV1.model_validate(payload)
            return EndpointModuleVersionProjection(
                version=EndpointModuleVersionRef(
                    module=EndpointModuleRef(module_key=request.recipe.module_key), version=request.version,
                ),
                display_name=request.display_name,
                state=wire.state,
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()

    async def validate_module_version(
        self, version: EndpointModuleVersionRef
    ) -> EndpointModuleValidationOutcome:
        payload = await self._request(
            "POST", f"/api/v1/modules/{_path_ref(version.module.module_key)}/versions/{_path_ref(version.version)}/validate",
            expected_statuses=frozenset({200}),
        )
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleValidationWireV1.model_validate(payload)
            if wire.module_key != version.module.module_key or wire.version != version.version:
                return EndpointModuleInvalidProjection()
            return EndpointModuleValidationProjection(
                module_version=version, status=wire.status, error_codes=wire.error_codes,
                warning_codes=wire.warning_codes, completed_at=wire.completed_at,
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()

    async def publish_module_version(self, version: EndpointModuleVersionRef) -> EndpointModuleVersionStateOutcome:
        return await self._transition_module_version(version, "publish")

    async def deprecate_module_version(self, version: EndpointModuleVersionRef) -> EndpointModuleVersionStateOutcome:
        return await self._transition_module_version(version, "deprecate")

    async def _transition_module_version(
        self, version: EndpointModuleVersionRef, action: str
    ) -> EndpointModuleVersionStateOutcome:
        payload = await self._request(
            "POST", f"/api/v1/modules/{_path_ref(version.module.module_key)}/versions/{_path_ref(version.version)}/{action}",
            expected_statuses=frozenset({200}),
        )
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleVersionStateWireV1.model_validate(payload)
            if wire.module_key != version.module.module_key or wire.version != version.version:
                return EndpointModuleInvalidProjection()
            return EndpointModuleVersionStateProjection(version=version, state=wire.state)
        except ValidationError:
            return EndpointModuleInvalidProjection()

    async def create_operation(
        self,
        request: EndpointModuleOperationCreateRequest,
        *,
        idempotency_key: OpaqueEndpointRef,
    ) -> EndpointModuleOperationCreateOutcome:
        wire_request = ModuleOperationCreateWireV1(
            module_key=request.module_version.module.module_key,
            version=request.module_version.version,
            inputs=request.inputs,
        )
        payload = await self._request(
            "POST",
            f"/api/v1/devices/{_path_ref(request.device_external_id)}/module-operations",
            expected_statuses=frozenset({200, 201}),
            body=wire_request.model_dump(mode="json"),
            idempotency_key=idempotency_key,
        )
        result = self._operation_projection(payload)
        if isinstance(result, EndpointModuleOperationProjection) and (
            result.device_external_id != request.device_external_id
            or result.module_version != request.module_version
        ):
            return EndpointModuleInvalidProjection()
        return result

    async def read_operation(
        self,
        operation: EndpointModuleOperationRef,
    ) -> EndpointModuleOperationReadOutcome:
        payload = await self._request(
            "GET",
            f"/api/v1/module-operations/{_path_ref(operation.external_id)}",
            expected_statuses=frozenset({200}),
        )
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleOperationDetailWireV1.model_validate(payload)
            if str(wire.operation_id) != operation.external_id:
                return EndpointModuleInvalidProjection()
            safe_steps = tuple(
                EndpointModuleOperationStepProjection(
                    sequence=step.sequence,
                    capability=step.capability,
                    status=step.status,
                    error_code=step.error_code,
                    safe_values={
                        key: value
                        for key, value in (step.safe_result or {}).items()
                        if key != "schema_version" and isinstance(value, (str, int, float, bool))
                    },
                )
                for step in wire.steps
                if step.safe_result is not None
                and step.status in {"succeeded", "failed", "canceled", "expired"}
            )
            return EndpointModuleOperationProjection(
                operation=EndpointModuleOperationRef(external_id=str(wire.operation_id)),
                module_version=EndpointModuleVersionRef(
                    module=EndpointModuleRef(module_key=wire.module_key),
                    version=wire.version,
                ),
                device_external_id=str(wire.device_id),
                status=wire.status,
                created_at=wire.created_at,
                deadline_at=wire.deadline_at,
                completed_at=wire.completed_at,
                result_available=bool(safe_steps),
                safe_result=safe_steps,
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()

    @staticmethod
    def _version_projection(
        payload: object,
        *,
        expected_module: EndpointModuleRef,
    ) -> EndpointModuleReadOutcome | EndpointModuleVersionReadOutcome:
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleVersionViewWireV1.model_validate(payload)
            version = EndpointModuleVersionRef(
                module=EndpointModuleRef(module_key=wire.module_key),
                version=wire.version,
            )
            if version.module != expected_module:
                return EndpointModuleInvalidProjection()
            return EndpointModuleVersionProjection(
                version=version,
                display_name=wire.display_name,
                state=wire.state,
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()

    @staticmethod
    def _operation_projection(
        payload: object,
    ) -> EndpointModuleOperationProjection | EndpointModuleUnavailable | EndpointModuleInvalidProjection | EndpointModuleNotFound:
        if isinstance(payload, (EndpointModuleUnavailable, EndpointModuleInvalidProjection, EndpointModuleNotFound)):
            return payload
        try:
            wire = ModuleOperationWireV1.model_validate(payload)
            return EndpointModuleOperationProjection(
                operation=EndpointModuleOperationRef(external_id=str(wire.operation_id)),
                module_version=EndpointModuleVersionRef(
                    module=EndpointModuleRef(module_key=wire.module_key),
                    version=wire.version,
                ),
                device_external_id=str(wire.device_id),
                status=wire.status,
                created_at=wire.created_at,
                deadline_at=wire.deadline_at,
                completed_at=wire.completed_at,
            )
        except ValidationError:
            return EndpointModuleInvalidProjection()
