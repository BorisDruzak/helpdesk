import importlib
import json
from pathlib import Path


def _complete_manifest(root: Path) -> Path:
    screenshot = root / "browser.png"
    screenshot.write_bytes(b"fake-png")
    canary_report = root / "observer-canary.json"
    canary_report.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-23T01:00:45+00:00",
                "base_url": "https://192.168.100.17:9443",
                "device_id": "device-abc",
                "coverage": {
                    "ok": True,
                    "required_root_kinds": ["module_install", "web_auth"],
                    "observed_root_kinds": ["module_install", "web_auth"],
                    "missing_root_kinds": [],
                    "trace_refs": [
                        {"scenario": "module_install", "root_kind": "module_install", "trace_id": "trace-canary-1"},
                        {"scenario": "coverage_web_auth", "root_kind": "web_auth", "trace_id": "trace-canary-2"},
                    ],
                },
                "results": [
                    {"name": "module_install", "ok": True, "summary": "Installed canary module."},
                    {"name": "coverage_web_auth", "ok": True, "summary": "Observed web auth trace."},
                ],
            }
        ),
        encoding="utf-8",
    )
    canary_markdown = root / "observer-canary.md"
    canary_markdown.write_text("# Observer Canary Report\n\nCoverage: passed\n", encoding="utf-8")
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
        "preflight": {
            "branch": "codex/helpdesk-process-model",
            "local_commit": "abc1234",
            "deployed_commit": "abc1234",
            "expected_schema_head": "schema-a",
            "actual_schema_head": "schema-a",
            "schema_status": "pass",
            "service_health": "pass",
            "checked_at": "2026-06-23T01:00:05+00:00",
        },
        "observer_delta": {
            "baseline_run_id": "observer-baseline-live-validator-pass",
            "scenario_run_id": "live-validator-pass",
            "before": {
                "active_refs": [],
                "suppressed_refs": [],
                "scan_status": "pass",
                "checked_at": "2026-06-23T01:00:10+00:00",
            },
            "after": {
                "active_refs": [],
                "suppressed_refs": [],
                "scan_status": "pass",
                "checked_at": "2026-06-23T01:00:50+00:00",
            },
            "delta": {
                "new_active_critical_high_error_refs": [],
                "unexpected_suppression_refs": [],
            },
            "traces": {
                "required_trace_ids": ["trace-1"],
                "linked_trace_ids": ["trace-1"],
                "missing_required_trace_ids": [],
                "db_outcome": "ticket appears in requester cabinet",
                "trace_outcome": "requester create trace succeeded",
                "consistency_status": "pass",
            },
            "checker_status": "pass",
            "writer_status": "pass",
            "correlation_status": "pass",
            "status": "pass",
            "checked_at": "2026-06-23T01:00:55+00:00",
        },
        "observer_canary": {
            "json_report_path": "observer-canary.json",
            "markdown_report_path": "observer-canary.md",
            "required_root_kinds": ["module_install", "web_auth"],
            "observed_root_kinds": ["module_install", "web_auth"],
            "missing_root_kinds": [],
            "failed_scenarios": [],
            "coverage_status": "pass",
            "status": "pass",
            "checked_at": "2026-06-23T01:00:58+00:00",
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


def test_validate_live_evidence_requires_commit_schema_preflight(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("preflight", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "preflight is required" in output


def test_validate_live_evidence_rejects_commit_or_schema_preflight_mismatch(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["preflight"] = {
        "branch": "codex/helpdesk-process-model",
        "local_commit": "zzz9999",
        "deployed_commit": "def5678",
        "expected_schema_head": "schema-a",
        "actual_schema_head": "schema-b",
        "schema_status": "fail",
        "service_health": "pass",
        "checked_at": "2026-06-23T01:00:05+00:00",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "preflight.local_commit must match commit" in output
    assert "preflight.deployed_commit must match deployed_commit" in output
    assert "commit and deployed_commit must match" in output
    assert "preflight actual_schema_head must match expected_schema_head" in output
    assert "preflight.schema_status must be pass" in output


def test_validate_live_evidence_requires_observer_integrity_delta(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("observer_delta", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "observer_delta is required" in output


def test_validate_live_evidence_requires_observer_canary_report(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("observer_canary", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "observer_canary is required" in output


def test_validate_live_evidence_rejects_observer_canary_failures(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    failed_report_path = tmp_path / "observer-canary-failed.json"
    failed_report_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-23T01:00:45+00:00",
                "coverage": {
                    "ok": False,
                    "required_root_kinds": ["module_install", "web_auth"],
                    "observed_root_kinds": ["module_install"],
                    "missing_root_kinds": ["web_auth"],
                    "trace_refs": [{"scenario": "module_install", "root_kind": "module_install", "trace_id": "trace-canary-1"}],
                },
                "results": [
                    {"name": "module_install", "ok": True, "summary": "Installed canary module."},
                    {"name": "coverage_web_auth", "ok": False, "summary": "No web auth trace."},
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["observer_canary"] = {
        "json_report_path": "observer-canary-failed.json",
        "markdown_report_path": "observer-canary.md",
        "required_root_kinds": ["module_install", "web_auth"],
        "observed_root_kinds": ["module_install"],
        "missing_root_kinds": ["web_auth"],
        "failed_scenarios": ["coverage_web_auth"],
        "coverage_status": "fail",
        "status": "fail",
        "checked_at": "2026-06-23T01:00:58+00:00",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "observer_canary.coverage_status must be pass" in output
    assert "observer_canary.status must be pass" in output
    assert "observer_canary.missing_root_kinds must be empty" in output
    assert "observer_canary.failed_scenarios must be empty" in output
    assert "observer_canary report coverage.ok must be true" in output
    assert "observer_canary report results must all pass" in output


def test_validate_live_evidence_rejects_observer_integrity_delta_stop_conditions(tmp_path, capsys):
    validator = importlib.import_module("scripts.validate_live_evidence")
    manifest_path = _complete_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["observer_delta"] = {
        "baseline_run_id": "observer-baseline-live-validator-pass",
        "scenario_run_id": "live-validator-pass",
        "before": {
            "active_refs": [],
            "suppressed_refs": [],
            "scan_status": "pass",
            "checked_at": "2026-06-23T01:00:10+00:00",
        },
        "after": {
            "active_refs": [],
            "suppressed_refs": ["observer.integrity:unexpected"],
            "scan_status": "incomplete",
            "checked_at": "2026-06-23T01:00:50+00:00",
        },
        "delta": {
            "new_active_critical_high_error_refs": ["observer.integrity:critical"],
            "unexpected_suppression_refs": ["observer.integrity:unexpected"],
        },
        "traces": {
            "required_trace_ids": ["trace-1", "trace-2"],
            "linked_trace_ids": ["trace-1"],
            "missing_required_trace_ids": ["trace-2"],
            "db_outcome": "ticket appears in requester cabinet",
            "trace_outcome": "trace missing terminal success",
            "consistency_status": "fail",
        },
        "checker_status": "incomplete",
        "writer_status": "fail",
        "correlation_status": "blocked",
        "status": "fail",
        "checked_at": "2026-06-23T01:00:55+00:00",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "observer_delta.after.scan_status must be pass" in output
    assert "observer_delta.delta.new_active_critical_high_error_refs must be empty" in output
    assert "observer_delta.delta.unexpected_suppression_refs must be empty" in output
    assert "observer_delta.traces.missing_required_trace_ids must be empty" in output
    assert "observer_delta.traces linked_trace_ids must include every required_trace_ids item" in output
    assert "observer_delta.traces.consistency_status must be pass" in output
    assert "observer_delta.checker_status must be pass" in output
    assert "observer_delta.writer_status must be pass" in output
    assert "observer_delta.correlation_status must be pass" in output
    assert "observer_delta.status must be pass" in output


def test_validate_live_evidence_rejects_template_manifest(tmp_path, capsys):
    pack = importlib.import_module("scripts.live_evidence_pack")
    validator = importlib.import_module("scripts.validate_live_evidence")
    pack.main(["--run-id", "draft-run", "--surface", "requester", "--artifacts-root", str(tmp_path)])

    manifest_path = tmp_path / "live" / "draft-run" / "manifest.json"

    assert validator.main(["--manifest", str(manifest_path)]) == 1

    output = capsys.readouterr().out
    assert "checks must contain at least one item" in output
    assert "commit is required" in output
    assert "preflight.local_commit is required" in output
    assert "observer_delta.baseline_run_id is required" in output
    assert "observer_canary.json_report_path is required" in output
    assert "artifacts must contain at least one item" in output
