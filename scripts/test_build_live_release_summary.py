import importlib
import json
from pathlib import Path


def _write_pack(path: Path, *, scenario_keys: list[str]) -> None:
    domains = []
    for index, scenario_key in enumerate(scenario_keys, start=1):
        domains.append(
            {
                "key": f"domain_{index}",
                "owner": "qa",
                "priority": "critical",
                "critical_invariants": [f"invariant {index}"],
                "existing_test_refs": ["scripts/test_build_live_release_summary.py"],
                "live_scenarios": [
                    {
                        "key": scenario_key,
                        "surface": "requester" if index == 1 else "operation_lifecycle",
                        "required_evidence": ["browser", "api", "db", "observer", "live_manifest"],
                        "manifest_requirements": ["preflight", "observer_delta", "observer_canary", "cleanup"],
                        "expected_outcomes": [f"outcome {index}"],
                    }
                ],
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema": "pc_client.critical_behavior_data_pack.v1",
                "version": 1,
                "domains": domains,
            }
        ),
        encoding="utf-8",
    )


def _write_complete_manifest(
    root: Path,
    *,
    scenario_key: str,
    commit: str = "abc1234",
    environment: str = "stand",
    release_run_id: str = "release-run-1",
    expected_schema_head: str = "schema-a",
    status: str = "pass",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "browser.png").write_bytes(b"fake-png")
    (root / "observer-canary.md").write_text("# Observer Canary Report\n", encoding="utf-8")
    (root / "observer-canary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-23T01:00:45+00:00",
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
    manifest = {
        "schema": "pc_client.live_evidence.v2",
        "run_id": f"live-{scenario_key}",
        "release_run_id": release_run_id,
        "scenario": scenario_key,
        "status": status,
        "commit": commit,
        "deployed_commit": commit,
        "environment": environment,
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
            "local_commit": commit,
            "deployed_commit": commit,
            "expected_schema_head": expected_schema_head,
            "actual_schema_head": expected_schema_head,
            "schema_status": "pass",
            "service_health": "pass",
            "checked_at": "2026-06-23T01:00:05+00:00",
        },
        "observer_delta": {
            "baseline_run_id": f"observer-baseline-{scenario_key}",
            "scenario_run_id": f"live-{scenario_key}",
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
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_build_live_release_summary_blocks_without_required_manifests(tmp_path):
    summary_builder = importlib.import_module("scripts.build_live_release_summary")
    pack_path = tmp_path / "critical_behavior.json"
    _write_pack(pack_path, scenario_keys=["requester_create", "tool_run"])

    summary = summary_builder.build_summary(pack_path=pack_path, live_root=tmp_path / "live")

    assert summary["status"] == "blocked"
    assert summary["coverage"]["scenario_count"] == 2
    assert summary["coverage"]["passed_scenario_keys"] == []
    assert summary["coverage"]["missing_scenario_keys"] == ["requester_create", "tool_run"]
    assert summary["required_manifest_sections"] == ["cleanup", "observer_canary", "observer_delta", "preflight"]
    assert summary["suite_plan"]["browser_scenarios"] == 1
    assert summary["suite_plan"]["agent_operation_scenarios"] == 1


def test_build_live_release_summary_accepts_complete_manifest_and_writes_outputs(tmp_path):
    summary_builder = importlib.import_module("scripts.build_live_release_summary")
    pack_path = tmp_path / "critical_behavior.json"
    _write_pack(pack_path, scenario_keys=["requester_create"])
    _write_complete_manifest(tmp_path / "live" / "requester_create", scenario_key="requester_create")
    output_path = tmp_path / "summary.json"
    markdown_path = tmp_path / "summary.md"

    exit_code = summary_builder.main(
        [
            "--pack",
            str(pack_path),
            "--live-root",
            str(tmp_path / "live"),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["coverage"]["passed_scenario_keys"] == ["requester_create"]
    assert payload["release_blockers"] == []
    assert "requester_create" in markdown_path.read_text(encoding="utf-8")


def test_build_live_release_summary_filters_to_exact_release_context_and_fail_wins(tmp_path):
    summary_builder = importlib.import_module("scripts.build_live_release_summary")
    pack_path = tmp_path / "critical_behavior.json"
    _write_pack(pack_path, scenario_keys=["requester_create"])
    _write_complete_manifest(
        tmp_path / "live" / "old-pass",
        scenario_key="requester_create",
        commit="oldcommit",
        environment="stand",
        release_run_id="old-release",
        expected_schema_head="schema-a",
        status="pass",
    )
    _write_complete_manifest(
        tmp_path / "live" / "current-fail",
        scenario_key="requester_create",
        commit="abc1234",
        environment="stand",
        release_run_id="release-run-1",
        expected_schema_head="schema-a",
        status="fail",
    )

    summary = summary_builder.build_summary(
        pack_path=pack_path,
        live_root=tmp_path / "live",
        commit="abc1234",
        environment="stand",
        release_run_id="release-run-1",
        expected_schema_head="schema-a",
    )

    assert summary["status"] == "fail"
    assert summary["release_context"] == {
        "commit": "abc1234",
        "environment": "stand",
        "release_run_id": "release-run-1",
        "expected_schema_head": "schema-a",
    }
    assert summary["coverage"]["passed_scenario_keys"] == []
    assert summary["coverage"]["failed_scenario_keys"] == ["requester_create"]
    assert summary["coverage"]["missing_scenario_keys"] == []
    assert len(summary["live_manifests"]) == 1
    assert Path(summary["live_manifests"][0]["path"]).parts[-2:] == ("current-fail", "manifest.json")
