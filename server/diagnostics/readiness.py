from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from diagnostics.capability_models import CapabilityDescriptor, CapabilityReadiness
from domain_ports.endpoint import (
    EndpointAvailability,
    EndpointCapabilitiesProjection,
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointNotFound,
    EndpointUnavailable,
)


@dataclass(frozen=True)
class ReadinessContext:
    ticket_id: Optional[str] = None
    device_id: Optional[str] = None
    actor: Any = None
    device_platform: Optional[str] = None
    installed_modules: Dict[str, Any] | None = None
    desired_modules: Dict[str, Any] | None = None
    dependency_status: Dict[str, Any] | None = None
    integration_configs: Dict[str, Any] | None = None
    credential_keys: Dict[str, Any] | None = None
    mappings: Dict[str, Any] | None = None
    policy_flags: Dict[str, Any] | None = None
    permissions: set[str] | list[str] | tuple[str, ...] | None = None
    has_root_trace: Optional[bool] = None
    has_permission: Optional[bool] = True
    endpoint_execution_mode: Optional[str] = None
    endpoint_port: Any = None
    endpoint_device_ref: Optional[str] = None


class CapabilityReadinessService:
    def __init__(self, *, state: Any = None) -> None:
        self.state = state

    async def get_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> CapabilityReadiness:
        target = capability.execution_target
        common = self._common_readiness(capability, context)
        if common is not None:
            return common
        if target in {"agent_recipe", "agent_builtin", "agent_managed_module"}:
            return self._status(
                capability,
                "unavailable",
                "Helpdesk no longer owns agent capability execution.",
                [],
                reason_code="ENDPOINT_ONLY_CAPABILITY_REQUIRED",
            )
        if target == "server_builtin":
            if capability.requires_consent:
                return self._consent_required(capability)
            return self._status(capability, "available", None, ["run"])
        if target == "server_connector":
            return self._server_connector_readiness(capability, context)
        if target == "observer_query":
            if context.has_root_trace is False:
                return self._status(
                    capability,
                    "unavailable",
                    "Ticket has no observer root trace",
                    [],
                    reason_code="OBSERVER_TRACE_MISSING",
                )
            return self._status(capability, "available", None, ["run"])
        if target == "manual":
            return self._status(capability, "available", None, ["create_manual_evidence"])
        if target == "endpoint_operation":
            return await self._endpoint_operation_readiness(capability, context)
        return self._status(capability, "unknown", "Capability target is reserved but not implemented", [])

    async def _endpoint_operation_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> CapabilityReadiness:
        if str(context.endpoint_execution_mode or "endpoint").strip().lower() != "endpoint":
            return self._status(
                capability,
                "disabled_by_policy",
                "Endpoint diagnostic cutover is disabled by policy",
                [],
                reason_code="ENDPOINT_DIAGNOSTIC_MODE_DISABLED",
            )
        # A Helpdesk legacy device id is not an Endpoint reference.  Fail
        # before touching the port so no legacy identifier can cross domains.
        if not context.endpoint_device_ref:
            return self._status(
                capability,
                "mapping_missing",
                "Ticket has no Endpoint device mapping",
                [],
                reason_code="ENDPOINT_DEVICE_MAPPING_MISSING",
            )
        try:
            device = EndpointDeviceRef(external_id=context.endpoint_device_ref)
        except ValueError:
            return self._status(
                capability,
                "mapping_missing",
                "Ticket Endpoint device mapping is invalid",
                [],
                reason_code="ENDPOINT_DEVICE_MAPPING_MISSING",
            )
        if context.endpoint_port is None:
            return self._status(
                capability,
                "integration_not_configured",
                "Endpoint integration is not configured",
                [],
                reason_code="ENDPOINT_INTEGRATION_NOT_CONFIGURED",
            )
        availability = await context.endpoint_port.availability()
        if isinstance(availability, EndpointUnavailable) or not isinstance(availability, EndpointAvailability):
            return self._status(
                capability,
                "integration_not_configured",
                "Endpoint integration is unavailable",
                [],
                reason_code="ENDPOINT_INTEGRATION_NOT_CONFIGURED",
            )
        if availability.status != "available":
            return self._status(
                capability,
                "unavailable",
                "Endpoint integration is temporarily unavailable",
                [],
                reason_code="ENDPOINT_TEMPORARILY_UNAVAILABLE",
            )
        device_outcome = await context.endpoint_port.read_device(device)
        if isinstance(device_outcome, EndpointUnavailable):
            return self._status(
                capability,
                "unavailable",
                "Endpoint device read is temporarily unavailable",
                [],
                reason_code="ENDPOINT_TEMPORARILY_UNAVAILABLE",
            )
        if isinstance(device_outcome, EndpointNotFound) or not isinstance(device_outcome, EndpointDeviceProjection):
            return self._status(
                capability,
                "mapping_missing",
                "Ticket Endpoint device mapping is missing",
                [],
                reason_code="ENDPOINT_DEVICE_MAPPING_MISSING",
            )
        capabilities = await context.endpoint_port.list_capabilities(device)
        if not isinstance(capabilities, EndpointCapabilitiesProjection):
            return self._status(
                capability,
                "unavailable",
                "Endpoint capabilities are temporarily unavailable",
                [],
                reason_code="ENDPOINT_TEMPORARILY_UNAVAILABLE",
            )
        if not any(item.capability == "context.diagnostic.collect" and item.available for item in capabilities.items):
            return self._status(
                capability,
                "unavailable",
                "Endpoint diagnostic collection is unavailable for the device",
                [],
                reason_code="ENDPOINT_DIAGNOSTIC_CAPABILITY_UNAVAILABLE",
            )
        return self._status(capability, "available", None, ["run"])

    def _common_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> Optional[CapabilityReadiness]:
        if context.has_permission is False:
            return self._status(
                capability,
                "permission_denied",
                "Operator lacks permission",
                [],
                reason_code="PERMISSION_DENIED",
            )
        if capability.required_permission:
            permissions = set(context.permissions or [])
            if context.permissions is not None and capability.required_permission not in permissions:
                return self._status(
                    capability,
                    "permission_denied",
                    "Operator lacks required permission",
                    [],
                    reason_code="PERMISSION_DENIED",
                )
        if capability.requires_policy:
            policy_key = capability.policy_key or capability.id
            policy_flags = context.policy_flags or {}
            if policy_key in policy_flags and not bool(policy_flags.get(policy_key)):
                return self._status(
                    capability,
                    "disabled_by_policy",
                    "Policy disables capability",
                    [],
                    reason_code="POLICY_DISABLED",
                )
        if not self._platform_supported(capability, context.device_platform):
            return self._status(
                capability,
                "unsupported_platform",
                f"Capability is not supported on platform '{context.device_platform}'",
                [],
                reason_code="PLATFORM_UNSUPPORTED",
            )
        dependency_status = context.dependency_status or {}
        dep_value = dependency_status.get(capability.id, dependency_status.get(capability.provider_id))
        dependency_readiness = self._dependency_readiness(capability, dep_value)
        if dependency_readiness is not None:
            return dependency_readiness
        return None

    def _server_connector_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> CapabilityReadiness:
        integration_key = capability.integration_key
        configs = context.integration_configs or {}
        credentials = context.credential_keys or {}
        mappings = context.mappings or {}
        if capability.requires_integration and (not integration_key or integration_key not in configs):
            return self._status(
                capability,
                "integration_not_configured",
                "Required integration is not configured",
                ["configure_integration"],
                reason_code="INTEGRATION_NOT_CONFIGURED",
            )
        if capability.requires_credentials and integration_key and credentials.get(integration_key) is not True:
            return self._status(
                capability,
                "credentials_missing",
                "Integration credentials are missing",
                ["add_credentials"],
                reason_code="CREDENTIALS_MISSING",
            )
        if capability.requires_mapping:
            mapping_key = capability.mapping_key or integration_key
            if mapping_key and mapping_key not in mappings:
                return self._status(
                    capability,
                    "mapping_missing",
                    "Required integration mapping is missing",
                    ["configure_integration"],
                    reason_code="MAPPING_MISSING",
                )
        if capability.requires_consent:
            return self._consent_required(capability)
        return self._status(capability, "available", None, ["run"])

    def _consent_required(self, capability: CapabilityDescriptor) -> CapabilityReadiness:
        return self._status(
            capability,
            "consent_required",
            "User consent is required",
            ["request_consent"],
            reason_code="CONSENT_REQUIRED",
        )

    def _dependency_readiness(
        self,
        capability: CapabilityDescriptor,
        dep_value: Any,
    ) -> Optional[CapabilityReadiness]:
        if dep_value is None or dep_value is True:
            return None
        if dep_value is False:
            return self._status(
                capability,
                "missing_dependency",
                "Capability dependency is missing",
                [],
                reason_code="DEPENDENCY_MISSING",
            )
        if isinstance(dep_value, dict):
            raw_status = str(dep_value.get("status") or dep_value.get("state") or "").strip().lower()
            if raw_status in {"ok", "ready", "available", "passed", "success"}:
                return None
            if raw_status in {"installing", "pending", "queued", "checking"}:
                return self._status(
                    capability,
                    "installing",
                    str(dep_value.get("reason") or "Capability dependency check is in progress"),
                    [],
                    reason_code=str(dep_value.get("reason_code") or "DEPENDENCY_CHECKING"),
                )
            reason = str(dep_value.get("reason") or "Capability dependency is missing")
            reason_code = str(dep_value.get("reason_code") or "DEPENDENCY_MISSING")
            return self._status(capability, "missing_dependency", reason, [], reason_code=reason_code)
        return self._status(
            capability,
            "missing_dependency",
            "Capability dependency is missing",
            [],
            reason_code="DEPENDENCY_MISSING",
        )

    def _platform_supported(self, capability: CapabilityDescriptor, device_platform: Optional[str]) -> bool:
        platforms = [str(item).strip().lower() for item in (capability.platforms or ["any"]) if str(item).strip()]
        if not platforms or "any" in platforms or not device_platform:
            return True
        platform = str(device_platform).strip().lower()
        aliases = {
            "windows": "win32",
            "win": "win32",
            "macos": "darwin",
            "mac": "darwin",
        }
        platform = aliases.get(platform, platform)
        return platform in platforms

    def _status(
        self,
        capability: CapabilityDescriptor,
        readiness: str,
        reason: Optional[str],
        actions: list[str],
        *,
        reason_code: Optional[str] = None,
    ) -> CapabilityReadiness:
        return CapabilityReadiness(
            capability_id=capability.id,
            title=capability.title,
            execution_target=capability.execution_target,
            readiness=readiness,
            reason=reason,
            reason_code=reason_code or readiness.upper(),
            actions=actions,
            evidence=capability.evidence,
            risk_level=capability.risk_level,
            requires_consent=capability.requires_consent,
        )
