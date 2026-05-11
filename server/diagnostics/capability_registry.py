from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.providers.server_connector import list_server_connector_capabilities
from diagnostics.providers.static_providers import list_static_capabilities


def _merge_tool_blocks(raw_tool: Dict[str, Any]) -> Dict[str, Any]:
    spec = raw_tool.get("spec") if isinstance(raw_tool.get("spec"), dict) else {}
    return {
        "execution": raw_tool.get("execution") or spec.get("execution") or {},
        "deployment": raw_tool.get("deployment") or spec.get("deployment") or {},
        "safety": raw_tool.get("safety") or spec.get("safety") or {},
        "readiness": raw_tool.get("readiness") or spec.get("readiness") or {},
        "evidence": raw_tool.get("evidence") or spec.get("evidence") or {"produces_evidence": False},
        "artifacts": raw_tool.get("artifacts") or spec.get("artifacts") or {},
        "spec": spec,
    }


def _descriptor_from_tool(raw_tool: Dict[str, Any], *, default_source: str) -> CapabilityDescriptor:
    blocks = _merge_tool_blocks(raw_tool)
    spec = blocks["spec"]
    execution = blocks["execution"]
    deployment = blocks["deployment"]
    safety = blocks["safety"]
    readiness = blocks["readiness"]
    metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else spec.get("metadata") or {}
    capability_id = str(raw_tool.get("tool") or raw_tool.get("tool_name") or "").strip()
    module_name = str(raw_tool.get("module") or raw_tool.get("module_name") or "").strip()
    provider_id = str(deployment.get("provider_id") or module_name or capability_id.split(".", 1)[0]).strip()
    execution_target = str(execution.get("target") or "agent_managed_module").strip()
    source = str(raw_tool.get("source") or default_source)
    if execution_target == "agent_builtin":
        provider_type = "agent_builtin"
    elif execution_target == "agent_managed_module":
        provider_type = "agent_managed_module"
    else:
        provider_type = execution_target
    return CapabilityDescriptor(
        id=capability_id,
        title=str(raw_tool.get("title") or spec.get("title") or spec.get("description") or capability_id),
        description=str(raw_tool.get("description") or spec.get("description") or ""),
        provider_id=provider_id,
        provider_type=provider_type,
        execution_target=execution_target,
        tool_kind=str(metadata.get("tool_kind") or raw_tool.get("tool_kind") or "diagnostic"),
        risk_level=str(raw_tool.get("risk_level") or spec.get("risk_level") or metadata.get("risk_level") or "low"),
        side_effects=bool(safety.get("side_effects", metadata.get("side_effects", False))),
        requires_consent=bool(safety.get("requires_consent", metadata.get("requires_consent", False))),
        requires_device=bool(execution.get("requires_device", False)),
        requires_agent_online=bool(execution.get("requires_agent_online", False)),
        supports_auto_install=bool(execution.get("supports_auto_install", False)),
        requires_integration=bool(execution.get("requires_integration", False)),
        integration_key=execution.get("integration_key"),
        requires_credentials=bool(readiness.get("requires_credentials", False)),
        requires_mapping=bool(readiness.get("requires_mapping", False)),
        requires_policy=bool(readiness.get("requires_policy", False)),
        required_permission=readiness.get("required_permission"),
        policy_key=readiness.get("policy_key"),
        mapping_key=readiness.get("mapping_key"),
        install_required_on_agent=bool(
            raw_tool.get("install_required", deployment.get("install_required_on_agent", False))
        ),
        platforms=list(metadata.get("platforms") or spec.get("platforms") or ["any"]),
        params_schema=dict(raw_tool.get("params_schema") or spec.get("params_schema") or {}),
        output_schema=dict(raw_tool.get("output_schema") or spec.get("output_schema") or {}),
        output_contract=dict(raw_tool.get("output_contract") or spec.get("output_contract") or {}),
        evidence=dict(blocks["evidence"] or {"produces_evidence": False}),
        artifacts=dict(blocks["artifacts"] or {}),
        aliases=list(raw_tool.get("aliases") or []),
        source=source,
    )


class CapabilityRegistry:
    def __init__(self, *, tool_service: Any = None, state: Any = None) -> None:
        self.tool_service = tool_service
        self.state = state

    async def list_capabilities(self, *, device_id: Optional[str] = None) -> List[CapabilityDescriptor]:
        capabilities: List[CapabilityDescriptor] = []
        if self.tool_service and device_id:
            device_tools = await self.tool_service.get_tools_list(device_id)
            capabilities.extend(self._project_tools(device_tools, default_source="builtin"))
        if self.tool_service:
            server_tools = await self.tool_service.get_tools_from_server(device_id)
            capabilities.extend(self._project_tools(server_tools, default_source="managed_module"))
        capabilities.extend(list_server_connector_capabilities())
        capabilities.extend(list_static_capabilities())
        return self._dedupe(capabilities)

    async def resolve_capability(
        self,
        capability_id: str,
        *,
        device_id: Optional[str] = None,
    ) -> Optional[CapabilityDescriptor]:
        for capability in await self.list_capabilities(device_id=device_id):
            if capability.id == capability_id or capability_id in capability.aliases:
                return capability
        return None

    def _project_tools(
        self,
        tools: Iterable[Dict[str, Any]],
        *,
        default_source: str,
    ) -> List[CapabilityDescriptor]:
        descriptors: List[CapabilityDescriptor] = []
        for raw_tool in tools or []:
            if not isinstance(raw_tool, dict):
                continue
            capability_id = raw_tool.get("tool") or raw_tool.get("tool_name")
            if not capability_id:
                continue
            descriptors.append(_descriptor_from_tool(raw_tool, default_source=default_source))
        return descriptors

    def _dedupe(self, capabilities: Iterable[CapabilityDescriptor]) -> List[CapabilityDescriptor]:
        by_id: Dict[str, CapabilityDescriptor] = {}
        for capability in capabilities:
            by_id.setdefault(capability.id, capability)
        return list(by_id.values())
