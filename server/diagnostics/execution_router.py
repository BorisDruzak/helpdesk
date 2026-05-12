from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.providers.manual_provider import ManualCapabilityProvider
from diagnostics.providers.observer_provider import ObserverCapabilityProvider
from diagnostics.providers.remote_assist_provider import RemoteAssistCapabilityProvider
from diagnostics.providers.server_builtin import ServerBuiltinProvider
from diagnostics.providers.server_connector import ServerConnectorProvider
from diagnostics.observability import NullCapabilityExecutionObserver, monotonic_ms


TARGET_EXECUTION_KIND = {
    "agent_builtin": "operation",
    "agent_managed_module": "operation",
    "server_builtin": "query",
    "server_connector": "query",
    "observer_query": "query",
    "remote_assist": "session",
    "manual": "manual_evidence",
    "hybrid": "session",
}

EXECUTABLE_READINESS = {"available"}


class CapabilityExecutionRouter:
    def __init__(
        self,
        *,
        capability_registry: CapabilityRegistry,
        tool_service: Any,
        server_builtin_provider: Any = None,
        server_connector_provider: Any = None,
        observer_provider: Any = None,
        remote_assist_provider: Any = None,
        manual_provider: Any = None,
        observability: Any = None,
    ) -> None:
        self.capability_registry = capability_registry
        self.tool_service = tool_service
        self.server_builtin_provider = server_builtin_provider or ServerBuiltinProvider()
        self.server_connector_provider = server_connector_provider or ServerConnectorProvider()
        self.observer_provider = observer_provider or ObserverCapabilityProvider()
        self.remote_assist_provider = remote_assist_provider or RemoteAssistCapabilityProvider()
        self.manual_provider = manual_provider or ManualCapabilityProvider()
        self.observability = observability or NullCapabilityExecutionObserver()

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
        readiness: Any = None,
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        capability = await self.resolve_capability(capability_id, device_id=device_id)
        if not capability:
            return {
                "status": "error",
                "error_code": "CAPABILITY_NOT_FOUND",
                "message": f"Capability '{capability_id}' not found",
                "capability_id": capability_id,
                "ticket_id": ticket_id,
                "device_id": device_id,
                "idempotency_key": idempotency_key,
                "timeout_ms": timeout_ms,
            }
        started_ms = monotonic_ms()
        await self.observability.record_started(
            capability=capability,
            ticket_id=ticket_id,
            device_id=device_id,
            actor=actor,
            params=params,
            readiness=readiness,
            idempotency_key=idempotency_key,
            timeout_ms=timeout_ms,
        )
        try:
            result = await self._run_resolved_capability(
                capability,
                ticket_id=ticket_id,
                device_id=device_id,
                params=params,
                actor=actor,
                readiness=readiness,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
            await self.observability.record_finished(
                capability=capability,
                ticket_id=ticket_id,
                device_id=device_id,
                actor=actor,
                params=params,
                result=result,
                readiness=readiness,
                duration_ms=max(0, monotonic_ms() - started_ms),
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
            return result
        except Exception as exc:
            await self.observability.record_finished(
                capability=capability,
                ticket_id=ticket_id,
                device_id=device_id,
                actor=actor,
                params=params,
                result={"status": "error", "capability_id": capability.id, "execution_target": capability.execution_target},
                readiness=readiness,
                duration_ms=max(0, monotonic_ms() - started_ms),
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
                error=exc,
            )
            raise

    async def _run_resolved_capability(
        self,
        capability,
        *,
        ticket_id: str,
        device_id: Optional[str],
        params: Dict[str, Any],
        actor: Any,
        readiness: Any = None,
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        readiness_error = self._readiness_error(
            capability,
            readiness=readiness,
            ticket_id=ticket_id,
            device_id=device_id,
            idempotency_key=idempotency_key,
            timeout_ms=timeout_ms,
        )
        if readiness_error is not None:
            return readiness_error
        target = capability.execution_target
        if target in {"agent_builtin", "agent_managed_module"}:
            result = await self.route_agent_tool(
                ticket_id=ticket_id,
                device_id=device_id,
                capability_id=capability.id,
                params=params,
                actor=actor,
                idempotency_key=idempotency_key,
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if target == "server_builtin":
            result = await self.route_server_builtin(
                capability,
                ticket_id=ticket_id,
                device_id=device_id,
                params=params,
                actor=actor,
                state=self.capability_registry.state,
                timeout_ms=timeout_ms,
                idempotency_key=idempotency_key,
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if target == "server_connector":
            result = await self.route_server_connector(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if target == "observer_query":
            result = await self.route_observer_query(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if target == "remote_assist":
            result = await self.route_remote_assist(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if target == "manual":
            result = await self.route_manual(
                capability, ticket_id=ticket_id, device_id=device_id, params=params, actor=actor, state=self.capability_registry.state
            )
            return self._envelope(
                capability,
                result,
                ticket_id=ticket_id,
                device_id=device_id,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        return {
            "status": "unsupported",
            "error_code": "CAPABILITY_TARGET_UNSUPPORTED",
            "message": f"Execution target '{target}' is reserved but not implemented",
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "device_id": device_id,
            "execution_target": target,
            "execution_kind": TARGET_EXECUTION_KIND.get(target, "unknown"),
            "idempotency_key": idempotency_key,
            "timeout_ms": timeout_ms,
        }

    async def route_agent_tool(
        self,
        *,
        ticket_id: str,
        device_id: Optional[str],
        capability_id: str,
        params: Dict[str, Any],
        actor: Any,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not device_id:
            return {"status": "error", "error_code": "DEVICE_REQUIRED", "message": "Device is required"}
        return await self.tool_service.run_tool(
            device_id=device_id,
            ticket_id=ticket_id,
            tool_name=capability_id,
            params=dict(params or {}),
            call_id=idempotency_key or f"capability-{uuid.uuid4()}",
            auth_context=actor,
            wait_for_result=False,
        )

    async def route_server_builtin(self, capability, **kwargs) -> Dict[str, Any]:
        return await self._route_query_provider(self.server_builtin_provider, capability, **kwargs)

    async def route_server_connector(self, capability, **kwargs) -> Dict[str, Any]:
        return await self._route_query_provider(self.server_connector_provider, capability, **kwargs)

    async def _route_query_provider(self, provider, capability, **kwargs) -> Dict[str, Any]:
        if hasattr(provider, "run_query"):
            result = await provider.run_query(capability, **kwargs)
            if hasattr(provider, "normalize_result"):
                result = provider.normalize_result(capability, result, **kwargs)
            if hasattr(provider, "map_evidence"):
                evidence_preview = provider.map_evidence(capability, result, **kwargs)
                if evidence_preview is not None:
                    result = dict(result or {})
                    result["evidence_preview"] = evidence_preview
            return result
        return await provider.run(capability, **kwargs)

    async def route_observer_query(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.observer_provider.run(capability, **kwargs)

    async def route_remote_assist(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.remote_assist_provider.run(capability, **kwargs)

    async def route_manual(self, capability, **kwargs) -> Dict[str, Any]:
        return await self.manual_provider.run(capability, **kwargs)

    def _readiness_error(
        self,
        capability,
        *,
        readiness: Any,
        ticket_id: str,
        device_id: Optional[str],
        idempotency_key: Optional[str],
        timeout_ms: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if readiness is None:
            return None
        if hasattr(readiness, "to_dict"):
            readiness_dict = readiness.to_dict()
        elif isinstance(readiness, dict):
            readiness_dict = dict(readiness)
        else:
            readiness_dict = {"readiness": str(readiness)}
        readiness_status = str(readiness_dict.get("readiness") or "").strip()
        if self._readiness_is_executable(capability, readiness_dict):
            return None
        return {
            "status": "error",
            "error_code": "CAPABILITY_NOT_READY",
            "reason_code": readiness_dict.get("reason_code") or readiness_status.upper() or "CAPABILITY_NOT_READY",
            "message": readiness_dict.get("reason") or "Capability is not ready to run",
            "readiness": readiness_status or "unknown",
            "readiness_actions": list(readiness_dict.get("actions") or []),
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "device_id": device_id,
            "execution_target": capability.execution_target,
            "execution_kind": TARGET_EXECUTION_KIND.get(capability.execution_target, "unknown"),
            "idempotency_key": idempotency_key,
            "timeout_ms": timeout_ms,
        }

    def _readiness_is_executable(self, capability, readiness: Dict[str, Any]) -> bool:
        readiness_status = str(readiness.get("readiness") or "").strip()
        if readiness_status in EXECUTABLE_READINESS:
            return True
        if (
            readiness_status == "consent_required"
            and capability.execution_target in {"agent_builtin", "agent_managed_module", "remote_assist"}
            and "request_consent" in set(readiness.get("actions") or [])
        ):
            return True
        return (
            readiness_status == "install_required"
            and capability.execution_target == "agent_managed_module"
            and capability.supports_auto_install
        )

    def _envelope(
        self,
        capability,
        result: Dict[str, Any],
        *,
        ticket_id: str,
        device_id: Optional[str],
        idempotency_key: Optional[str],
        timeout_ms: Optional[int],
    ) -> Dict[str, Any]:
        payload = dict(result or {})
        payload.setdefault("capability_id", capability.id)
        payload.setdefault("ticket_id", ticket_id)
        payload.setdefault("device_id", device_id)
        payload["execution_target"] = capability.execution_target
        payload["execution_kind"] = TARGET_EXECUTION_KIND.get(capability.execution_target, "unknown")
        payload["provider_id"] = capability.provider_id
        payload["provider_type"] = capability.provider_type
        payload["idempotency_key"] = idempotency_key
        payload["timeout_ms"] = timeout_ms
        return payload
