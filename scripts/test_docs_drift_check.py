import argparse
import json

import pytest

import scripts.docs_drift_check as drift
from scripts.navigation_catalog import ChangedPath, DriftRule


def test_is_tracked_artifact_accepts_harness_files() -> None:
    assert drift.is_tracked_artifact("docs/QUICK_LOOKUP.md")
    assert drift.is_tracked_artifact(".cursor/rules/navigation-tools.mdc")
    assert drift.is_tracked_artifact(".cursor/skills/pc-client-release/SKILL.md")
    assert drift.is_tracked_artifact(".codex/config.toml")
    assert drift.is_tracked_artifact("PLANS.md")


def test_main_accepts_skill_update_as_required_artifact(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        drift,
        "parse_args",
        lambda: argparse.Namespace(base=None, staged=False, paths=None, json=False),
    )
    monkeypatch.setattr(
        drift,
        "collect_changed_paths",
        lambda **kwargs: [
            ChangedPath(status="M", path="scripts/verify_workspace.py"),
            ChangedPath(status="M", path=".cursor/skills/pc-client-release/SKILL.md"),
        ],
    )
    monkeypatch.setattr(
        drift,
        "iter_triggered_drift_rules",
        lambda changes: [
            (
                DriftRule(
                    key="workflow_harness",
                    title="Workflow harness changed",
                    reason="Harness docs must stay aligned.",
                    required_docs=(".cursor/skills/pc-client-release/SKILL.md",),
                ),
                [ChangedPath(status="M", path="scripts/verify_workspace.py")],
            )
        ],
    )

    assert drift.main() == 0
    assert "docs_drift_check: ok." in capsys.readouterr().out


def test_main_json_failure_reports_required_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        drift,
        "parse_args",
        lambda: argparse.Namespace(base=None, staged=False, paths=None, json=True),
    )
    monkeypatch.setattr(
        drift,
        "collect_changed_paths",
        lambda **kwargs: [ChangedPath(status="M", path="scripts/navigation_catalog.py")],
    )
    monkeypatch.setattr(
        drift,
        "iter_triggered_drift_rules",
        lambda changes: [
            (
                DriftRule(
                    key="navigation_harness",
                    title="Navigation harness changed",
                    reason="Navigation docs must stay aligned.",
                    required_docs=("AGENTS.md", ".cursor/rules/navigation-tools.mdc"),
                ),
                [ChangedPath(status="M", path="scripts/navigation_catalog.py")],
            )
        ],
    )

    assert drift.main() == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["failures"][0]["rule"] == "navigation_harness"
    assert ".cursor/rules/navigation-tools.mdc" in payload["failures"][0]["required_artifacts"]


def test_main_fails_when_required_all_artifacts_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        drift,
        "parse_args",
        lambda: argparse.Namespace(base=None, staged=False, paths=None, json=False),
    )
    monkeypatch.setattr(
        drift,
        "collect_changed_paths",
        lambda **kwargs: [
            ChangedPath(status="M", path="server/modules/handlers.py"),
            ChangedPath(status="M", path="server/docs/MODULES_API.md"),
        ],
    )
    monkeypatch.setattr(
        drift,
        "iter_triggered_drift_rules",
        lambda changes: [
            (
                DriftRule(
                    key="modules",
                    title="Module pipeline changed",
                    reason="Module docs and navigation must stay aligned.",
                    required_docs=("server/docs/MODULES_API.md",),
                    required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
                ),
                [ChangedPath(status="M", path="server/modules/handlers.py")],
            )
        ],
    )

    assert drift.main() == 1
    output = capsys.readouterr().out
    assert "Required artifacts missing" in output
    assert "scripts/navigation_catalog.py" in output
