"""Safe read/execute module boundary; no module authoring methods."""
from typing import Protocol, runtime_checkable

from .endpoint import EndpointDeviceRef, EndpointFailureOutcome, EndpointOperationRef
from .endpoint_module_contracts_generated import (
    EndpointDeviceModulesPageV1, ModuleCapabilityCatalogV1, ModuleOperationCreateV1,
    ModuleOperationDetailV1, ModuleOperationV1, ModuleVersionViewV1,
)


@runtime_checkable
class EndpointModulesPort(Protocol):
    async def list_primitives(self) -> ModuleCapabilityCatalogV1 | EndpointFailureOutcome: ...
    async def list_device_modules(self, device: EndpointDeviceRef, *, limit: int = 50,
        cursor: str | None = None) -> EndpointDeviceModulesPageV1 | EndpointFailureOutcome: ...
    async def read_module_version(self, key: str, version: str) -> ModuleVersionViewV1 | EndpointFailureOutcome: ...
    async def create_module_operation(self, device: EndpointDeviceRef, request: ModuleOperationCreateV1,
        *, idempotency_key: str, correlation_id: str) -> ModuleOperationV1 | EndpointFailureOutcome: ...
    async def read_module_operation(self, ref: EndpointOperationRef) -> ModuleOperationDetailV1 | EndpointFailureOutcome: ...


class UnavailableEndpointModulesPort:
    def __init__(self, code="endpoint_external_unconfigured"):
        self.code = code

    async def list_primitives(self):
        from .endpoint import EndpointUnavailable
        return EndpointUnavailable(code=self.code)

    async def list_device_modules(self, device, *, limit=50, cursor=None):
        return await self.list_primitives()

    async def read_module_version(self, key, version):
        return await self.list_primitives()

    async def create_module_operation(self, device, request, *, idempotency_key, correlation_id):
        return await self.list_primitives()

    async def read_module_operation(self, ref):
        return await self.list_primitives()
