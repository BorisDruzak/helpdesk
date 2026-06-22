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
    ]:
        assert (output_dir / name).is_file(), name

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "live-20260622-smoke"
    assert manifest["ticket"] == "T-000123"
    assert manifest["device"] == "device-abc"
    assert manifest["surface"] == "requester"


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
