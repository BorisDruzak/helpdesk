from __future__ import annotations

from typing import Any, Dict, List

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.providers.zabbix_provider import list_zabbix_capabilities


def list_server_connector_capabilities() -> List[CapabilityDescriptor]:
    return list_zabbix_capabilities()


class ServerConnectorProvider:
    """Server-side connector execution boundary.

    This intentionally does not call external systems yet. It validates that the
    capability reached the server connector route and returns a bounded provider
    response until a configured connector client is added.
    """

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        integration_key = capability.integration_key
        config = params.get("integration_config") or params.get("_integration_config")
        if capability.requires_integration and not config:
            return {
                "status": "error",
                "error_code": "INTEGRATION_NOT_CONFIGURED",
                "capability_id": capability.id,
                "message": f"Integration '{integration_key or 'unknown'}' is not configured",
            }
        credentials_ref = params.get("credentials_ref") or params.get("_credentials_ref")
        if capability.requires_credentials and not credentials_ref:
            return {
                "status": "error",
                "error_code": "CREDENTIALS_MISSING",
                "capability_id": capability.id,
                "message": f"Credentials for integration '{integration_key or 'unknown'}' are missing",
            }
        mapping = params.get("mapping") or params.get("_mapping")
        if capability.requires_mapping and not mapping:
            return {
                "status": "error",
                "error_code": "MAPPING_MISSING",
                "capability_id": capability.id,
                "message": f"Mapping '{capability.mapping_key or integration_key or capability.id}' is missing",
            }
        return {
            "status": "unavailable",
            "error_code": "CONNECTOR_CLIENT_NOT_CONFIGURED",
            "capability_id": capability.id,
            "provider_id": capability.provider_id,
            "integration_key": integration_key,
            "message": "Server connector route is active, but no external connector client is configured.",
            "evidence": capability.evidence,
        }
