import pytest

from playbooks.catalog import (
    DIAGNOSTIC_MODULE_CATALOG,
    normalize_playbook_draft,
)
from playbooks.tool_catalog import (
    build_required_tools_manifest,
    expand_preset_params,
    normalize_tool_catalog_entry,
)
from playbooks.form_triggers import (
    build_ticket_playbook_context,
    collect_ticket_created_playbook_triggers,
)
from tickets.form_catalog import (
    build_form_custom_fields,
    validate_form_pack_schema,
    validate_form_submission,
)


@pytest.mark.no_db
def test_diagnostic_module_catalog_contains_only_diagnostic_blocks():
    tool_ids = {item["tool"] for item in DIAGNOSTIC_MODULE_CATALOG}

    assert {"system.collect", "ip_address.get_ip", "diag.logs.collect"} <= tool_ids
    assert all(item["module_kind"] == "diagnostic" for item in DIAGNOSTIC_MODULE_CATALOG)
    assert all(item["changes_device"] is False for item in DIAGNOSTIC_MODULE_CATALOG)


@pytest.mark.no_db
def test_normalize_playbook_draft_rejects_remediation_without_confirmation_policy():
    with pytest.raises(ValueError, match="remediation"):
        normalize_playbook_draft(
            {
                "key": "restart_network",
                "name": "Restart network",
                "domain": "network",
                "blocks": [
                    {
                        "id": "restart",
                        "type": "remediate",
                        "module_kind": "remediation",
                        "tool": "service.restart",
                        "params": {"service": "network"},
                    }
                ],
            }
        )


@pytest.mark.no_db
def test_normalize_playbook_draft_keeps_reorderable_conditions_and_report_steps():
    normalized = normalize_playbook_draft(
        {
            "key": "site_not_opening",
            "name": "Site is not opening",
            "domain": "network",
            "blocks": [
                {
                    "id": "collect_identity",
                    "type": "diagnostic",
                    "module_kind": "diagnostic",
                    "tool": "system.collect",
                    "params": {"preset": "network"},
                },
                {
                    "id": "branch",
                    "type": "decision",
                    "module_kind": "diagnostic",
                    "condition": "steps.collect_identity.status == 'success'",
                    "params": {"default": "continue"},
                },
                {
                    "id": "facts",
                    "type": "report",
                    "module_kind": "diagnostic",
                    "params": {"title": "Network evidence package"},
                },
            ],
        }
    )

    assert normalized["playbook"]["key"] == "site_not_opening"
    assert [step["step_key"] for step in normalized["steps"]] == [
        "collect_identity",
        "branch",
        "facts",
    ]
    assert normalized["steps"][0]["type"] == "collect"
    assert normalized["steps"][1]["if_expr"] == "steps.collect_identity.status == 'success'"
    assert normalized["steps"][2]["type"] == "report"


@pytest.mark.no_db
def test_tool_catalog_expands_presets_into_concrete_params():
    tool = normalize_tool_catalog_entry(
        {
            "tool": "system.collect",
            "module": "system",
            "description": "System snapshot",
            "spec": {
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "preset": {"type": "string", "default": "basic"},
                        "include_ip": {"type": "boolean", "default": False},
                    },
                },
                "presets": [
                    {
                        "id": "network",
                        "name": "Network",
                        "params": {"preset": "network", "include_ip": True},
                    }
                ],
                "metadata": {
                    "platforms": ["any"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                },
            },
            "install_required": False,
        },
        source="builtin",
    )

    params = expand_preset_params(tool, preset_id="network", overrides={"include_ip": False})

    assert params == {"preset": "network", "include_ip": False}


@pytest.mark.no_db
def test_tool_catalog_exposes_predictable_output_contract_and_condition_hints():
    tool = normalize_tool_catalog_entry(
        {
            "tool": "network.ping",
            "module": "network_basic",
            "description": "Ping target",
            "spec": {
                "params_schema": {},
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
                "metadata": {"platforms": ["linux", "win32"], "risk_level": "safe_read"},
                "dependencies": {"min_agent_version": "3.1.0"},
                "error_codes": ["HOST_UNREACHABLE"],
            },
            "install_required": True,
        },
        source="server",
    )

    assert tool["output_contract"]["status_values"] == ["ok", "error"]
    assert tool["condition_hints"]["status_path"] == "result.status"
    assert tool["condition_hints"]["status_values"] == ["ok", "error"]
    assert tool["condition_hints"]["error_codes"] == ["HOST_UNREACHABLE"]
    assert tool["condition_hints"]["condition_templates"][0] == {
        "label": "status == ok",
        "expression": "{step}.output.result.status == 'ok'",
    }


