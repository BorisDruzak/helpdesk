from __future__ import annotations

from dataclasses import dataclass
import re
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
        if target == "agent_recipe":
            return self._agent_recipe_readiness(capability, context)
        if target in {"agent_builtin", "agent_managed_module"}:
            return self._agent_readiness(capability, context)
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

    def _agent_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> CapabilityReadiness:
        if not context.device_id:
            return self._status(
                capability,
                "unavailable",
                "Device is required",
                [],
                reason_code="DEVICE_REQUIRED",
            )
        if capability.execution_target == "agent_managed_module" and capability.install_required_on_agent:
            module_state = self._module_state(capability, context)
            if module_state in {"installing", "activating"}:
                return self._status(
                    capability,
                    "installing",
                    "Module installation is in progress",
                    [],
                    reason_code="MODULE_INSTALLING",
                )
            if module_state in {"failed", "missing"}:
                return self._status(
                    capability,
                    "missing_dependency",
                    "Module installation failed or is missing",
                    ["install"],
                    reason_code="MODULE_INSTALL_FAILED",
                )
            if module_state == "active":
                if capability.requires_consent:
                    return self._consent_required(capability)
                return self._status(capability, "available", None, ["run"])
            actions = ["install"]
            if capability.supports_auto_install:
                actions.append("run")
            return self._status(
                capability,
                "install_required",
                "Module is not installed on the device",
                actions,
                reason_code="MODULE_INSTALL_REQUIRED",
            )
        if capability.requires_consent:
            return self._consent_required(capability)
        return self._status(capability, "available", None, ["run"])

    def _agent_recipe_readiness(
        self,
        capability: CapabilityDescriptor,
        context: ReadinessContext,
    ) -> CapabilityReadiness:
        if not context.device_id:
            return self._status(
                capability,
                "unavailable",
                "Device is required",
                [],
                reason_code="DEVICE_REQUIRED",
            )
        if not self._platform_supported(capability, context.device_platform):
            return self._status(
                capability,
                "unsupported_platform",
                f"Recipe is not supported on platform '{context.device_platform}'",
                [],
                reason_code="PLATFORM_UNSUPPORTED",
            )
        if getattr(capability, "recipe_status", None) not in (None, "", "published", "active"):
            return self._status(
                capability,
                "recipe_not_published",
                "Recipe capability version is not published",
                [],
                reason_code="RECIPE_NOT_PUBLISHED",
            )

        runner_provider_id = capability.runner_provider_id or capability.provider_id or "agent_recipe_runner"
        installed_modules = context.installed_modules or {}
        runner_state = installed_modules.get(runner_provider_id)
        runner_version = self._module_version(runner_state)
        runner_active = self._module_active(runner_state)
        runner_state_name = self._module_state_name(runner_state)
        if runner_state_name in {"installing", "activating", "queued", "pending"}:
            return self._status(
                capability,
                "runner_installing",
                "Agent Recipe Runner installation is in progress",
                [],
                reason_code="RUNNER_INSTALLING",
            )
        if not runner_active or not runner_version:
            return self._status(
                capability,
                "runner_not_installed",
                "Agent Recipe Runner is not installed on the device",
                ["install_runner"],
                reason_code="RUNNER_NOT_INSTALLED",
            )
        min_runner_version = capability.min_runner_version or "0.0.0"
        if self._compare_versions(runner_version, min_runner_version) < 0:
            return self._status(
                capability,
                "runner_outdated",
                f"Agent Recipe Runner {runner_version} is below required {min_runner_version}",
                ["upgrade_runner"],
                reason_code="RUNNER_OUTDATED",
            )
        primitive_key = f"{runner_provider_id}:{capability.primitive_id}" if capability.primitive_id else None
        dependency_status = context.dependency_status or {}
        if primitive_key and dependency_status.get(primitive_key) is False:
            return self._status(
                capability,
                "primitive_not_supported",
                "Installed Agent Recipe Runner does not support the required primitive",
                ["upgrade_runner"],
                reason_code="PRIMITIVE_NOT_SUPPORTED",
            )
        if capability.requires_consent:
            return self._consent_required(capability)
        return self._status(capability, "available", None, ["run", "test"])

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

    def _module_state(self, capability: CapabilityDescriptor, context: ReadinessContext) -> Optional[str]:
        module_name = capability.provider_id
        installed_modules = context.installed_modules or {}
        desired_modules = context.desired_modules or {}
        raw_state = installed_modules.get(module_name)
        if isinstance(raw_state, dict):
            if raw_state.get("active") is True:
                return "active"
            state = str(raw_state.get("state") or "").strip().lower()
            if state:
                return state
        elif raw_state:
            return "active"
        desired = desired_modules.get(module_name)
        if isinstance(desired, dict):
            desired_state = str(desired.get("state") or "").strip().lower()
            if desired_state in {"installed", "installing", "queued", "pending", "requested", "reconciling"}:
                return "installing"
        elif desired:
            return "installing"
        return None

    def _module_version(self, raw_state: Any) -> Optional[str]:
        if isinstance(raw_state, dict):
            value = raw_state.get("version") or raw_state.get("active_version")
            return str(value).strip() if value else None
        return None

    def _module_active(self, raw_state: Any) -> bool:
        if isinstance(raw_state, dict):
            if raw_state.get("active") is True:
                return True
            return str(raw_state.get("state") or "").strip().lower() == "active"
        return bool(raw_state)

    def _module_state_name(self, raw_state: Any) -> Optional[str]:
        if isinstance(raw_state, dict):
            return str(raw_state.get("state") or "").strip().lower() or None
        return "active" if raw_state else None

    def _compare_versions(self, left: str, right: str) -> int:
        left_key = self._version_key(left)
        right_key = self._version_key(right)
        if left_key < right_key:
            return -1
        if left_key > right_key:
            return 1
        return 0

    def _version_key(self, value: str) -> tuple[int, ...]:
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
        if not match:
            return (0, 0, 0)
        return tuple(int(part) for part in match.groups())

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
