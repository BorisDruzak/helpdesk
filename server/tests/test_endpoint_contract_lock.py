"""Tests for the immutable Endpoint provider lock validator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validate_endpoint_contract_lock import validate


pytestmark = pytest.mark.no_db


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _output(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_lock(path: Path, values: dict[str, str]) -> None:
    path.write_text(json.dumps(values), encoding="utf-8")


def _provider_with_locked_openapi(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, str], bytes]:
    provider_root = tmp_path / "provider"
    openapi = provider_root / "contracts" / "openapi" / "endpoint-platform-v1.yaml"
    openapi.parent.mkdir(parents=True)
    raw_openapi = b"openapi: 3.1.0\ninfo:\n  title: test\n"
    openapi.write_bytes(raw_openapi)
    (provider_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (provider_root / ".gitattributes").write_text(
        "contracts/openapi/*.yaml text eol=crlf\n", encoding="utf-8"
    )
    _run("git", "init", cwd=provider_root)
    _run("git", "config", "user.email", "tests@example.invalid", cwd=provider_root)
    _run("git", "config", "user.name", "Contract test", cwd=provider_root)
    _run("git", "add", ".", cwd=provider_root)
    _run("git", "commit", "-m", "test provider", cwd=provider_root)
    _run("git", "config", "core.autocrlf", "true", cwd=provider_root)
    _run(
        "git",
        "checkout",
        "-f",
        "HEAD",
        "--",
        "contracts/openapi/endpoint-platform-v1.yaml",
        cwd=provider_root,
    )
    assert _output("git", "status", "--porcelain", cwd=provider_root) == ""
    lock_data = {
        "schema_version": "endpoint_contract_lock_v1",
        "provider_repository": "BorisDruzak/endpoint_platform",
        "provider_commit": _output("git", "rev-parse", "HEAD", cwd=provider_root),
        "openapi_path": "contracts/openapi/endpoint-platform-v1.yaml",
        "openapi_sha256": hashlib.sha256(raw_openapi).hexdigest(),
    }
    lock = tmp_path / "endpoint_contract.lock.json"
    _write_lock(lock, lock_data)
    return provider_root, lock, lock_data, raw_openapi


def test_validator_accepts_clean_matching_provider_and_crlf_checkout(
    tmp_path: Path,
) -> None:
    provider_root, lock, _, _ = _provider_with_locked_openapi(tmp_path)

    validate(lock_path=lock, provider_root=provider_root)


def test_validator_rejects_unexpected_provider_repository(tmp_path: Path) -> None:
    provider_root, lock, lock_data, _ = _provider_with_locked_openapi(tmp_path)
    _write_lock(lock, {**lock_data, "provider_repository": "other/provider"})

    with pytest.raises(ValueError, match="provider repository"):
        validate(lock_path=lock, provider_root=provider_root)


def test_validator_rejects_wrong_provider_head(tmp_path: Path) -> None:
    provider_root, lock, _, _ = _provider_with_locked_openapi(tmp_path)
    (provider_root / "new-file.txt").write_text("next commit\n", encoding="utf-8")
    _run("git", "add", "new-file.txt", cwd=provider_root)
    _run("git", "commit", "-m", "next provider commit", cwd=provider_root)

    with pytest.raises(ValueError, match="HEAD"):
        validate(lock_path=lock, provider_root=provider_root)


@pytest.mark.parametrize("change_kind", ("modified", "staged", "untracked"))
def test_validator_rejects_dirty_provider_checkout(
    tmp_path: Path,
    change_kind: str,
) -> None:
    provider_root, lock, _, _ = _provider_with_locked_openapi(tmp_path)
    changed_path = provider_root / (
        "untracked.txt" if change_kind == "untracked" else "tracked.txt"
    )
    changed_path.write_text("dirty\n", encoding="utf-8")
    if change_kind == "staged":
        _run("git", "add", "tracked.txt", cwd=provider_root)

    with pytest.raises(ValueError, match="clean"):
        validate(lock_path=lock, provider_root=provider_root)


def test_dirty_provider_checkout_is_rejected_before_acceptance_import(
    tmp_path: Path,
) -> None:
    provider_root, _, _, _ = _provider_with_locked_openapi(tmp_path)
    (provider_root / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "server/tests/acceptance/test_endpoint_operations_v1_acceptance.py",
            "--collect-only",
            "-q",
        ),
        cwd=Path.cwd(),
        env=os.environ | {"ENDPOINT_PLATFORM_REPO": str(provider_root)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    output = completed.stdout + completed.stderr
    assert "provider checkout must be clean" in output
    assert "ModuleNotFoundError" not in output


@pytest.mark.parametrize(
    "lock_overrides",
    (
        {"openapi_sha256": "0" * 64},
        {"openapi_path": "../endpoint-platform-v1.yaml"},
    ),
)
def test_validator_rejects_wrong_digest_and_path_traversal(
    tmp_path: Path,
    lock_overrides: dict[str, str],
) -> None:
    provider_root, lock, lock_data, _ = _provider_with_locked_openapi(tmp_path)
    _write_lock(lock, {**lock_data, **lock_overrides})

    with pytest.raises(ValueError):
        validate(lock_path=lock, provider_root=provider_root)
