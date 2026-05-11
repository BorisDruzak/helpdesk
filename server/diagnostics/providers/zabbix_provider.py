from __future__ import annotations

from typing import List

from diagnostics.capability_models import CapabilityDescriptor


def list_zabbix_capabilities() -> List[CapabilityDescriptor]:
    common = {
        "provider_id": "zabbix_connector",
        "provider_type": "server_connector",
        "execution_target": "server_connector",
        "tool_kind": "diagnostic",
        "risk_level": "low",
        "requires_device": False,
        "requires_agent_online": False,
        "supports_auto_install": False,
        "requires_integration": True,
        "integration_key": "zabbix",
        "requires_credentials": True,
        "requires_mapping": True,
        "requires_policy": True,
        "required_permission": "monitoring.zabbix.view",
        "policy_key": "monitoring.zabbix.enabled",
        "mapping_key": "zabbix.host",
        "install_required_on_agent": False,
        "platforms": ["any"],
        "source": "server_connector",
        "evidence": {
            "produces_evidence": True,
            "kind": "monitoring.problem",
            "domain": "monitoring",
            "perspective": "monitoring",
            "passport_eligible": True,
        },
    }
    return [
        CapabilityDescriptor(
            id="zabbix.problems.lookup",
            title="Zabbix: active problems lookup",
            description="Placeholder capability for active Zabbix problem lookup.",
            **common,
        ),
        CapabilityDescriptor(
            id="zabbix.host.health",
            title="Zabbix: host health",
            description="Placeholder capability for host health lookup.",
            evidence={**common["evidence"], "kind": "monitoring.host_health"},
            **{key: value for key, value in common.items() if key != "evidence"},
        ),
        CapabilityDescriptor(
            id="zabbix.item.history",
            title="Zabbix: item history",
            description="Placeholder capability for Zabbix item history lookup.",
            evidence={**common["evidence"], "kind": "monitoring.metric_history"},
            **{key: value for key, value in common.items() if key != "evidence"},
        ),
    ]
