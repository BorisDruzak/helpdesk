"""Bounded typed module transport through the existing verified HTTPS adapter."""
import re
from collections.abc import Mapping
from urllib.parse import quote, urlencode

from pydantic import ValidationError

try:
    from domain_ports.endpoint import EndpointInvalidProjection
    from domain_ports.endpoint_module_contracts_generated import (
        EndpointDeviceModulesPageV1, ModuleCapabilityCatalogV1, ModuleOperationCreateV1,
        ModuleOperationDetailV1, ModuleOperationV1, ModuleVersionViewV1,
    )
except ModuleNotFoundError as error:
    if error.name != "domain_ports":
        raise
    from server.domain_ports.endpoint import EndpointInvalidProjection
    from server.domain_ports.endpoint_module_contracts_generated import (
        EndpointDeviceModulesPageV1, ModuleCapabilityCatalogV1, ModuleOperationCreateV1,
        ModuleOperationDetailV1, ModuleOperationV1, ModuleVersionViewV1,
    )

from .modules_wire import validate_module_projection


class EndpointModulesHttpMixin:
    async def _module_projection(self, method, path, model, *, unwrap_data=True, **kwargs):
        payload = await self._request(method, path, bounded_response=True, unwrap_data=unwrap_data, **kwargs)
        if not isinstance(payload, Mapping):
            return payload
        try:
            return validate_module_projection(model.model_validate(payload))
        except (ValidationError, ValueError, TypeError, KeyError):
            return EndpointInvalidProjection()

    async def list_primitives(self):
        return await self._module_projection("GET", "/api/v1/module-capabilities", ModuleCapabilityCatalogV1,
            expected_statuses=frozenset({200}))

    async def list_device_modules(self, device, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100 or (cursor is not None and (not isinstance(cursor, str) or len(cursor) > 1024)):
            return EndpointInvalidProjection()
        query = urlencode({"limit": limit, **({"cursor": cursor} if cursor is not None else {})})
        result = await self._module_projection("GET", f"/api/v1/devices/{quote(device.external_id, safe='')}/modules?{query}",
            EndpointDeviceModulesPageV1, unwrap_data=False, expected_statuses=frozenset({200}))
        if isinstance(result, EndpointDeviceModulesPageV1) and str(result.device_id) != device.external_id:
            return EndpointInvalidProjection()
        return result

    async def read_module_version(self, key, version):
        if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}", key) is None or len(key) > 128:
            return EndpointInvalidProjection()
        if not isinstance(version, str) or re.fullmatch(r"\d+\.\d+\.\d+", version) is None or len(version) > 64:
            return EndpointInvalidProjection()
        result = await self._module_projection("GET", f"/api/v1/modules/{quote(key, safe='')}/versions/{quote(version, safe='')}",
            ModuleVersionViewV1, expected_statuses=frozenset({200}))
        if isinstance(result, ModuleVersionViewV1) and (result.module_key != key or result.version != version):
            return EndpointInvalidProjection()
        return result

    async def create_module_operation(self, device, request, *, idempotency_key, correlation_id):
        if not isinstance(idempotency_key, str) or re.fullmatch(r"[!-~][ -~]{6,126}[!-~]", idempotency_key) is None:
            return EndpointInvalidProjection()
        if not isinstance(correlation_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", correlation_id) is None:
            return EndpointInvalidProjection()
        try:
            parsed = request if isinstance(request, ModuleOperationCreateV1) else ModuleOperationCreateV1.model_validate(request)
        except ValidationError:
            return EndpointInvalidProjection()
        # Creation returns the parent only; steps are obtained through caller-owned GET.
        result = await self._module_projection("POST", f"/api/v1/devices/{quote(device.external_id, safe='')}/module-operations",
            ModuleOperationV1, body=parsed.model_dump(mode="json"), extra_headers={"Idempotency-Key": idempotency_key},
            correlation_id_override=correlation_id, expected_statuses=frozenset({200, 201}))
        if isinstance(result, ModuleOperationV1) and (str(result.device_id) != device.external_id or result.module_key != parsed.module_key or result.version != parsed.version):
            return EndpointInvalidProjection()
        return result

    async def read_module_operation(self, ref):
        result = await self._module_projection("GET", f"/api/v1/module-operations/{quote(ref.external_id, safe='')}",
            ModuleOperationDetailV1, expected_statuses=frozenset({200}))
        if isinstance(result, ModuleOperationDetailV1) and str(result.operation_id) != ref.external_id:
            return EndpointInvalidProjection()
        return result
