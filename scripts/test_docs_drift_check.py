import argparse
import json

import pytest

import scripts.docs_drift_check as drift


def test_repo_path_normalizes_windows_separators() -> None:
    assert drift.repo_path(r"docs\AGENTS.md") == "docs/AGENTS.md"


def test_main_fails_when_code_changes_lack_documentation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(drift, "parse_args", lambda: argparse.Namespace(base=None, staged=False, paths=None, json=False))
    monkeypatch.setattr(drift, "collect_changed_paths", lambda **kwargs: [drift.ChangedPath(status="M", path="server/routes.py")])

    assert drift.main() == 1
    assert "require at least one documentation" in capsys.readouterr().out


def test_main_accepts_code_change_with_codemapping(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(drift, "parse_args", lambda: argparse.Namespace(base=None, staged=False, paths=None, json=True))
    monkeypatch.setattr(
        drift,
        "collect_changed_paths",
        lambda **kwargs: [
            drift.ChangedPath(status="M", path="server/routes.py"),
            drift.ChangedPath(status="M", path="server/docs/CODEMAP.md"),
        ],
    )

    assert drift.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"status": "ok", "message": "documentation coverage present", "failures": []}
