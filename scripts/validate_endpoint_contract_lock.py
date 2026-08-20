"""Validate the immutable Endpoint provider checkout used only by acceptance tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import NoReturn


_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "provider_repository",
        "provider_commit",
        "openapi_path",
        "openapi_sha256",
    }
)
_SHA256_LENGTH = 64


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _load_lock(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _fail(f"invalid Endpoint contract lock: {error.__class__.__name__}")
    if not isinstance(value, dict) or set(value) != _REQUIRED_KEYS:
        _fail("Endpoint contract lock has an unexpected shape")
    if value.get("schema_version") != "endpoint_contract_lock_v1":
        _fail("Endpoint contract lock has an unsupported schema version")
    if not all(isinstance(item, str) and item for item in value.values()):
        _fail("Endpoint contract lock fields must be non-empty strings")
    if len(value["provider_commit"]) != 40 or any(
        char not in "0123456789abcdef" for char in value["provider_commit"].lower()
    ):
        _fail("Endpoint contract lock provider commit must be a full SHA-1")
    if len(value["openapi_sha256"]) != _SHA256_LENGTH or any(
        char not in "0123456789abcdef" for char in value["openapi_sha256"].lower()
    ):
        _fail("Endpoint contract lock OpenAPI digest must be SHA-256")
    return value


def _provider_head(provider_root: Path) -> str:
    try:
        top_level = subprocess.run(
            ("git", "-C", str(provider_root), "rev-parse", "--show-toplevel"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if Path(top_level).resolve() != provider_root.resolve():
            _fail("provider root must be the Git checkout root")
        return subprocess.run(
            ("git", "-C", str(provider_root), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().lower()
    except (OSError, subprocess.CalledProcessError) as error:
        _fail(f"provider checkout is unavailable: {error.__class__.__name__}")


def validate(*, lock_path: Path, provider_root: Path) -> None:
    """Reject a provider checkout that differs from its exact consumer lock."""
    lock = _load_lock(lock_path)
    if _provider_head(provider_root) != lock["provider_commit"].lower():
        _fail("provider checkout HEAD does not match Endpoint contract lock")

    relative_openapi = Path(lock["openapi_path"])
    if relative_openapi.is_absolute() or ".." in relative_openapi.parts:
        _fail("Endpoint contract lock OpenAPI path must be relative and contained")
    openapi_path = (provider_root / relative_openapi).resolve()
    if provider_root.resolve() not in openapi_path.parents:
        _fail("Endpoint contract lock OpenAPI path escapes provider root")
    try:
        actual_digest = hashlib.sha256(openapi_path.read_bytes()).hexdigest()
    except OSError as error:
        _fail(f"locked Endpoint OpenAPI is unavailable: {error.__class__.__name__}")
    if actual_digest != lock["openapi_sha256"].lower():
        _fail("provider OpenAPI digest does not match Endpoint contract lock")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(lock_path=args.lock, provider_root=args.provider_root)
    except ValueError as error:
        print(f"Endpoint contract validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
