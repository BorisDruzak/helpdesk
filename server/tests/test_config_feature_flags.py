from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1]


def _read_flags(env_overrides: dict[str, str] | None = None) -> dict[str, bool]:
    env = os.environ.copy()
    env.pop("WEB_SELF_REGISTRATION_ENABLED", None)
    env.pop("PROFILE_COMPLETION_REQUIRED", None)
    env.update(env_overrides or {})
    script = (
        "import json, config; "
        "print(json.dumps({"
        "'web_self_registration_enabled': config.WEB_SELF_REGISTRATION_ENABLED, "
        "'profile_completion_required': config.PROFILE_COMPLETION_REQUIRED"
        "}, sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=SERVER_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.no_db
def test_web_self_registration_is_disabled_by_default():
    assert _read_flags()["web_self_registration_enabled"] is False


@pytest.mark.no_db
def test_web_self_registration_can_be_enabled_by_env():
    assert _read_flags({"WEB_SELF_REGISTRATION_ENABLED": "true"})["web_self_registration_enabled"] is True


@pytest.mark.no_db
def test_profile_completion_is_required_by_default():
    assert _read_flags()["profile_completion_required"] is True


@pytest.mark.no_db
def test_profile_completion_can_be_made_advisory_by_env():
    assert _read_flags({"PROFILE_COMPLETION_REQUIRED": "false"})["profile_completion_required"] is False
