import argparse
from pathlib import Path

import pytest

import scripts.release_candidate_preflight as preflight


def make_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "workspace": Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
        "commit": None,
        "allow_local_dirty": False,
        "skip_webapp_bundle": False,
        "environment": "stand",
        "release_run_id": None,
        "expected_schema_head": None,
        "live_summary": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_dirty_message_explains_freeze_invalidation() -> None:
    message = preflight.build_dirty_message([" M scripts/release_server_to_remote.py"])

    assert "committing after green CI invalidates the artifact" in message
    assert "--allow-local-dirty" in message


def test_release_relevant_dirty_entries_ignores_generated_artifacts() -> None:
    assert preflight.release_relevant_dirty_entries(
        [
            "?? artifacts/ui_audit_2026-05-19/report.md",
            " M scripts/release_server_to_remote.py",
        ]
    ) == [" M scripts/release_server_to_remote.py"]


def test_main_refuses_dirty_workspace_before_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "parse_args", lambda: make_args())
    monkeypatch.setattr(preflight, "detect_commit", lambda workspace, commit=None: "abc123")
    monkeypatch.setattr(preflight, "git_status_short", lambda workspace: [" M docs/LOCAL_WORKFLOW.md"])

    with pytest.raises(SystemExit) as exc_info:
        preflight.main()

    assert "uncommitted local changes" in str(exc_info.value)
    assert "invalidates the artifact" in str(exc_info.value)


def test_main_checks_exact_ci_and_bundle_for_clean_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[str, Path, str, str | None, str | None, str | None]] = []

    monkeypatch.setattr(preflight, "parse_args", lambda: make_args())
    monkeypatch.setattr(preflight, "detect_commit", lambda workspace, commit=None: "abc123")
    monkeypatch.setattr(preflight, "git_status_short", lambda workspace: [])
    monkeypatch.setattr(
        preflight,
        "require_green_ci_artifact",
        lambda workspace, commit: recorded.append(("ci", workspace, commit, None, None, None)) or workspace / "summary.json",
    )
    monkeypatch.setattr(
        preflight,
        "require_webapp_bundle_artifact",
        lambda workspace, commit: recorded.append(("bundle", workspace, commit, None, None, None)) or workspace / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(
        preflight,
        "require_live_release_summary",
        lambda workspace, commit, environment, **kwargs: recorded.append(
            (
                "live",
                workspace,
                commit,
                environment,
                kwargs.get("release_run_id"),
                kwargs.get("expected_schema_head"),
            )
        )
        or workspace / "artifacts" / "live" / "release-summary.json",
    )

    preflight.main()

    workspace = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
    assert recorded == [
        ("ci", workspace, "abc123", None, None, None),
        ("bundle", workspace, "abc123", None, None, None),
        ("live", workspace, "abc123", "stand", None, None),
    ]


def test_git_status_short_returns_non_empty_lines(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Result:
        stdout = " M a.py\n\n?? b.py\n"

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
    ) -> Result:
        assert command[:2] == ["git", "status"]
        assert cwd == tmp_path
        return Result()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert preflight.git_status_short(tmp_path) == [" M a.py", "?? b.py"]
