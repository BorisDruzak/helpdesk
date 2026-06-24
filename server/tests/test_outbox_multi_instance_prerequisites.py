from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db

WORKSPACE = Path(__file__).resolve().parents[2]
PREREQUISITES_PATH = WORKSPACE / "quality" / "outbox_multi_instance_prerequisites.json"
ACTIVE_RISKS_PATH = WORKSPACE / "quality" / "active_risks.json"

REQUIRED_PREREQUISITES = {
    "db_coordination",
    "lock_ownership",
    "agent_connection_ownership",
    "lease_recovery",
    "multi_instance_test_plan",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_outbox_multi_instance_prerequisites_are_recorded() -> None:
    payload = _load_json(PREREQUISITES_PATH)

    assert payload["schema"] == "pc_client.outbox_multi_instance_prerequisites.v1"
    assert payload["status"] == "single_process_only"
    assert payload["deployment_gate"]["horizontal_server_dispatch"] == "blocked_until_prerequisites_pass"

    current_guards = set(payload["current_single_process_guards"])
    assert "server/tests/test_device_dispatch_integration.py::test_shard_dispatcher_light_load_50_devices_no_scheduling_loss" in current_guards
    assert "server/tests/test_device_dispatch_runtime.py::test_sharded_dispatch_commits_each_command_before_next_send" in current_guards

    prerequisites = {item["id"]: item for item in payload["required_before_horizontal_scaling"]}
    assert REQUIRED_PREREQUISITES <= set(prerequisites)
    for prerequisite_id in REQUIRED_PREREQUISITES:
        item = prerequisites[prerequisite_id]
        assert item["owner_zone"] == "server_runtime"
        assert item["requirement"].strip()
        assert item["evidence_refs"]
        assert item["test_plan"]


def test_td015_active_risk_links_outbox_multi_instance_record() -> None:
    payload = _load_json(ACTIVE_RISKS_PATH)
    td015 = next(risk for risk in payload["risks"] if risk["id"] == "TD-015")

    assert td015["status"] == "accepted"
    assert "quality/outbox_multi_instance_prerequisites.json" in td015["evidence_refs"]
    assert any(
        ref["ref"] == "server/tests/test_outbox_multi_instance_prerequisites.py::test_outbox_multi_instance_prerequisites_are_recorded"
        for ref in td015["linked_tests"]
    )
    assert any(
        criterion["metric"] == "multi-instance prerequisite record"
        and "quality/outbox_multi_instance_prerequisites.json" in criterion["target"]
        for criterion in td015["acceptance_criteria"]
    )
