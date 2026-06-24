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


def test_live_browser_script_uses_real_routes_without_network_mocks() -> None:
    script = BROWSER_SCRIPT.read_text(encoding="utf-8")

    assert "page.route(" not in script
    assert "PC_CLIENT_REQUESTER_LOGIN" in script
    assert "PC_CLIENT_SUPPORT_LOGIN" in script
    assert '"/app/requester"' in script
    assert '"/app/requester/tickets"' in script
    assert '"/app/support"' in script
    assert '"/app/tickets"' in script
