from __future__ import annotations

import json
from pathlib import Path

from scripts import audit_fixture_builders


WORKSPACE = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_registry(workspace: Path) -> Path:
    registry_path = workspace / "quality" / "fixture_builders.json"
    _write_json(
        registry_path,
        {
            "schema": "pc_client.fixture_builders.v1",
            "fixtures": [
                {
                    "id": "web_first_phase_e",
                    "path": "test_data_packs/web_first_phase_e.json",
                    "schema_builder": "web_first_phase_e_test_data_pack_v1",
                    "owner": "quality",
                    "secret_free": True,
                },
                {
                    "id": "critical_behavior_v1",
                    "path": "test_data_packs/critical_behavior_v1.json",
                    "schema_builder": "critical_behavior_data_pack_v1",
                    "owner": "quality",
                    "secret_free": True,
                },
            ],
        },
    )
    return registry_path


def _valid_phase_e_pack() -> dict:
    return {
        "schema": "web_first_phase_e_test_data_pack_v1",
        "purpose": "pre_broad_live_testing_gate",
        "version": 1,
        "run_id_prefix": "web-first-phase-e",
        "users": [
            {
                "key": "admin_test",
                "role": "admin",
                "credential_source": "environment_or_secret_store",
                "required_capabilities": ["admin"],
            },
            {
                "key": "requester_a_completed_profile_windows_agent",
                "role": "requester",
                "credential_source": "environment_or_secret_store",
                "profile_state": "complete",
                "expected_primary_agent": "lab-win-primary-agent",
            },
        ],
        "vm_agents": [
            {
                "key": "lab-win-primary-agent",
                "os": "windows",
                "ssh_required": True,
                "agent_installed_required": True,
                "device_id_source": "live_registry",
                "unique_device_id_required": True,
                "manual_contamination_check_required": True,
                "bound_requester": "requester_a_completed_profile_windows_agent",
                "primary_active_binding_required": True,
                "module_snapshot_required": True,
                "evidence": ["registry_device"],
            }
        ],
        "knowledge": [
            {
                "scenario": "public_requester_article",
                "visibility": "requester",
                "audience": "public",
            }
        ],
        "forms": [
            {
                "scenario": "normal_incident",
                "template_key": "phase_e_normal_incident",
                "availability_policy": {
                    "available_without_completed_profile": False,
                    "available_without_agent_binding": False,
                },
                "on_behalf_policy": {"enabled": False},
            }
        ],
        "validation_matrix": [
            {
                "gate": "ticket_context_v1",
                "evidence": ["pytest", "browser_ticket_create"],
            }
        ],
    }


def _valid_critical_pack() -> dict:
    return {
        "schema": "pc_client.critical_behavior_data_pack.v1",
        "purpose": "critical_behavior_live_gate",
        "version": 1,
        "pack_version": "1.0.0",
        "run_id_prefix": "critical-behavior",
        "requires_manifest_schema": "pc_client.live_evidence.v2",
        "source_packs": ["test_data_packs/web_first_phase_e.json"],
        "shared_data_refs": {
            "phase_e_user_keys": ["requester_a_completed_profile_windows_agent"],
            "phase_e_agent_keys": ["lab-win-primary-agent"],
            "phase_e_form_scenarios": ["normal_incident"],
        },
        "domains": [
            {
                "key": "tickets_chat",
                "owner": "tickets",
                "priority": "critical",
                "critical_invariants": ["message_ordering"],
                "automated_layers": [
                    {
                        "kind": "service_api_db",
                        "test_refs": ["server/tests/test_example.py"],
                    }
                ],
                "live_scenarios": [
                    {
                        "key": "requester_support_chat_roundtrip",
                        "surface": "requester",
                        "data_refs": {
                            "users": ["requester_a_completed_profile_windows_agent"],
                            "agents": ["lab-win-primary-agent"],
                            "forms": ["normal_incident"],
                            "knowledge": ["public_requester_article"],
                        },
                        "required_evidence": ["browser", "api", "db", "observer", "live_manifest"],
                        "manifest_requirements": ["preflight", "observer_delta", "observer_canary", "cleanup"],
                        "expected_outcomes": ["public messages agree"],
                    }
                ],
            }
        ],
    }


def test_audit_fixture_builders_accepts_schema_valid_packs(tmp_path):
    registry_path = _write_registry(tmp_path)
    _write_json(tmp_path / "test_data_packs" / "web_first_phase_e.json", _valid_phase_e_pack())
    _write_json(tmp_path / "test_data_packs" / "critical_behavior_v1.json", _valid_critical_pack())
    test_path = tmp_path / "server" / "tests" / "test_example.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_example():\n    pass\n", encoding="utf-8")

    report = audit_fixture_builders.audit_fixture_builders(tmp_path, registry_path=registry_path)

    assert report["status"] == "ok"
    assert report["fixture_count"] == 2
    assert report["issues"] == []


def test_audit_fixture_builders_reports_schema_and_reference_errors(tmp_path):
    registry_path = _write_registry(tmp_path)
    phase_pack = _valid_phase_e_pack()
    del phase_pack["users"][0]["credential_source"]
    _write_json(tmp_path / "test_data_packs" / "web_first_phase_e.json", phase_pack)
    critical_pack = _valid_critical_pack()
    critical_pack["domains"][0]["automated_layers"][0]["test_refs"] = ["server/tests/test_missing.py"]
    critical_pack["domains"][0]["live_scenarios"][0]["data_refs"]["forms"] = ["missing_form"]
    _write_json(tmp_path / "test_data_packs" / "critical_behavior_v1.json", critical_pack)

    report = audit_fixture_builders.audit_fixture_builders(tmp_path, registry_path=registry_path)

    assert report["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} >= {
        "fixture_schema_validation",
        "missing_test_ref",
        "unknown_data_ref",
    }


def test_repository_fixture_builders_do_not_reference_deleted_tests() -> None:
    report = audit_fixture_builders.audit_fixture_builders(WORKSPACE)

    assert not [
        issue
        for issue in report["issues"]
        if issue["code"] == "missing_test_ref"
    ]
