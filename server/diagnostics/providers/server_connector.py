from __future__ import annotations

from typing import Any, Dict, List

from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from diagnostics.providers.zabbix_provider import ZabbixProvider, list_zabbix_capabilities


def list_server_connector_capabilities() -> List[CapabilityDescriptor]:
    return list_zabbix_capabilities()


class ServerConnectorProvider:
    """Server-side connector execution boundary.

    This intentionally does not call external systems yet. It validates that the
    capability reached the server connector route and returns a bounded provider
    response until a configured connector client is added.
    """

    def __init__(self, *, zabbix_provider: ZabbixProvider | None = None) -> None:
        self.zabbix_provider = zabbix_provider or ZabbixProvider()

    def list_capabilities(self) -> List[CapabilityDescriptor]:
        return list_server_connector_capabilities()

    async def get_readiness(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        if capability.requires_integration and not (params.get("integration_config") or params.get("_integration_config")):
            return {"readiness": "integration_not_configured", "reason_code": "INTEGRATION_NOT_CONFIGURED"}
        if capability.requires_credentials and not (params.get("credentials_ref") or params.get("_credentials_ref")):
            return {"readiness": "credentials_missing", "reason_code": "CREDENTIALS_MISSING"}
        if capability.requires_mapping and not (params.get("mapping") or params.get("_mapping")):
            return {"readiness": "mapping_missing", "reason_code": "MAPPING_MISSING"}
        return {"readiness": "available", "reason_code": "AVAILABLE"}

    async def run_query(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
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
        if capability.provider_id == "zabbix_connector" or capability.integration_key == "zabbix":
            return await self.zabbix_provider.run_query(capability, **kwargs)
        return {
            "status": "unavailable",
            "error_code": "CONNECTOR_CLIENT_NOT_CONFIGURED",
            "capability_id": capability.id,
            "provider_id": capability.provider_id,
            "integration_key": integration_key,
            "message": "Server connector route is active, but no external connector client is configured.",
            "evidence": capability.evidence,
        }

    def normalize_result(self, capability: CapabilityDescriptor, result: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        payload = dict(result or {})
        payload.setdefault("capability_id", capability.id)
        payload.setdefault("provider_id", capability.provider_id)
        payload.setdefault("integration_key", capability.integration_key)
        payload.setdefault("evidence", capability.evidence)
        return payload

    def map_evidence(self, capability: CapabilityDescriptor, result: Dict[str, Any], **kwargs: Any) -> Dict[str, Any] | None:
        if result.get("evidence_preview"):
            return result["evidence_preview"]
        if not (capability.evidence or {}).get("produces_evidence"):
            return None
        return normalize_tool_result_to_evidence_stub(
            {"operation_id": f"server_connector:{capability.id}", "status": result.get("status") or "unknown"},
            capability,
            result,
        ).to_dict()

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        result = await self.run_query(capability, **kwargs)
        normalized = self.normalize_result(capability, result, **kwargs)
        evidence_preview = self.map_evidence(capability, normalized, **kwargs)
        if evidence_preview is not None:
            normalized["evidence_preview"] = evidence_preview
        return normalized
