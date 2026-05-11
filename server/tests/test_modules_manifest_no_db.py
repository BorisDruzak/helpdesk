import io
import json
import subprocess
import zipfile
from unittest.mock import patch

import pytest

from modules.handlers import _run_module_smoke
from utils.module_builder import build_module_package
from utils.module_manifest import normalize_manifest
from utils.module_preflight import preflight_module_zip


@pytest.mark.no_db
def test_normalize_manifest_keeps_semantic_tool_name_and_legacy_alias():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "network_basic",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "core",
            "tools": [
                {
                    "canonical_name": "dns.resolve",
                    "aliases": ["resolve_dns"],
                    "method": "resolve_impl",
                    "contract_version": "1.0.0",
                    "dependencies": {
                        "min_agent_version": "1.0.0",
                        "required_binaries": [],
                        "required_python_packages": [],
                        "required_services": [],
                        "required_permissions": [],
                    },
                    "lifecycle": "stable",
                    "error_codes": ["DNS_NXDOMAIN"],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "output_schema": {"type": "object"},
                    "metadata": {
                        "domain": "network",
                        "platforms": ["linux", "win32"],
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "timeout_sec": 15,
                        "idempotent": True,
                    },
                }
            ],
        }
    )
    assert not validation["errors"]["tools"]
    assert normalized is not None
    tool = normalized["tools"][0]
    assert tool["tool"] == "dns.resolve"
    assert "network_basic.resolve" in tool["aliases"]
    assert "network_basic.resolve_dns" in tool["aliases"]
    assert tool["output_schema"]["type"] == "object"
    assert tool["contract_version"] == "1.0.0"
    assert tool["metadata"]["risk_level"] == "safe_read"


@pytest.mark.no_db
def test_normalize_manifest_defaults_old_tool_to_agent_managed_capability():
    normalized, validation, summary = normalize_manifest(
        {
            "module_name": "network_tools",
            "module_version": "1.0.0",
            "tools": [{"name": "http_request", "description": "HTTP request from endpoint"}],
        }
    )

    assert normalized is not None
    assert not validation["errors"]["tools"]
    tool = normalized["tools"][0]
    assert tool["execution"] == {
        "target": "agent_managed_module",
        "requires_device": True,
        "requires_agent_online": True,
        "supports_auto_install": True,
        "requires_integration": False,
    }
    assert tool["deployment"] == {
        "provider_id": "network_tools",
        "install_required_on_agent": True,
        "package_type": "zip",
    }
    assert tool["readiness"] == {
        "requires_credentials": False,
        "requires_mapping": False,
        "requires_policy": False,
    }
    assert tool["evidence"] == {"produces_evidence": False}
    assert summary["tools"][0]["execution"]["target"] == "agent_managed_module"


