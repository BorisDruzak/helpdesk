"""Tests for the immutable Endpoint provider lock validator."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def test_validator_accepts_only_matching_provider_head_and_openapi_bytes(
    tmp_path: Path,
) -> None:
    provider_root = tmp_path / "provider"
    openapi = provider_root / "contracts" / "openapi" / "endpoint-platform-v1.yaml"
    openapi.parent.mkdir(parents=True)
    raw_openapi = b"openapi: 3.1.0\ninfo:\n  title: test\n"
    openapi.write_bytes(raw_openapi)
    _run("git", "init", cwd=provider_root)
    _run("git", "config", "user.email", "tests@example.invalid", cwd=provider_root)
    _run("git", "config", "user.name", "Contract test", cwd=provider_root)
    _run("git", "add", ".", cwd=provider_root)
    _run("git", "commit", "-m", "test provider", cwd=provider_root)
    provider_commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=provider_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock = tmp_path / "endpoint_contract.lock.json"
    lock_data = {
        "schema_version": "endpoint_contract_lock_v1",
        "provider_repository": "BorisDruzak/endpoint_platform",
        "provider_commit": provider_commit,
        "openapi_path": "contracts/openapi/endpoint-platform-v1.yaml",
        "openapi_sha256": hashlib.sha256(raw_openapi).hexdigest(),
    }
    lock.write_text(json.dumps(lock_data), encoding="utf-8")

    # A Windows checkout can materialize the same committed text with CRLF.
    # The immutable lock must describe the provider's Git blob, not local EOLs.
    openapi.write_bytes(raw_openapi.replace(b"\n", b"\r\n"))

    completed = subprocess.run(
        (
            sys.executable,
            "scripts/validate_endpoint_contract_lock.py",
            "--lock",
            str(lock),
            "--provider-root",
            str(provider_root),
        ),
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr

    lock.write_text(
        json.dumps({**lock_data, "openapi_sha256": "0" * 64}),
        encoding="utf-8",
    )
    mismatched_digest = subprocess.run(
        (
            sys.executable,
            "scripts/validate_endpoint_contract_lock.py",
            "--lock",
            str(lock),
            "--provider-root",
            str(provider_root),
        ),
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert mismatched_digest.returncode == 1
    assert "OpenAPI digest" in mismatched_digest.stderr