@pytest.mark.no_db
def test_normalize_playbook_draft_writes_manifest_v2_required_tools_and_install_policy():
    catalog_entry = normalize_tool_catalog_entry(
        {
            "tool": "ip_address.get_ip",
            "module": "ip_address",
            "description": "IP address",
            "spec": {
                "params_schema": {},
                "output_schema": {"type": "object", "properties": {"ip": {"type": "string"}}},
                "output_contract": {
                    "status_path": "result.status",
                    "status_values": ["ok", "error"],
                    "success_values": ["ok"],
                    "error_values": ["error"],
                    "summary_path": "result.output.summary",
                },
                "presets": [],
                "metadata": {
                    "platforms": ["linux", "win32"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                },
                "dependencies": {"min_agent_version": "3.1.0"},
                "error_codes": ["NETWORK_UNAVAILABLE"],
            },
            "install_required": True,
        },
        source="server",
    )
    normalized = normalize_playbook_draft(
        {
            "key": "internet_not_working",
            "name": "Internet is not working",
            "blocks": [
                {
                    "id": "get_ip",
                    "type": "diagnostic",
                    "module_kind": "diagnostic",
                    "tool": "ip_address.get_ip",
                    "label": "IP address",
                    "params": {},
                    "install_policy": "lazy",
                    "tool_manifest": catalog_entry,
                }
            ],
        }
    )

    assert normalized["manifest"]["schema"] == "pc_client.playbook.self_healing.v2"
    assert normalized["manifest"]["blocks"][0]["install_policy"] == "lazy"
    assert normalized["manifest"]["required_tools"] == [
        build_required_tools_manifest([normalized["manifest"]["blocks"][0]], {"ip_address.get_ip": catalog_entry})[0]
    ]
    assert normalized["manifest"]["required_tools"][0]["module_name"] == "ip_address"
    assert normalized["manifest"]["required_tools"][0]["min_agent_version"] == "3.1.0"
    assert normalized["manifest"]["required_tools"][0]["output_contract"]["status_values"] == ["ok", "error"]
    assert normalized["manifest"]["required_tools"][0]["condition_hints"]["status_path"] == "result.status"


@pytest.mark.no_db
def test_normalize_playbook_draft_accepts_capability_id_for_non_agent_steps():
    normalized = normalize_playbook_draft(
        {
            "key": "server_side_http",
            "name": "Server-side HTTP check",
            "blocks": [
                {
                    "id": "server_http",
                    "type": "diagnostic",
                    "module_kind": "diagnostic",
                    "capability_id": "server.http.request",
                    "label": "Server HTTP request",
                    "params": {"url": "https://example.test"},
                    "tool_manifest": {
                        "id": "server.http.request",
                        "capability_id": "server.http.request",
                        "label": "Server HTTP request",
                        "execution_target": "server_builtin",
                        "provider_id": "server_builtin",
                        "params_schema": {
                            "type": "object",
                            "required": ["url"],
                            "properties": {"url": {"type": "string"}},
                        },
                        "output_contract": {
                            "status_path": "status",
                            "status_values": ["success", "error"],
                            "success_values": ["success"],
                            "error_values": ["error"],
                        },
                        "evidence": {
                            "produces_evidence": True,
                            "kind": "network.http",
                            "domain": "network",
                            "perspective": "server",
                        },
                    },
                }
            ],
        }
    )

    block = normalized["manifest"]["blocks"][0]
    assert normalized["steps"][0]["tool"] == "server.http.request"
    assert block["tool"] == "server.http.request"
    assert block["capability_id"] == "server.http.request"
    assert block["execution_target"] == "server_builtin"
    assert normalized["manifest"]["required_capabilities"] == [
        {
            "capability_id": "server.http.request",
            "execution_target": "server_builtin",
            "provider_id": "server_builtin",
            "install_required": False,
            "install_policy": "server",
            "requires_consent": False,
            "params_schema": {
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string"}},
            },
            "output_schema": {},
            "output_contract": {
                "status_path": "status",
                "status_values": ["success", "error"],
                "success_values": ["success"],
                "error_values": ["error"],
            },
            "condition_hints": {},
            "evidence": {
                "produces_evidence": True,
                "kind": "network.http",
                "domain": "network",
                "perspective": "server",
            },
        }
    ]
    assert normalized["manifest"]["required_tools"] == []


@pytest.mark.no_db
def test_form_pack_preserves_ticket_created_diagnostic_playbook_trigger():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "2.0.0",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "site_system",
                    "request_kind": "site_system",
                    "title": "Site / system",
                    "playbook_triggers": [
                        {
                            "event": "ticket_created",
                            "playbook_key": "site_not_opening",
                            "module_kind": "diagnostic",
                            "enabled": True,
                        }
                    ],
                    "fields": [
                        {
                            "key": "url",
                            "label": "URL",
                            "type": "text",
                            "required": True,
                        }
                    ],
                }
            ],
        }
    )
    submission = validate_form_submission(
        pack,
        form_key="site_system",
        raw_values={
            "url": "https://intranet.example",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )
    custom_fields = build_form_custom_fields(submission)

    assert pack["forms"][0]["playbook_triggers"][0]["playbook_key"] == "site_not_opening"
    assert custom_fields["request_form_playbook_triggers"] == [
        {
            "event": "ticket_created",
            "playbook_key": "site_not_opening",
            "module_kind": "diagnostic",
            "enabled": True,
        }
    ]
    assert collect_ticket_created_playbook_triggers(custom_fields)[0]["playbook_key"] == "site_not_opening"


@pytest.mark.no_db
def test_build_ticket_playbook_context_returns_structured_fact_package():
    context = build_ticket_playbook_context(
        ticket_id="ticket-1",
        device_id="device-1",
        trigger={"playbook_key": "agent_offline", "module_kind": "diagnostic"},
        custom_fields={
            "request_form_key": "network",
            "request_form_data": {"pc_name": "WS-01"},
            "request_form_summary": [{"key": "pc_name", "label": "PC", "value": "WS-01"}],
        },
    )

    assert context["ticket"]["ticket_id"] == "ticket-1"
    assert context["device"]["device_id"] == "device-1"
    assert context["scenario"]["class"] == "diagnostic"
    assert context["facts_package"]["request_form_data"]["pc_name"] == "WS-01"
