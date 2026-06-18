from __future__ import annotations

import json

import pytest

import scripts.check_phase_e_vm_snapshot as checker
import scripts.collect_phase_e_vm_snapshot as collector


pytestmark = pytest.mark.no_db


def _pack() -> dict:
    return {
        "schema": "web_first_phase_e_test_data_pack_v1",
        "vm_agents": [
            {
                "key": "lab-win-primary-agent",
                "os": "windows",
                "device_id_source": "live_registry",
                "unique_device_id_required": True,
                "manual_contamination_check_required": True,
                "bound_requester": "requester_a_completed_profile_windows_agent",
                "primary_active_binding_required": True,
                "module_snapshot_required": True,
            },
            {
                "key": "lab-lin-primary-agent",
                "os": "linux",
                "device_id_source": "live_registry",
                "unique_device_id_required": True,
                "manual_contamination_check_required": True,
                "bound_requester": "requester_b_completed_profile_linux_agent",
                "primary_active_binding_required": True,
                "module_snapshot_required": True,
            },
        ],
    }


def test_collect_phase_e_vm_snapshot_builds_checker_compatible_snapshot() -> None:
    inventory = {
        "devices": [
            {
                "device_id": "win-device",
                "hostname": "lab-win-primary-agent",
                "os": "Windows 11",
                "agent_version": "3.1.68",
                "device_metadata": {
                    "manual_contamination_review": {"status": "clean", "reviewed_by": "qa"},
                },
                "bindings": [
                    {
                        "relationship_type": "primary_user",
                        "status": "active",
                        "person": {
                            "profile_key": "requester_a_completed_profile_windows_agent",
                            "metadata_json": {},
                        },
                    }
                ],
                "toolset_snapshot": {"snapshot_id": 10, "tool_count": 2, "captured_at": "2026-06-18T01:00:00Z"},
            },
            {
                "device_id": "lin-device",
                "hostname": "phase-e-linux-host",
                "os": "linux",
                "agent_version": "3.1.68",
                "device_metadata": {
                    "phase_e_agent_key": "lab-lin-primary-agent",
                    "manual_contamination_review": {"status": "clean", "reviewed_by": "qa"},
                },
                "bindings": [
                    {
                        "relationship_type": "primary_user",
                        "status": "active",
                        "person": {
                            "profile_key": "person-b",
                            "metadata_json": {"phase_e_user_key": "requester_b_completed_profile_linux_agent"},
                        },
                    }
                ],
                "toolset_snapshot": {
                    "snapshot_id": 11,
                    "tool_count": 1,
                    "captured_at": "2026-06-18T01:00:01Z",
                    "tools": [{"tool": "system.collect"}],
                },
            },
        ],
        "runtime": {"connected_device_ids": ["win-device", "lin-device"]},
    }

    snapshot = collector.build_phase_e_vm_snapshot(
        _pack(),
        inventory,
        collected_at="2026-06-18T01:02:03Z",
        source="unit_test",
    )

    assert snapshot["schema"] == "web_first_phase_e_vm_snapshot_v1"
    assert {agent["key"] for agent in snapshot["agents"]} == {
        "lab-win-primary-agent",
        "lab-lin-primary-agent",
    }
    assert snapshot["agents"][0]["registry_device"]["source"] == "live_registry"
    assert checker.validate_phase_e_vm_snapshot(_pack(), snapshot)["status"] == "pass"


def test_collect_phase_e_vm_snapshot_keeps_missing_required_agents_visible() -> None:
    snapshot = collector.build_phase_e_vm_snapshot(
        _pack(),
        {"devices": [], "runtime": {"connected_device_ids": []}},
        collected_at="2026-06-18T01:02:03Z",
        source="unit_test",
    )

    assert snapshot["agents"] == []
    assert "lab-win-primary-agent" in snapshot["missing_required_agents"]
    assert "lab-lin-primary-agent" in snapshot["missing_required_agents"]
    result = checker.validate_phase_e_vm_snapshot(_pack(), snapshot)
    assert result["status"] == "fail"
    assert result["summary"]["failed_checks"] == 2


def test_collect_phase_e_vm_snapshot_cli_accepts_database_url_override(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: dict[str, str | None] = {}

    async def fake_collect_inventory_from_db(database_url: str | None = None) -> dict:
        captured["database_url"] = database_url
        return {"devices": [], "runtime": {"connected_device_ids": []}}

    monkeypatch.setattr(collector, "collect_inventory_from_db", fake_collect_inventory_from_db)
    output = tmp_path / "snapshot.json"

    exit_code = collector.main(
        [
            "--database-url",
            "postgresql+asyncpg://example.invalid/pc_client",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert captured["database_url"] == "postgresql+asyncpg://example.invalid/pc_client"
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    assert snapshot["missing_required_agents"] == ["lab-win-primary-agent", "lab-lin-primary-agent"]