@pytest.mark.no_db
def test_normalize_manifest_validates_execution_deployment_evidence_and_safety_blocks():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "zabbix_connector",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "core",
            "tools": [
                {
                    "tool": "zabbix.problems.lookup",
                    "method": "lookup_problems",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": [],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "execution": {
                        "target": "server_connector",
                        "requires_device": False,
                        "requires_agent_online": False,
                        "supports_auto_install": False,
                        "requires_integration": True,
                        "integration_key": "zabbix",
                    },
                    "deployment": {
                        "provider_id": "zabbix_connector",
                        "install_required_on_agent": False,
                        "package_type": "server_connector",
                    },
                    "readiness": {
                        "requires_credentials": True,
                        "requires_mapping": True,
                        "requires_policy": True,
                        "required_permission": "monitoring.zabbix.view",
                        "policy_key": "monitoring.zabbix.enabled",
                        "mapping_key": "zabbix.host",
                    },
                    "safety": {"side_effects": False, "requires_consent": False, "idempotent": True},
                    "evidence": {
                        "produces_evidence": True,
                        "kind": "monitoring.problem",
                        "domain": "monitoring",
                        "perspective": "monitoring",
                        "passport_eligible": True,
                    },
                }
            ],
        }
    )

    assert normalized is not None
    assert not validation["errors"]["tools"]
    tool = normalized["tools"][0]
    assert tool["execution"]["target"] == "server_connector"
    assert tool["execution"]["integration_key"] == "zabbix"
    assert tool["deployment"]["install_required_on_agent"] is False
    assert tool["readiness"] == {
        "requires_credentials": True,
        "requires_mapping": True,
        "requires_policy": True,
        "required_permission": "monitoring.zabbix.view",
        "policy_key": "monitoring.zabbix.enabled",
        "mapping_key": "zabbix.host",
    }
    assert tool["safety"] == {"side_effects": False, "requires_consent": False, "idempotent": True}
    assert tool["evidence"]["kind"] == "monitoring.problem"


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("tool_patch", "expected_message"),
    [
        ({"execution": {"target": "bad_target"}}, "execution.target"),
        (
            {
                "execution": {"target": "server_connector", "requires_integration": True},
                "deployment": {"install_required_on_agent": False},
            },
            "integration_key",
        ),
        (
            {
                "execution": {"target": "agent_builtin"},
                "deployment": {"install_required_on_agent": True},
            },
            "agent_builtin",
        ),
        ({"evidence": {"produces_evidence": True, "kind": "logs.bundle"}}, "evidence.domain"),
        ({"safety": {"side_effects": "no"}}, "safety.side_effects"),
        ({"readiness": {"requires_credentials": "yes"}}, "readiness.requires_credentials"),
        ({"readiness": {"required_permission": ""}}, "readiness.required_permission"),
    ],
)
def test_normalize_manifest_rejects_invalid_capability_contract_blocks(tool_patch, expected_message):
    tool = {
        "tool": "vendor_x.capability",
        "method": "run",
        "contract_version": "1.0.0",
        "dependencies": {"min_agent_version": "1.0.0"},
        "lifecycle": "stable",
        "error_codes": [],
        "artifact_types": [],
        "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
        "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
    }
    tool.update(tool_patch)

    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "vendor_capabilities",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "vendor",
            "tools": [tool],
        }
    )

    assert normalized is None
    assert any(expected_message in error for error in validation["errors"]["tools"])


@pytest.mark.no_db
def test_normalize_manifest_keeps_playbook_output_contract():
    normalized, validation, summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "network_basic",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "core",
            "tools": [
                {
                    "tool": "network.ping",
                    "method": "ping_host",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": ["HOST_UNREACHABLE"],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "output_schema": {"type": "object", "properties": {"reachable": {"type": "boolean"}}},
                    "output_contract": {
                        "status_path": "result.status",
                        "status_values": ["ok", "error"],
                        "success_values": ["ok"],
                        "error_values": ["error"],
                        "summary_path": "result.output.summary",
                        "error_code_path": "result.error.code",
                        "compact_fields": [
                            {"path": "result.output.reachable", "label": "Reachable", "type": "boolean"}
                        ],
                    },
                    "metadata": {
                        "domain": "network",
                        "platforms": ["linux", "win32"],
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "idempotent": True,
                    },
                }
            ],
        }
    )

    assert normalized is not None
    assert not validation["errors"]["tools"]
    tool = normalized["tools"][0]
    assert tool["output_contract"]["status_values"] == ["ok", "error"]
    assert tool["output_contract"]["success_values"] == ["ok"]
    assert tool["output_contract"]["error_values"] == ["error"]
    assert tool["output_contract"]["summary_path"] == "result.output.summary"
    assert summary is not None
    assert summary["tools"][0]["output_contract"]["status_path"] == "result.status"


