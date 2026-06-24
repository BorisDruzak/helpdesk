#!/usr/bin/env python3
"""JSON Schema builders for checked test fixture/data-pack inputs."""

from __future__ import annotations

from typing import Any


REGISTRY_SCHEMA = "pc_client.fixture_builders.v1"
WEB_FIRST_PHASE_E_SCHEMA = "web_first_phase_e_test_data_pack_v1"
CRITICAL_BEHAVIOR_SCHEMA = "pc_client.critical_behavior_data_pack.v1"


def _string() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def _string_array(*, min_items: int = 1) -> dict[str, Any]:
    return {"type": "array", "items": _string(), "minItems": min_items}


def _object(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": True,
    }


def fixture_registry_schema() -> dict[str, Any]:
    return _object(
        ["schema", "fixtures"],
        {
            "$schema": {"type": "string"},
            "schema": {"const": REGISTRY_SCHEMA},
            "fixtures": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["id", "path", "schema_builder", "owner"],
                    {
                        "id": _string(),
                        "path": _string(),
                        "schema_builder": {"enum": [WEB_FIRST_PHASE_E_SCHEMA, "critical_behavior_data_pack_v1"]},
                        "owner": _string(),
                        "secret_free": {"type": "boolean"},
                    },
                ),
            },
        },
    )


def web_first_phase_e_test_data_pack_v1() -> dict[str, Any]:
    return _object(
        ["schema", "purpose", "version", "run_id_prefix", "users", "vm_agents", "knowledge", "forms", "validation_matrix"],
        {
            "$schema": {"type": "string"},
            "schema": {"const": WEB_FIRST_PHASE_E_SCHEMA},
            "purpose": {"const": "pre_broad_live_testing_gate"},
            "version": {"type": "integer", "minimum": 1},
            "run_id_prefix": _string(),
            "users": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["key", "role", "credential_source"],
                    {
                        "key": _string(),
                        "role": {"enum": ["admin", "support", "requester"]},
                        "credential_source": {"const": "environment_or_secret_store"},
                        "required_capabilities": _string_array(min_items=0),
                        "profile_state": {"enum": ["complete", "incomplete"]},
                        "expected_primary_agent": {"type": ["string", "null"]},
                    },
                ),
            },
            "vm_agents": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    [
                        "key",
                        "os",
                        "device_id_source",
                        "unique_device_id_required",
                        "manual_contamination_check_required",
                        "bound_requester",
                        "primary_active_binding_required",
                        "module_snapshot_required",
                    ],
                    {
                        "key": _string(),
                        "os": {"enum": ["windows", "linux", "macos"]},
                        "ssh_required": {"type": "boolean"},
                        "agent_installed_required": {"type": "boolean"},
                        "device_id_source": {"const": "live_registry"},
                        "unique_device_id_required": {"type": "boolean"},
                        "manual_contamination_check_required": {"type": "boolean"},
                        "bound_requester": _string(),
                        "primary_active_binding_required": {"type": "boolean"},
                        "module_snapshot_required": {"type": "boolean"},
                        "evidence": _string_array(min_items=0),
                    },
                ),
            },
            "knowledge": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["scenario", "visibility", "audience"],
                    {
                        "scenario": _string(),
                        "visibility": {"enum": ["requester", "support", "admin"]},
                        "audience": _string(),
                    },
                ),
            },
            "forms": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["scenario", "template_key", "availability_policy"],
                    {
                        "scenario": _string(),
                        "template_key": _string(),
                        "availability_policy": {"type": "object"},
                        "on_behalf_policy": {"type": "object"},
                        "approval_policy": {"type": "object"},
                        "sla_policy": {"type": "object"},
                        "diagnostic_policy": {"type": "object"},
                    },
                ),
            },
            "validation_matrix": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["gate", "evidence"],
                    {
                        "gate": _string(),
                        "evidence": _string_array(),
                    },
                ),
            },
        },
    )


def critical_behavior_data_pack_v1() -> dict[str, Any]:
    return _object(
        [
            "schema",
            "purpose",
            "version",
            "pack_version",
            "run_id_prefix",
            "requires_manifest_schema",
            "source_packs",
            "domains",
        ],
        {
            "$schema": {"type": "string"},
            "schema": {"const": CRITICAL_BEHAVIOR_SCHEMA},
            "purpose": {"const": "critical_behavior_live_gate"},
            "version": {"type": "integer", "minimum": 1},
            "pack_version": _string(),
            "run_id_prefix": _string(),
            "requires_manifest_schema": {"const": "pc_client.live_evidence.v2"},
            "source_packs": _string_array(),
            "shared_data_refs": {"type": "object"},
            "domains": {
                "type": "array",
                "minItems": 1,
                "items": _object(
                    ["key", "owner", "priority", "critical_invariants", "automated_layers", "live_scenarios"],
                    {
                        "key": _string(),
                        "owner": _string(),
                        "priority": {"enum": ["critical", "high"]},
                        "critical_invariants": _string_array(),
                        "automated_layers": {
                            "type": "array",
                            "minItems": 1,
                            "items": _object(
                                ["kind", "test_refs"],
                                {
                                    "kind": _string(),
                                    "test_refs": _string_array(),
                                },
                            ),
                        },
                        "live_scenarios": {
                            "type": "array",
                            "minItems": 1,
                            "items": _object(
                                [
                                    "key",
                                    "surface",
                                    "data_refs",
                                    "required_evidence",
                                    "manifest_requirements",
                                    "expected_outcomes",
                                ],
                                {
                                    "key": _string(),
                                    "surface": _string(),
                                    "data_refs": {"type": "object"},
                                    "required_evidence": _string_array(),
                                    "manifest_requirements": _string_array(),
                                    "expected_outcomes": _string_array(),
                                },
                            ),
                        },
                    },
                ),
            },
        },
    )


def schema_builders() -> dict[str, dict[str, Any]]:
    return {
        WEB_FIRST_PHASE_E_SCHEMA: web_first_phase_e_test_data_pack_v1(),
        "critical_behavior_data_pack_v1": critical_behavior_data_pack_v1(),
    }
