import importlib
import json
from pathlib import Path


def _complete_manifest(root: Path) -> Path:
    screenshot = root / "browser.png"
    screenshot.write_bytes(b"fake-png")
    manifest = {
        "schema": "pc_client.live_evidence.v2",
        "run_id": "live-validator-pass",
        "scenario": "requester_create",
        "status": "pass",
        "commit": "abc1234",
        "deployed_commit": "abc1234",
        "environment": "stand",
        "started_at": "2026-06-23T01:00:00+00:00",
        "finished_at": "2026-06-23T01:01:00+00:00",
        "entities": {
            "ticket_id": "T-000123",
            "device_id": "device-abc",
            "operation_id": None,
            "trace_ids": ["trace-1"],
        },
        "checks": [
            {
                "layer": "browser",
                "surface": "requester",
                "expected": "ticket appears in requester cabinet",
                "actual": "ticket T-000123 visible",
                "status": "pass",
                "artifact_path": "browser.png",
                "query_request_digest": "GET /app/requester sha256:1234",
                "timestamp": "2026-06-23T01:00:30+00:00",
                "redaction_status": "redacted",
            }
        ],
        "artifacts": [
            {
                "kind": "screenshot",
                "path": "browser.png",
                "description": "Requester cabinet after create",
                "redaction_status": "redacted",
            }
        ],
        "contamination": {"status": "clean", "notes": "fresh run marker"},
        "cleanup": {"status": "completed", "notes": "test data removed"},
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_validate_live_evidence_accepts_complete_manifest(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)

    assert validator.main(["--manifest", str(manifest_path)]) == 0

    assert "status=pass" in capsys.readouterr().out


def test_validate_live_evidence_rejects_template_manifest(tmp_path, capsys):
    pack = importlib.import_module("scripts.live_evidence_pack")
    validator = importlib.import_module("scripts.validate_live_evidence")
    pack.main(["--run-id", "draft-run", "--surface", "requester", "--artifacts-root", str(tmp_path)])

    manifest_path = tmp_path / "live" / "draft-run" / "manifest.json"

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "checks must contain at least one item" in output
    assert "commit is required" in output
    assert "artifacts must contain at least one item" in output