@pytest.mark.no_db
def test_normalize_manifest_rejects_ambiguous_output_contract_statuses():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "network_basic",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "core",
            "tools": [
                {
                    "tool": "network.ping",
                    "method": "ping_host",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": [],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "output_contract": {"status_values": ["ok", "ok"]},
                }
            ],
        }
    )

    assert normalized is None
    assert any("output_contract.status_values" in error for error in validation["errors"]["tools"])


@pytest.mark.no_db
def test_normalize_manifest_rejects_duplicate_tool_alias_conflicts():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "network_basic",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "core",
            "tools": [
                {
                    "tool": "dns.resolve",
                    "method": "resolve_dns",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": [],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "aliases": ["shared.alias"],
                },
                {
                    "tool": "network.ping",
                    "method": "ping_host",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": [],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                    "aliases": ["shared.alias", "dns.resolve"],
                },
            ],
        }
    )

    assert normalized is None
    assert any("shared.alias" in error for error in validation["errors"]["tools"])
    assert any("dns.resolve" in error and "conflicts" in error for error in validation["errors"]["tools"])


@pytest.mark.no_db
def test_normalize_manifest_rejects_reserved_namespace_for_vendor_scope():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "vendor_netkit",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "vendor",
            "tools": [
                {
                    "tool": "dns.resolve",
                    "method": "resolve_dns",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": [],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                }
            ],
        }
    )

    assert normalized is None
    assert any("reserved namespace" in error for error in validation["errors"]["tools"])


@pytest.mark.no_db
def test_normalize_manifest_allows_vendor_namespace_for_vendor_scope():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "vendor_netkit",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "vendor",
            "tools": [
                {
                    "tool": "vendor_x.resolve",
                    "method": "resolve_dns",
                    "contract_version": "1.0.0",
                    "dependencies": {"min_agent_version": "1.0.0"},
                    "lifecycle": "stable",
                    "error_codes": ["VALIDATION_ERROR"],
                    "artifact_types": [],
                    "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                    "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                }
            ],
        }
    )

    assert normalized is not None
    assert not validation["errors"]["tools"]


@pytest.mark.no_db
def test_normalize_manifest_requires_contract_redaction_resources_and_dependencies():
    normalized, validation, _summary = normalize_manifest(
        {
            "manifest_version": 2,
            "module_name": "vendor_echo",
            "module_version": "1.0.0",
            "module_api_version": "1.0.0",
            "owner_scope": "vendor",
            "tools": [
                {
                    "tool": "vendor.echo",
                    "method": "run",
                }
            ],
        }
    )

    assert normalized is None
    joined = "\n".join(validation["errors"]["tools"])
    assert "contract_version" in joined
    assert "dependencies" in joined
    assert "redaction" in joined
    assert "resources" in joined


@pytest.mark.no_db
def test_build_module_package_supports_multi_tool_semantic_names():
    zip_bytes, summary = build_module_package(
        module_name="network_basic",
        version="1.0.0",
        tool_name="",
        description="Network diagnostics",
        user_function_body="",
        platforms=["linux", "win32"],
        tools=[
            {
                "tool_name": "dns.resolve",
                "method_name": "resolve_dns",
                "description": "Resolve DNS",
                "params_schema": [{"name": "hostname", "type": "string", "required": True}],
                "metadata": {"domain": "dns", "platforms": ["linux", "win32"], "idempotent": True},
                "user_function_body": 'return {"ok": True, "best_ip": "127.0.0.1"}',
            },
            {
                "tool_name": "network.ping",
                "aliases": ["ping.host"],
                "method_name": "ping_host",
                "description": "Ping target",
                "params_schema": [{"name": "target", "type": "string", "required": True}],
                "metadata": {"domain": "network", "platforms": ["linux", "win32"], "idempotent": True},
                "user_function_body": 'return {"ok": True, "reachable": True}',
            },
        ],
    )

    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)

    assert ok is True
    assert manifest_json is not None
    assert [tool["tool"] for tool in manifest_json["tools"]] == ["dns.resolve", "network.ping"]
    assert "network_basic.ping" in manifest_json["tools"][1]["aliases"]
    assert "ping.host" in manifest_json["tools"][1]["aliases"]
    assert manifest_summary == summary
    assert validation_json["validation_status"] == "passed"


