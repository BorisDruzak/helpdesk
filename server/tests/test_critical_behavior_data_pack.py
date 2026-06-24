from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "test_data_packs" / "critical_behavior_v1.json"

REQUIRED_DOMAINS = {
    "auth_web_sessions",
    "registry_cmdb_access",
    "tickets_chat",
    "forms_service_catalog",
    "routing_sla_ola",
    "knowledge_platform",
    "quality_loop",
    "problem_management",
    "change_enablement",
    "diagnostics_providers",
    "modules_recipes_playbooks",
    "operations_consent",
    "agent_auth_update_runtime",
    "remote_assist",
    "observer",
    "reports_analytics",
    "release_deploy",
}
MANDATORY_EVIDENCE = {"api", "db", "observer", "live_manifest"}
VISIBLE_SURFACES = {"admin", "requester", "support", "webapp", "reports"}
FORBIDDEN_SECRET_KEYS = {"password", "token", "secret", "cookie", "auth_header", "authorization"}


def _walk_dicts(value: Any, *, path: str = "$") -> Iterator[tuple[str, str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk_dicts(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_dicts(child, path=f"{path}[{index}]")


@pytest.mark.no_db
def test_critical_behavior_data_pack_covers_workstream_d_matrix() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))

    assert pack["schema"] == "pc_client.critical_behavior_data_pack.v1"
    assert pack["purpose"] == "critical_behavior_live_gate"
    assert pack["version"] == 1
    assert pack["requires_manifest_schema"] == "pc_client.live_evidence.v2"
    assert "test_data_packs/web_first_phase_e.json" in pack["source_packs"]
    for source_pack in pack["source_packs"]:
        assert (ROOT / source_pack).is_file(), source_pack

    domains = {item["key"]: item for item in pack["domains"]}
    assert REQUIRED_DOMAINS <= set(domains)
    for key, record in domains.items():
        assert record["owner"], key
        assert record["priority"] in {"critical", "high"}, key
        assert record["critical_invariants"], key
        assert record["automated_layers"], key
        for layer in record["automated_layers"]:
            assert layer["kind"], key
            assert layer["test_refs"], key
            for test_ref in layer["test_refs"]:
                assert (ROOT / test_ref).is_file(), f"{key}: {test_ref}"

        assert record["live_scenarios"], key
        for scenario in record["live_scenarios"]:
            assert scenario["key"], key
            assert scenario["surface"], scenario["key"]
            evidence = set(scenario["required_evidence"])
            assert MANDATORY_EVIDENCE <= evidence, scenario["key"]
            if scenario["surface"] in VISIBLE_SURFACES:
                assert "browser" in evidence, scenario["key"]
            assert {"preflight", "observer_delta"} <= set(scenario["manifest_requirements"]), scenario["key"]
            assert scenario["data_refs"], scenario["key"]
            assert scenario["expected_outcomes"], scenario["key"]


@pytest.mark.no_db
def test_critical_behavior_data_pack_contains_no_secret_material() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))

    for path, key, value in _walk_dicts(pack):
        assert key.lower() not in FORBIDDEN_SECRET_KEYS, path
        if isinstance(value, str):
            lower_value = value.lower()
            assert "begin private key" not in lower_value, path
            assert "bearer " not in lower_value, path
