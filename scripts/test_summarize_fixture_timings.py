import importlib
import json
from pathlib import Path


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def test_summarize_artifact_dir_groups_fixture_phase_stats(tmp_path):
    summarize = importlib.import_module("scripts.summarize_fixture_timings")
    artifact_dir = tmp_path / "artifacts" / "ci" / "abc123"
    _write_jsonl(
        artifact_dir / "fixture-timings" / "server_pytest_db_web_api.jsonl",
        [
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 1.0},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 2.0},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 3.0},
            {"fixture": "test_app", "phase": "setup", "duration_seconds": 0.5},
        ],
    )
    _write_jsonl(
        artifact_dir / "fixture-timings" / "server_pytest_agent_ws.jsonl",
        [
            {"fixture": "test_agent", "phase": "setup", "duration_seconds": 10.0},
            {"fixture": "test_agent", "phase": "teardown", "duration_seconds": 4.0},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 4.0},
        ],
    )

    summary = summarize.summarize_artifact_dir(artifact_dir)

    cleanup_setup = summary["fixtures"]["cleanup_db"]["setup"]
    assert {key: value for key, value in cleanup_setup.items() if key != "budget"} == {
        "count": 4,
        "total_seconds": 10.0,
        "avg_seconds": 2.5,
        "p50_seconds": 2.5,
        "p95_seconds": 4.0,
        "max_seconds": 4.0,
    }
    assert summary["fixtures"]["test_app"]["setup"]["count"] == 1
    assert summary["fixtures"]["test_agent"]["setup"]["total_seconds"] == 10.0
    assert summary["fixtures"]["test_agent"]["teardown"]["total_seconds"] == 4.0
    assert summary["record_count"] == 7
    assert (artifact_dir / "fixture-timings-summary.json").exists()


def test_summarize_artifact_dir_adds_cleanup_profile_breakdown(tmp_path):
    summarize = importlib.import_module("scripts.summarize_fixture_timings")
    artifact_dir = tmp_path / "artifacts" / "ci" / "abc123"
    _write_jsonl(
        artifact_dir / "fixture-timings" / "server_pytest_db_web_api.jsonl",
        [
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 1.0, "profile": "full"},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 2.0, "profile": "tickets"},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 3.0, "profile": "tickets"},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 4.0},
        ],
    )

    summary = summarize.summarize_artifact_dir(artifact_dir)

    assert summary["fixtures"]["cleanup_db"]["setup"]["count"] == 4
    assert summary["fixtures"]["cleanup_db:full"]["setup"]["total_seconds"] == 1.0
    assert summary["fixtures"]["cleanup_db:tickets"]["setup"] == {
        "count": 2,
        "total_seconds": 5.0,
        "avg_seconds": 2.5,
        "p50_seconds": 2.5,
        "p95_seconds": 3.0,
        "max_seconds": 3.0,
    }


def test_main_prints_summary_table_and_ignores_bad_records(tmp_path, capsys):
    summarize = importlib.import_module("scripts.summarize_fixture_timings")
    artifact_dir = tmp_path / "artifacts" / "ci" / "abc123"
    timings_path = artifact_dir / "fixture-timings" / "server_pytest_db_web_api.jsonl"
    timings_path.parent.mkdir(parents=True)
    timings_path.write_text(
        "\n".join(
            [
                json.dumps({"fixture": "run_migrations", "phase": "setup", "duration_seconds": 5.0}),
                "{bad json",
                json.dumps({"fixture": "missing_duration", "phase": "setup"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = summarize.main([str(artifact_dir)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "run_migrations" in output
    assert "setup" in output
    assert "total" in output
    summary = json.loads((artifact_dir / "fixture-timings-summary.json").read_text(encoding="utf-8"))
    assert summary["record_count"] == 1
    assert summary["invalid_record_count"] == 2


def test_summarize_artifact_dir_flags_fixture_budget_violations(tmp_path):
    summarize = importlib.import_module("scripts.summarize_fixture_timings")
    artifact_dir = tmp_path / "artifacts" / "ci" / "abc123"
    _write_jsonl(
        artifact_dir / "fixture-timings" / "server_pytest_db_web_api.jsonl",
        [
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 1.0},
            {"fixture": "cleanup_db", "phase": "setup", "duration_seconds": 45.0},
            {"fixture": "test_app", "phase": "setup", "duration_seconds": 0.5},
        ],
    )

    summary = summarize.summarize_artifact_dir(artifact_dir)

    assert summary["budget_status"] == "fail"
    assert summary["fixtures"]["cleanup_db"]["setup"]["budget"] == {
        "p95_seconds": 30.0,
        "max_seconds": 45.0,
    }
    assert summary["budget_violations"] == [
        {
            "fixture": "cleanup_db",
            "phase": "setup",
            "metric": "p95_seconds",
            "actual_seconds": 45.0,
            "budget_seconds": 30.0,
        }
    ]


def test_main_can_enforce_fixture_timing_budget(tmp_path):
    summarize = importlib.import_module("scripts.summarize_fixture_timings")
    artifact_dir = tmp_path / "artifacts" / "ci" / "abc123"
    _write_jsonl(
        artifact_dir / "fixture-timings" / "server_pytest_db_web_api.jsonl",
        [{"fixture": "test_agent", "phase": "setup", "duration_seconds": 95.0}],
    )

    exit_code = summarize.main([str(artifact_dir), "--enforce-budget"])

    assert exit_code == 1
    summary = json.loads((artifact_dir / "fixture-timings-summary.json").read_text(encoding="utf-8"))
    assert summary["budget_status"] == "fail"
