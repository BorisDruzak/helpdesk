"""Recipe inputs must satisfy every bound DTO, never widen literal-only fields."""
import importlib
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.no_db


def parameters_module():
    assert importlib.util.find_spec("diagnostics.endpoint_tool_parameters") is not None, "typed tool input validation is required"
    return importlib.import_module("diagnostics.endpoint_tool_parameters")


def catalog():
    # Hand-checked shared timeout bounds and literal-only family.
    return {"items": [
        {"capability": "network.ping", "parameter_schema_version": "network_ping_parameters_v1", "parameters": [
            {"name": "target", "value_type": "string", "allowed_sources": ["input", "literal"]},
            {"name": "count", "value_type": "integer", "allowed_sources": ["input", "literal"], "minimum": 1, "maximum": 5},
            {"name": "timeout_ms", "value_type": "integer", "allowed_sources": ["input", "literal"], "minimum": 100, "maximum": 5000}]},
        {"capability": "tcp.connect", "parameter_schema_version": "tcp_connect_parameters_v1", "parameters": [
            {"name": "target", "value_type": "string", "allowed_sources": ["input", "literal"]},
            {"name": "port", "value_type": "integer", "allowed_sources": ["input", "literal"], "minimum": 1, "maximum": 65535},
            {"name": "timeout_ms", "value_type": "integer", "allowed_sources": ["input", "literal"], "minimum": 100, "maximum": 10000}]},
        {"capability": "dns.resolve", "parameter_schema_version": "dns_resolve_parameters_v1", "parameters": [
            {"name": "target", "value_type": "string", "allowed_sources": ["input", "literal"]},
            {"name": "family", "value_type": "enum", "allowed_sources": ["literal"], "enum_values": ["any", "ipv4", "ipv6"]}]}]}


def recipe():
    return {"schema_version": "endpoint_recipe_module_v1", "module_key": "network.test",
        "supported_platforms": ["windows_amd64"],
        "inputs": [{"name": "target", "value_type": "string"}, {"name": "timeout", "value_type": "integer"}],
        "steps": [
            {"step_id": "ping", "capability": "network.ping", "parameters": {
                "target": {"kind": "input", "name": "target"}, "count": {"kind": "literal", "value": 2},
                "timeout_ms": {"kind": "input", "name": "timeout"}}},
            {"step_id": "tcp", "capability": "tcp.connect", "parameters": {
                "target": {"kind": "input", "name": "target"}, "port": {"kind": "literal", "value": 443},
                "timeout_ms": {"kind": "input", "name": "timeout"}}}]}


def test_shared_input_bounds_intersect():
    tools = parameters_module()
    schema = tools.derive_recipe_inputs(recipe(), catalog())
    timeout = next(item for item in schema.inputs if item.name == "timeout")
    assert (timeout.minimum, timeout.maximum) == (100, 5000)
    assert tools.validate_tool_inputs(schema, {"target": "example.test", "timeout": 5000}).inputs == {"target": "example.test", "timeout": 5000}
    for values in ({"target": "example.test", "timeout": 5001}, {"target": "https://example.test", "timeout": 100},
                   {"target": "example.test", "timeout": True}, {"target": "example.test", "timeout": 100, "shell": "bad"}):
        with pytest.raises(ValueError):
            tools.validate_tool_inputs(schema, values)


def test_conflicting_bounds_block_recipe():
    tools = parameters_module()
    metadata = catalog()
    metadata["items"][1]["parameters"][2]["minimum"] = 6000
    with pytest.raises(ValueError):
        tools.derive_recipe_inputs(recipe(), metadata)


def test_literal_parameter_is_not_input():
    tools = parameters_module()
    dns = {"schema_version": "endpoint_recipe_module_v1", "module_key": "network.dns", "supported_platforms": ["windows_amd64"],
        "inputs": [{"name": "target", "value_type": "string"}], "steps": [{"step_id": "dns", "capability": "dns.resolve",
        "parameters": {"target": {"kind": "input", "name": "target"}, "family": {"kind": "literal", "value": "any"}}}]}
    schema = tools.derive_recipe_inputs(dns, catalog())
    assert [item.name for item in schema.inputs] == ["target"]
    assert schema.fixed_settings[0].value == "any"
    dns["inputs"].append({"name": "family", "value_type": "string"})
    dns["steps"][0]["parameters"]["family"] = {"kind": "input", "name": "family"}
    with pytest.raises(ValueError):
        tools.derive_recipe_inputs(dns, catalog())


def test_unknown_parameter_schema_cannot_enable_execution():
    tools = parameters_module()
    metadata = catalog()
    metadata["items"][0]["parameter_schema_version"] = "network_ping_parameters_v9"
    with pytest.raises(ValueError):
        tools.derive_recipe_inputs(recipe(), metadata)


def test_updater_literal_uses_the_accepted_logical_service_key():
    tools = parameters_module()
    metadata = {"items": [{"capability": "system.service_status", "parameter_schema_version": "service_status_parameters_v1",
        "parameters": [{"name": "service_key", "value_type": "enum", "allowed_sources": ["literal"],
                        "enum_values": ["endpoint_agent", "endpoint_agent_updater"]}]}]}
    service = {"schema_version": "endpoint_recipe_module_v1", "module_key": "service.updater", "inputs": [],
        "supported_platforms": ["windows_amd64"], "steps": [{"step_id": "updater", "capability": "system.service_status",
        "parameters": {"service_key": {"kind": "literal", "value": "endpoint_agent_updater"}}}]}
    assert tools.derive_recipe_inputs(service, metadata).fixed_settings[0].value == "endpoint_agent_updater"


def test_family_input_is_available_when_published_recipe_declares_it():
    tools = parameters_module()
    metadata = catalog()
    metadata["items"][2]["parameters"][1]["allowed_sources"] = ["input", "literal"]
    dns = {"schema_version": "endpoint_recipe_module_v1", "module_key": "network.dns", "supported_platforms": ["windows_amd64"],
        "inputs": [{"name": "target", "value_type": "string"}, {"name": "family", "value_type": "string"}],
        "steps": [{"step_id": "dns", "capability": "dns.resolve", "parameters": {
            "target": {"kind": "input", "name": "target"}, "family": {"kind": "input", "name": "family"}}}]}
    schema = tools.derive_recipe_inputs(dns, metadata)
    assert next(item for item in schema.inputs if item.name == "family").enum_values == ("any", "ipv4", "ipv6")
    assert tools.validate_tool_inputs(schema, {"target": "example.test", "family": "ipv6"}).inputs["family"] == "ipv6"
