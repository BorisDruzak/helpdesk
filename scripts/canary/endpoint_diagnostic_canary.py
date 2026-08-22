"""Fail-closed manifest gate for one Helpdesk Endpoint diagnostic canary."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.canary.evidence_models import CanaryEvidenceError, reject_sensitive_values


class CanaryManifestError(ValueError):
    """The requested canary lacks an exact non-production authorization."""


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_TOP_LEVEL = frozenset({"schema_version", "environment", "revisions", "targets", "baseline", "execution", "rollback", "result"})
_APPLY_ENVIRONMENT_KEYS = frozenset({
    "CANARY_APPROVED", "CANARY_ENVIRONMENT", "CANARY_CHANGE_ID", "CANARY_ENDPOINT_HOST",
    "CANARY_HELPDESK_HOST", "CANARY_AGENT_HOST", "CANARY_ENDPOINT_DEVICE_ID",
    "CANARY_HELPDESK_TICKET_ID", "CANARY_EVIDENCE_ROOT",
})


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CanaryManifestError(f"{name} must be an object")
    return value


def _https_host(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise CanaryManifestError(f"{name} must be an HTTPS origin")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise CanaryManifestError(f"{name} must be an HTTPS origin")
    return parsed.hostname


def _required_string(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CanaryManifestError(f"missing {key}")
    return value


def validate_manifest(
    manifest: Mapping[str, Any], *, environment: str, apply: bool, env: Mapping[str, str]
) -> dict[str, object]:
    """Validate scope and approval before any canary operation can be issued."""
    try:
        reject_sensitive_values(manifest)
    except CanaryEvidenceError as error:
        raise CanaryManifestError(str(error)) from error
    if set(manifest) != _REQUIRED_TOP_LEVEL:
        raise CanaryManifestError("manifest top-level schema is invalid")
    if manifest.get("schema_version") != "endpoint_diagnostic_canary_v1":
        raise CanaryManifestError("unsupported manifest schema")
    if environment != "staging":
        raise CanaryManifestError("only staging environment is permitted")
    environment_data = _mapping(manifest["environment"], name="environment")
    targets = _mapping(manifest["targets"], name="targets")
    execution = _mapping(manifest["execution"], name="execution")
    result = _mapping(manifest["result"], name="result")
    if environment_data.get("environment_class") != "staging":
        raise CanaryManifestError("manifest is not staging")
    if result.get("production_changed") is not False:
        raise CanaryManifestError("manifest must state production_changed=false")
    idempotency_hash = execution.get("caller_idempotency_key_hash")
    if not isinstance(idempotency_hash, str) or not _SHA256.fullmatch(idempotency_hash):
        raise CanaryManifestError("caller idempotency key must be a SHA-256 hash")
    endpoint_host = _https_host(targets.get("endpoint_origin"), name="endpoint_origin")
    helpdesk_host = _https_host(targets.get("helpdesk_origin"), name="helpdesk_origin")
    change_id = _required_string(environment_data, "change_id")
    agent_host = _required_string(targets, "agent_host_safe_label")
    device_id = _required_string(targets, "endpoint_device_id")
    ticket_id = _required_string(targets, "helpdesk_ticket_id")
    if apply:
        missing = [key for key in _APPLY_ENVIRONMENT_KEYS if not env.get(key)]
        if missing:
            raise CanaryManifestError(f"missing canary approval variable: {sorted(missing)[0]}")
        expected = {
            "CANARY_APPROVED": "true", "CANARY_ENVIRONMENT": "staging",
            "CANARY_CHANGE_ID": change_id, "CANARY_ENDPOINT_HOST": endpoint_host,
            "CANARY_HELPDESK_HOST": helpdesk_host, "CANARY_AGENT_HOST": agent_host,
            "CANARY_ENDPOINT_DEVICE_ID": device_id, "CANARY_HELPDESK_TICKET_ID": ticket_id,
        }
        if any(env.get(key) != value for key, value in expected.items()):
            raise CanaryManifestError("canary approval variables do not match manifest")
    return {"environment_class": "staging", "apply": apply, "endpoint_host": endpoint_host, "helpdesk_host": helpdesk_host}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight", help="validate only; never issues an operation")
    preflight.add_argument("--manifest", required=True, type=Path)
    preflight.add_argument("--environment", required=True)
    preflight.add_argument("--apply", action="store_true", help="validate mutable-stage authority only")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = validate_manifest(manifest, environment=args.environment, apply=args.apply, env=os.environ)
    except (OSError, json.JSONDecodeError, CanaryManifestError) as error:
        print(f"canary preflight failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "preflight_ready", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
