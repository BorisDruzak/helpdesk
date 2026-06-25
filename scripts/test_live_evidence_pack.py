import importlib
import json
from pathlib import Path


def test_live_evidence_pack_creates_expected_markdown_files(tmp_path):
    pack = importlib.import_module("scripts.live_evidence_pack")

    exit_code = pack.main(
        [
            "--run-id",
            "live-20260622-smoke",
            "--ticket",
            "T-000123",
            "--device",
            "device-abc",
            "--surface",
            "requester",
            "--artifacts-root",
            str(tmp_path),
        ]
    )

    output_dir = tmp_path / "live" / "live-20260622-smoke"
    assert exit_code == 0
    assert output_dir.is_dir()
    for name in [
        "browser.md",
        "api.md",
        "server-db.md",
        "agent-sqlite.md",
        "logs.md",
        "contamination.md",
        "observer-delta.md",
        "observer-canary.md",
    ]:
        assert (output_dir / name).is_file(), name

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "pc_client.live_evidence.v2"
    assert manifest["run_id"] == "live-20260622-smoke"
    assert manifest["scenario"] == "requester"
    assert manifest["entities"]["ticket_id"] == "T-000123"
    assert manifest["entities"]["device_id"] == "device-abc"
    assert manifest["status"] == "blocked"
    assert manifest["preflight"]["schema_status"] == "blocked"
    assert manifest["preflight"]["service_health"] == "blocked"
    assert manifest["observer_delta"]["status"] == "blocked"
    assert manifest["observer_delta"]["before"]["scan_status"] == "blocked"
    assert manifest["observer_delta"]["after"]["scan_status"] == "blocked"
    assert manifest["observer_canary"]["coverage_status"] == "blocked"
    assert manifest["observer_canary"]["status"] == "blocked"


def test_live_evidence_pack_records_scenario_key_and_release_context(tmp_path):
    pack = importlib.import_module("scripts.live_evidence_pack")

    exit_code = pack.main(
        [
            "--run-id",
            "rel-1__requester_support_chat_roundtrip",
            "--surface",
            "support",
            "--scenario-key",
            "requester_support_chat_roundtrip",
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
            "--actual-schema-head",
            "schema-head",
            "--artifacts-root",
            str(tmp_path),
        ]
    )

    manifest = json.loads(
        (tmp_path / "live" / "rel-1__requester_support_chat_roundtrip" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert exit_code == 0
    assert manifest["scenario"] == "requester_support_chat_roundtrip"
    assert manifest["scenario_key"] == "requester_support_chat_roundtrip"
    assert manifest["surface"] == "support"
    assert manifest["release_run_id"] == "rel-1"
    assert manifest["commit"] == "abc1234"
    assert manifest["deployed_commit"] == "abc1234"
    assert manifest["environment"] == "stand"
    assert manifest["preflight"]["branch"] == "codex/helpdesk-process-model"
    assert manifest["preflight"]["local_commit"] == "abc1234"
    assert manifest["preflight"]["deployed_commit"] == "abc1234"
    assert manifest["preflight"]["expected_schema_head"] == "schema-head"
    assert manifest["preflight"]["actual_schema_head"] == "schema-head"


def test_requester_surface_template_includes_account_session_and_binding_checks(tmp_path):
    pack = importlib.import_module("scripts.live_evidence_pack")

    pack.main(
        [
            "--run-id",
            "requester-run",
            "--surface",
            "requester",
            "--artifacts-root",
            str(tmp_path),
        ]
    )

    browser = (tmp_path / "live" / "requester-run" / "browser.md").read_text(encoding="utf-8")
    server_db = (tmp_path / "live" / "requester-run" / "server-db.md").read_text(encoding="utf-8")
    assert "/app/requester" in browser
    assert "authenticated web account" in browser
    assert "account_session_id" in server_db
    assert "registry binding" in server_db


def test_admin_surface_template_includes_network_and_log_checks(tmp_path):
    pack = importlib.import_module("scripts.live_evidence_pack")

    pack.main(
        [
            "--run-id",
            "admin-run",
            "--surface",
            "admin",
            "--artifacts-root",
            str(tmp_path),
        ]
    )

    browser = (tmp_path / "live" / "admin-run" / "browser.md").read_text(encoding="utf-8")
    logs = (tmp_path / "live" / "admin-run" / "logs.md").read_text(encoding="utf-8")
    assert "/admin" in browser
    assert "network" in browser
    assert "server log" in logs
