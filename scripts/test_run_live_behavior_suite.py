from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "test_data_packs" / "critical_behavior_v1.json"
BROWSER_SCRIPT = ROOT / "webapp" / "scripts" / "live-browser-scenarios.mjs"


def test_discovers_requester_support_browser_scenarios_from_pack() -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")
    pack = runner.load_pack(PACK_PATH)

    scenarios = runner.discover_browser_scenarios(pack, surfaces={"requester", "support"})

    keys = {scenario["scenario_key"] for scenario in scenarios}
    assert "requester_support_chat_roundtrip" in keys
    assert "admin_publish_requester_create" in keys
    assert "support_queue_status_after_routing" in keys
    assert "admin_problem_support_link" not in keys
    assert {scenario["surface"] for scenario in scenarios} <= {"requester", "support"}
    assert all("browser" in scenario["required_evidence"] for scenario in scenarios)
    assert all({"preflight", "observer_delta"} <= set(scenario["manifest_requirements"]) for scenario in scenarios)


def test_dry_run_outputs_live_browser_commands(tmp_path, capsys) -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")

    exit_code = runner.main(
        [
            "--pack",
            str(PACK_PATH),
            "--surfaces",
            "requester,support",
            "--base-url",
            "https://stand.example.test",
            "--out-dir",
            str(tmp_path),
            "--dry-run",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["browser_script"] == "webapp/scripts/live-browser-scenarios.mjs"
    assert payload["scenario_count"] >= 4
    for item in payload["scenarios"]:
        command = item["command"]
        assert command[:2] == ["node", "webapp/scripts/live-browser-scenarios.mjs"]
        assert "--scenario-key" in command
        assert "--base-url" in command
        assert "https://stand.example.test" in command


def test_dry_run_can_scaffold_live_evidence_pack_for_selected_scenario(tmp_path, capsys) -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")

    exit_code = runner.main(
        [
            "--pack",
            str(PACK_PATH),
            "--surfaces",
            "support",
            "--scenario-key",
            "requester_support_chat_roundtrip",
            "--out-dir",
            str(tmp_path / "suite"),
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--release-run-id",
            "rel-1",
            "--commit",
            "abc1234",
            "--deployed-commit",
            "abc1234",
            "--environment",
            "stand",
            "--branch",
            "codex/helpdesk-process-model",
            "--expected-schema-head",
            "schema-head",
            "--dry-run",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    manifest_path = (
        tmp_path
        / "evidence"
        / "live"
        / "rel-1__requester_support_chat_roundtrip"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["scenarios"][0]["evidence_manifest"] == str(manifest_path)
    assert manifest["scenario_key"] == "requester_support_chat_roundtrip"
    assert manifest["release_run_id"] == "rel-1"
    assert manifest["commit"] == "abc1234"
    assert manifest["deployed_commit"] == "abc1234"
    assert manifest["environment"] == "stand"
    assert manifest["preflight"]["expected_schema_head"] == "schema-head"


def test_default_browser_dry_run_covers_all_visible_pack_surfaces(tmp_path, capsys) -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")

    exit_code = runner.main(
        [
            "--pack",
            str(PACK_PATH),
            "--out-dir",
            str(tmp_path),
            "--dry-run",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    keys = {item["scenario_key"] for item in payload["scenarios"]}
    assert payload["scenario_count"] == 14
    assert "real_account_device_linking" in keys
    assert "admin_problem_support_link" in keys
    assert "admin_change_approval_workflow" in keys
    assert "module_playbook_canary" in keys
    assert "admin_support_trace_drilldown" in keys
    assert "browser_totals_against_seeded_pack" in keys
    assert {item["surface"] for item in payload["scenarios"]} == {"requester", "support", "admin", "reports"}


def test_discovers_agent_operation_scenarios_from_pack() -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")
    pack = runner.load_pack(PACK_PATH)

    scenarios = runner.discover_agent_operation_scenarios(pack, surfaces={"native_agent", "operation_lifecycle"})

    keys = {scenario["scenario_key"] for scenario in scenarios}
    assert keys == {"tool_run_approve_deny_timeout", "windows_linux_vm_agent_runtime"}
    assert all("agent_sqlite" in scenario["required_evidence"] for scenario in scenarios)
    assert {scenario["surface"] for scenario in scenarios} == {"native_agent", "operation_lifecycle"}


def test_agent_operation_dry_run_outputs_probe_commands(tmp_path, capsys) -> None:
    runner = importlib.import_module("scripts.run_live_behavior_suite")

    exit_code = runner.main(
        [
            "--pack",
            str(PACK_PATH),
            "--mode",
            "agent-operation",
            "--surfaces",
            "native_agent,operation_lifecycle",
            "--out-dir",
            str(tmp_path),
            "--dry-run",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["runner_mode"] == "agent-operation"
    assert payload["scenario_count"] == 2
    commands = {item["scenario_key"]: item["command"] for item in payload["scenarios"]}
    assert commands["windows_linux_vm_agent_runtime"][:2] == ["python", "scripts/live_agent_uia_state_probe.py"]
    assert "--expect-connected" in commands["windows_linux_vm_agent_runtime"]
    assert commands["tool_run_approve_deny_timeout"][:2] == ["python", "scripts/live_ws_v3_probe.py"]
    assert "malformed-outbox" in commands["tool_run_approve_deny_timeout"]


def test_live_browser_script_uses_real_routes_without_network_mocks() -> None:
    script = BROWSER_SCRIPT.read_text(encoding="utf-8")

    assert "page.route(" not in script
    assert "PC_CLIENT_REQUESTER_LOGIN" in script
    assert "PC_CLIENT_SUPPORT_LOGIN" in script
    assert "PC_CLIENT_ADMIN_LOGIN" in script
    assert 'waitFor({ state: "visible", timeout: 10_000 })' in script
    assert '"/app/requester"' in script
    assert '"/app/requester/tickets"' in script
    assert '"/app/support"' in script
    assert '"/app/tickets"' in script
    assert '"/app/admin/registry"' in script
    assert '"/app/admin/problems"' in script
    assert '"/app/admin/changes"' in script
    assert '"/app/admin/modules"' in script
    assert '"/app/admin/playbooks"' in script
    assert '"/app/admin/observer"' in script
    assert '"/app/reports"' in script
