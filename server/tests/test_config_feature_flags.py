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


def _read_knowledge_config_surface() -> dict[str, object]:
    env = os.environ.copy()
    env.pop("KNOWLEDGE_PORT_MODE", None)
    retired_settings = (
        "KNOWLEDGE_REMOTE_IMPORT_ENABLED",
        "KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS",
        "KNOWLEDGE_REMOTE_IMPORT_MAX_BYTES",
        "KNOWLEDGE_REMOTE_IMPORT_TIMEOUT_SECONDS",
        "KNOWLEDGE_REMOTE_IMPORT_MAX_GIT_FILES",
    )
    script = (
        "import json, config; "
        f"retired_settings = {retired_settings!r}; "
        "print(json.dumps({"
        "'knowledge_port_mode': config.KNOWLEDGE_PORT_MODE, "
        "'retired_settings': [name for name in retired_settings if hasattr(config, name)]"
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


def _read_registry_timeout(env_overrides: dict[str, str]) -> float:
    env = os.environ.copy()
    env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.REGISTRY_EXTERNAL_TIMEOUT_SECONDS)"],
        cwd=SERVER_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


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


@pytest.mark.no_db
def test_config_keeps_external_knowledge_port_mode_without_local_import_settings():
    assert _read_knowledge_config_surface() == {
        "knowledge_port_mode": "unavailable",
        "retired_settings": [],
    }


@pytest.mark.no_db
def test_registry_external_timeout_rejects_non_finite_values() -> None:
    assert _read_registry_timeout({"REGISTRY_EXTERNAL_TIMEOUT_SECONDS": "NaN"}) == 2.0
