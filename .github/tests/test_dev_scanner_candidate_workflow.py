"""Exercise candidate admission with synthetic GitHub responses, without networking."""
from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
BRANCH = "codex/guided-request-studio-v2"
REPOSITORY = "BorisDruzak/helpdesk"


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/dev-scanner-quality.yml").read_text(encoding="utf-8"))


def candidate():
    return workflow()["jobs"]["quality_candidate"]


def response():
    return {
        "number": 41, "state": "open", "draft": True,
        "head": {"ref": BRANCH, "sha": SHA, "repo": {"full_name": REPOSITORY}},
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
    }


def run_guard(tmp_path, payload, *, network_allowed=True, **overrides):
    script = candidate()["steps"][0]["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    environment = {
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": f"refs/heads/{BRANCH}",
        "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_SHA": SHA,
        "GITHUB_JOB": "quality_candidate", "GH_TOKEN": "synthetic-fixture",
        "GITHUB_WORKSPACE": str(tmp_path),
    }
    environment.update(overrides)
    with patch.dict(os.environ, environment, clear=True), patch(
        "urllib.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()),
        side_effect=None if network_allowed else AssertionError("Unexpected network request"),
    ) as request:
        exec(compile(script, "candidate-admission", "exec"), {})
    return request


def test_main_mode_and_shared_gates_remain_separate():
    jobs = workflow()["jobs"]
    main = jobs["quality"]
    guarded = candidate()
    assert main["if"] == "github.repository == 'BorisDruzak/helpdesk' && github.ref == 'refs/heads/main'"
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in main["steps"][0]["run"]
    assert "workflow_dispatch" in guarded["if"] and f"refs/heads/{BRANCH}" in guarded["if"]
    assert guarded["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert guarded["runs-on"] == main["runs-on"]
    assert guarded["env"] == main["env"]
    assert guarded["timeout-minutes"] == main["timeout-minutes"]
    for name in ("Canonical backend coverage", "Generate frontend coverage", "Semgrep SAST and secrets baseline"):
        assert next(step for step in guarded["steps"] if step["name"] == name) == next(
            step for step in main["steps"] if step["name"] == name
        )
    scanner = next(step for step in guarded["steps"] if step.get("id") == "sonar")
    previous = guarded["steps"][guarded["steps"].index(scanner) - 1]
    assert previous == guarded["steps"][0]
    for parameter in ("key=41", f"branch={BRANCH}", "base=main"):
        assert f"-Dsonar.pullrequest.{parameter}" in scanner["run"]
    assert "-Dsonar.qualitygate.wait=true" in scanner["run"]
    main_scanner = next(step for step in main["steps"] if step.get("id") == "sonar")
    normalized = scanner["run"]
    for parameter in ("key=41", f"branch={BRANCH}", "base=main"):
        normalized = normalized.replace(f"-Dsonar.pullrequest.{parameter}             ", "")
    assert normalized == main_scanner["run"]


def test_exact_draft_head_is_admitted(tmp_path):
    request = run_guard(tmp_path, response())
    assert request.call_args.args[0].full_url == "https://api.github.com/repos/BorisDruzak/helpdesk/pulls/41"
    assert request.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize("path,value", [
    (("number",), 42), (("state",), "closed"), (("draft",), False),
    (("head", "ref"), "main"), (("head", "sha"), "b" * 40),
    (("head", "repo", "full_name"), "foreign/helpdesk"),
    (("base", "ref"), "release"), (("base", "repo", "full_name"), "foreign/helpdesk"),
    (("head", "repo"), None),
])
def test_ineligible_pull_request_is_rejected(tmp_path, path, value):
    payload = copy.deepcopy(response())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(SystemExit, match="Candidate PR admission rejected"):
        run_guard(tmp_path, payload)


@pytest.mark.parametrize("key,value", [
    ("GITHUB_EVENT_NAME", "pull_request_target"), ("GITHUB_REF", "refs/heads/main"),
    ("GITHUB_REPOSITORY", "foreign/helpdesk"), ("GITHUB_JOB", "quality"),
])
def test_unapproved_dispatch_is_rejected_before_network(tmp_path, key, value):
    with pytest.raises(SystemExit, match="Candidate dispatch rejected"):
        run_guard(tmp_path, response(), network_allowed=False, **{key: value})