@pytest.mark.no_db
def test_build_module_package_includes_output_contract_for_playbook_builder():
    zip_bytes, summary = build_module_package(
        module_name="vendor_netkit",
        version="1.0.0",
        tool_name="",
        description="Network tools",
        user_function_body="",
        platforms=["any"],
        owner_scope="vendor",
        tools=[
            {
                "tool_name": "vendor_x.echo",
                "method_name": "echo_tool",
                "description": "Echo value",
                "params_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                "output_schema": {
                    "type": "object",
                    "properties": {"status": {"type": "string", "enum": ["ok", "error"]}},
                },
                "output_contract": {
                    "status_path": "result.status",
                    "status_values": ["ok", "error"],
                    "success_values": ["ok"],
                    "error_values": ["error"],
                    "summary_path": "result.output.value",
                    "error_code_path": "result.error.code",
                },
                "metadata": {"domain": "vendor_x", "platforms": ["any"], "risk_level": "safe_read"},
                "user_function_body": 'return {"status": "ok", "value": params.get("value")}',
            }
        ],
    )

    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)

    assert ok is True
    assert manifest_json is not None
    assert manifest_json["tools"][0]["output_contract"]["status_values"] == ["ok", "error"]
    assert summary["tools"][0]["output_contract"]["summary_path"] == "result.output.value"
    assert manifest_summary["tools"][0]["output_contract"]["status_path"] == "result.status"
    assert validation_json["validation_status"] == "passed"


@pytest.mark.no_db
def test_preflight_module_zip_rejects_missing_observer_breadcrumbs():
    module_name = "observer_missing"
    manifest = {
        "manifest_version": 2,
        "module_name": module_name,
        "module_version": "1.0.0",
        "module_api_version": "1.0.0",
        "entrypoint": "module:register",
        "owner_scope": "vendor",
        "platforms": ["any"],
        "tools": [
            {
                "tool": "vendor_x.echo",
                "method": "echo_tool",
                "description": "Echo",
                "contract_version": "1.0.0",
                "dependencies": {"min_agent_version": "1.0.0"},
                "lifecycle": "stable",
                "error_codes": [],
                "artifact_types": [],
                "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "metadata": {
                    "risk_level": "safe_read",
                    "requires_consent": False,
                    "platforms": ["any"],
                    "allow_roles": ["admin"],
                },
            }
        ],
    }
    module_py = """
from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


class ExampleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "observer_missing"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(name="vendor_x.echo", description="Echo", risk_level="safe_readonly")
    async def echo_tool(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True}


def register():
    return ExampleCollector()
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("module.py", module_py)

    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(buf.getvalue())

    assert ok is False
    assert manifest_json is None
    assert manifest_summary is None
    assert any("tool.entry" in error for error in validation_json["errors"]["tools"])


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_run_module_smoke_falls_back_to_blocking_subprocess_when_asyncio_subprocess_is_unavailable():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({"module_name": "fallback_demo"}))

    completed = subprocess.CompletedProcess(
        args=["python", "smoke_check_module.py"],
        returncode=0,
        stdout=b'{"status":"ok","tools_checked":1}',
        stderr=b"",
    )

    with (
        patch("modules.handlers.asyncio.create_subprocess_exec", side_effect=NotImplementedError),
        patch("modules.handlers.subprocess.run", return_value=completed) as subprocess_run,
    ):
        ok, smoke_result, smoke_errors = await _run_module_smoke(zip_buffer.getvalue(), "pc_smoke_fallback_")

    assert ok is True
    assert smoke_errors == []
    assert smoke_result == {"status": "ok", "tools_checked": 1}
    subprocess_run.assert_called_once()
