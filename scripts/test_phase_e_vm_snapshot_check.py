from __future__ import annotations

import json

import pytest

import scripts.check_phase_e_vm_snapshot as checker


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


def _snapshot() -> dict:
    return {
        "schema": "web_first_phase_e_vm_snapshot_v1",
        "collected_at": "2026-06-17T10:00:00Z",
        "agents": [
            {
                "key": "lab-win-primary-agent",
                "os": "windows",
                "device_id": "live-win-device",
                "registry_device": {
                    "source": "live_registry",
                    "device_id": "live-win-device",
                },
                "bound_requester": "requester_a_completed_profile_windows_agent",
                "primary_active_binding": True,
                "agent_online": True,
                "module_snapshot": {"collected": True, "modules": ["system", "inventory"]},
                "manual_contamination_review": {
                    "status": "clean",
                    "reviewed_by": "qa",
                    "reviewed_at": "2026-06-17T10:05:00Z",
                },
            },
            {
                "key": "lab-lin-primary-agent",
                "os": "linux",
                "device_id": "live-lin-device",
                "registry_device": {
                    "source": "live_registry",
                    "device_id": "live-lin-device",
                },
                "bound_requester": "requester_b_completed_profile_linux_agent",
                "primary_active_binding": True,
                "agent_online": True,
                "module_snapshot": {"collected": True, "module_count": 2},
                "manual_contamination_review": {
                    "status": "clean",
                    "reviewed_by": "qa",
                    "reviewed_at": "2026-06-17T10:05:00Z",
                },
            },
        ],
    }


def test_phase_e_vm_snapshot_passes_when_required_live_evidence_is_clean() -> None:
    result = checker.validate_phase_e_vm_snapshot(_pack(), _snapshot())

    assert result["status"] == "pass"
    assert result["summary"]["failed_checks"] == 0
    assert {item["key"] for item in result["agents"]} == {
        "lab-win-primary-agent",
        "lab-lin-primary-agent",
    }


def test_phase_e_vm_snapshot_fails_duplicate_live_device_ids() -> None:
    snapshot = _snapshot()
    snapshot["agents"][1]["device_id"] = "live-win-device"
    snapshot["agents"][1]["registry_device"]["device_id"] = "live-win-device"

    result = checker.validate_phase_e_vm_snapshot(_pack(), snapshot)

    assert result["status"] == "fail"
    assert any(check["name"] == "unique_device_id" and check["status"] == "fail" for check in result["checks"])


def test_phase_e_vm_snapshot_fails_without_clean_manual_contamination_review() -> None:
    snapshot = _snapshot()
    snapshot["agents"][0]["manual_contamination_review"] = {"status": "needs_review"}

    result = checker.validate_phase_e_vm_snapshot(_pack(), snapshot)

    assert result["status"] == "fail"
    assert any(
        check.get("agent") == "lab-win-primary-agent"
        and check["name"] == "manual_contamination_review"
        and check["status"] == "fail"
        for check in result["checks"]
    )


def test_phase_e_vm_snapshot_cli_returns_nonzero_for_failed_snapshot(tmp_path) -> None:
    pack_path = tmp_path / "pack.json"
    snapshot_path = tmp_path / "snapshot.json"
    pack_path.write_text(json.dumps(_pack()), encoding="utf-8")
    failed = _snapshot()
    failed["agents"][0]["agent_online"] = False
    snapshot_path.write_text(json.dumps(failed), encoding="utf-8")

    assert checker.main(["--pack", str(pack_path), "--snapshot", str(snapshot_path), "--json"]) == 1
