from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.providers.manual_provider import ManualCapabilityProvider
from diagnostics.providers.observer_provider import ObserverCapabilityProvider
from diagnostics.providers.remote_assist_provider import RemoteAssistCapabilityProvider
from diagnostics.providers.server_connector import ServerConnectorProvider


class CapabilityExecutionRouter:
    def __init__(
        self,
        *,
        capability_registry: CapabilityRegistry,
        tool_service: Any,
        server_connector_provider: Any = None,
        observer_provider: Any = None,
        remote_assist_provider: Any = None,
        manual_provider: Any = None,
    ) -> None:
        self.capability_registry = capability_registry
        self.tool_service = tool_service
        self.server_connector_provider = server_connector_provider or ServerConnectorProvider()
        self.observer_provider = observer_provider or ObserverCapabilityProvider()
        self.remote_assist_provider = remote_assist_provider or RemoteAssistCapabilityProvider()
        self.manual_provider = manual_provider or ManualCapabilityProvider()

    async def resolve_capability(self, capability_id: str, *, device_id: Optional[str] = None):
        return await self.capability_registry.resolve_capability(capability_id, device_id=device_id)

    async def run_capability(
        self,
        *,
        ticket_id: str,
        device_id: Optional[str],
        capability_id: str,
        params: Dict[str, Any],
        actor: Any,
    ) -> Dict[str, Any]:
        capability = await self.resolve_capability(capability_id, device_id=device_id)
        if not capability:
            return {
                "status": "error",
                "error_code": "CAPABILITY_NOT_FOUND",
                "message": f"Capability '{capability_id}' not found",
            }
        target = capability.execution_target
        if target in {"agent_builtin", "agent_managed_module"}:
            return await self.route_agent_tool(
                ticket_id=ticket_id,
                device_id=device_id,
                capability_id=capability.id,
                params=params,
                actor=actor,
            )
        if target == "server_connector":
            return await self.route_server_connector(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
        if target == "observer_query":
            return await self.route_observer_query(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
        if target == "remote_assist":
            return await self.route_remote_assist(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
        if target == "manual":
            return await self.route_manual(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
        return {
            "status": "unsupported",
            "error_code": "CAPABILITY_TARGET_UNSUPPORTED",
            "message": f"Execution target '{target}' is reserved but not implemented",
        }

    async def route_agent_tool(
        self,
        *,
        ticket_id: str,
        device_id: Optional[str],
        capability_id: str,
        params: Dict[str, Any],
        actor: Any,
    ) -> Dict[str, Any]:
        if not device_id:
            return {"status": "error", "error_code": "DEVICE_REQUIRED", "message": "Device is required"}
        return await self.tool_service.run_tool(
            device_id=device_id,
            ticket_id=ticket_id,
            tool_name=capability_id,
            params=dict(params or {}),
            call_id=f"capability-{uuid.uuid4()}",
            auth_context=actor,
            wait_for_result=False,
        )

    async def route_server_connector(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.server_connector_provider.run(capability, **kwargs)

    async def route_observer_query(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.observer_provider.run(capability, **kwargs)

    async def route_remote_assist(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.remote_assist_provider.run(capability, **kwargs)

    async def route_manual(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.manual_provider.run(capability, **kwargs)
