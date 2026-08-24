"""Fail-closed manifest gate for one Helpdesk Endpoint diagnostic canary."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.canary.evidence_models import CanaryEvidenceError, reject_sensitive_values


class CanaryManifestError(ValueError):
    """The requested canary lacks an exact non-production authorization."""


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_TOP_LEVEL = frozenset({"schema_version", "environment", "revisions", "targets", "baseline", "execution", "rollback", "result"})
_V2_TOP_LEVEL = _REQUIRED_TOP_LEVEL | frozenset({"agent"})
_V2_AGENT_KEYS = frozenset({
    "platform", "host_safe_label", "device_id", "service_name", "updater_service_name",
    "source_revision", "version", "package_name", "package_sha256",
})
_APPLY_ENVIRONMENT_KEYS = frozenset({
    "CANARY_APPROVED", "CANARY_ENVIRONMENT", "CANARY_CHANGE_ID", "CANARY_ENDPOINT_HOST",
    "CANARY_HELPDESK_HOST", "CANARY_AGENT_HOST", "CANARY_ENDPOINT_DEVICE_ID",
    "CANARY_HELPDESK_TICKET_ID", "CANARY_EVIDENCE_ROOT",
    "CANARY_AGENT_PLATFORM", "CANARY_WINDOWS_SERVICE", "CANARY_WINDOWS_UPDATER_SERVICE",
    "CANARY_WINDOWS_MSI_VERSION", "CANARY_WINDOWS_MSI_SHA256", "CANARY_WINDOWS_SOURCE_REVISION",
})
_STAGING_PROOF_KEYS = frozenset({
    "schema_version", "environment_class", "endpoint_host", "helpdesk_host", "agent_host_safe_label",
    "dedicated_windows_vm", "production_identifiers",
    "endpoint_database_revision", "helpdesk_database_revision",
})
_OPTIONAL_STAGING_PROOF_KEYS = frozenset({"snapshot_or_recovery_point"})


@dataclass(frozen=True)
class CanaryHttpAdapter:
    """Small transport seam for the existing Helpdesk routes only."""

    request: Any | None = None
    authorization: str | None = None

    def call(self, *, method: str, url: str, payload: Mapping[str, object] | None, headers: Mapping[str, str]) -> Mapping[str, Any]:
        if self.request is not None:
            result = self.request(method=method, url=url, payload=payload, headers=dict(headers))
            if not isinstance(result, Mapping):
                raise CanaryManifestError("canary route returned an invalid JSON object")
            return result
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = {"Accept": "application/json", **headers}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if self.authorization:
            request_headers["Authorization"] = self.authorization
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:  # nosec B310: manifest permits HTTPS origins only
                data = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise CanaryManifestError(f"canary route request failed: {type(error).__name__}") from error
        if not isinstance(data, Mapping):
            raise CanaryManifestError("canary route returned an invalid JSON object")
        return data


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


def _validate_v2_agent(manifest: Mapping[str, Any], *, targets: Mapping[str, Any]) -> str:
    agent = _mapping(manifest.get("agent"), name="agent")
    if set(agent) != _V2_AGENT_KEYS:
        raise CanaryManifestError("agent schema is invalid")
    if agent.get("platform") != "windows_amd64":
        raise CanaryManifestError("Windows agent platform is invalid")
    if agent.get("service_name") != "EndpointAgent":
        raise CanaryManifestError("Windows service name is invalid")
    if agent.get("updater_service_name") != "EndpointAgentUpdater":
        raise CanaryManifestError("Windows updater service name is invalid")
    for key in ("host_safe_label", "device_id", "source_revision", "version", "package_name"):
        _required_string(agent, key)
    package_sha256 = agent.get("package_sha256")
    if not isinstance(package_sha256, str) or not _SHA256.fullmatch(package_sha256):
        raise CanaryManifestError("Windows package SHA-256 is invalid")
    if agent["device_id"] != targets.get("endpoint_device_id"):
        raise CanaryManifestError("Windows device does not match target")
    if agent["host_safe_label"] != targets.get("agent_host_safe_label"):
        raise CanaryManifestError("Windows host does not match target")
    return "windows_amd64"


def _validate_staging_proof(manifest: Mapping[str, Any], *, staging_proof: Mapping[str, Any] | None) -> None:
    if (
        staging_proof is None
        or not _STAGING_PROOF_KEYS.issubset(staging_proof)
        or set(staging_proof) - _STAGING_PROOF_KEYS - _OPTIONAL_STAGING_PROOF_KEYS
    ):
        raise CanaryManifestError("technical staging proof is required")
    if staging_proof.get("schema_version") != "windows_canary_staging_proof_v1":
        raise CanaryManifestError("technical staging proof schema is invalid")
    if staging_proof.get("environment_class") != "staging":
        raise CanaryManifestError("technical staging proof is not staging")
    targets = _mapping(manifest["targets"], name="targets")
    revisions = _mapping(manifest["revisions"], name="revisions")
    exact_values = {
        "endpoint_host": _https_host(targets.get("endpoint_origin"), name="endpoint_origin"),
        "helpdesk_host": _https_host(targets.get("helpdesk_origin"), name="helpdesk_origin"),
        "agent_host_safe_label": targets.get("agent_host_safe_label"),
        "endpoint_database_revision": revisions.get("endpoint_database_revision"),
        "helpdesk_database_revision": revisions.get("helpdesk_database_revision"),
    }
    if any(staging_proof.get(key) != value for key, value in exact_values.items()):
        raise CanaryManifestError("technical staging proof does not match manifest")
    if staging_proof.get("dedicated_windows_vm") is not True:
        raise CanaryManifestError("technical staging proof requires a dedicated Windows VM")
    if staging_proof.get("production_identifiers") != []:
        raise CanaryManifestError("technical staging proof contains production identifiers")


def validate_manifest(
    manifest: Mapping[str, Any], *, environment: str, apply: bool, env: Mapping[str, str],
    staging_proof: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Validate scope and approval before any canary operation can be issued."""
    try:
        reject_sensitive_values(manifest)
    except CanaryEvidenceError as error:
        raise CanaryManifestError(str(error)) from error
    schema_version = manifest.get("schema_version")
    if schema_version == "endpoint_diagnostic_canary_v1":
        expected_top_level = _REQUIRED_TOP_LEVEL
    elif schema_version == "endpoint_diagnostic_canary_v2":
        expected_top_level = _V2_TOP_LEVEL
    else:
        raise CanaryManifestError("unsupported manifest schema")
    if set(manifest) != expected_top_level:
        raise CanaryManifestError("manifest top-level schema is invalid")
    if environment != "staging":
        raise CanaryManifestError("only staging environment is permitted")
    environment_data = _mapping(manifest["environment"], name="environment")
    targets = _mapping(manifest["targets"], name="targets")
    execution = _mapping(manifest["execution"], name="execution")
    result = _mapping(manifest["result"], name="result")
    if environment_data.get("environment_class") != "staging":
        raise CanaryManifestError("manifest is not staging")
    if schema_version == "endpoint_diagnostic_canary_v2" and environment_data.get("production_changed") is not False:
        raise CanaryManifestError("manifest must state production_changed=false")
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
    platform = "linux_amd64"
    if schema_version == "endpoint_diagnostic_canary_v2":
        platform = _validate_v2_agent(manifest, targets=targets)
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
        if schema_version != "endpoint_diagnostic_canary_v2":
            raise CanaryManifestError("mutable canary requires a Windows v2 manifest")
        agent = _mapping(manifest["agent"], name="agent")
        windows_expected = {
            "CANARY_AGENT_PLATFORM": agent["platform"],
            "CANARY_WINDOWS_SERVICE": agent["service_name"],
            "CANARY_WINDOWS_UPDATER_SERVICE": agent["updater_service_name"],
            "CANARY_WINDOWS_MSI_VERSION": agent["version"],
            "CANARY_WINDOWS_MSI_SHA256": agent["package_sha256"],
            "CANARY_WINDOWS_SOURCE_REVISION": agent["source_revision"],
        }
        if any(env.get(key) != value for key, value in windows_expected.items()):
            raise CanaryManifestError("Windows identity variables do not match manifest")
        _validate_staging_proof(manifest, staging_proof=staging_proof)
    return {"environment_class": "staging", "apply": apply, "endpoint_host": endpoint_host, "helpdesk_host": helpdesk_host, "platform": platform}


def _helpdesk_route(manifest: Mapping[str, Any], path: str) -> str:
    targets = _mapping(manifest["targets"], name="targets")
    return f"https://{_https_host(targets.get('helpdesk_origin'), name='helpdesk_origin')}{path}"


def _operation_id(response: Mapping[str, Any]) -> str:
    value = response.get("operation_id")
    if not isinstance(value, str) or not value:
        raise CanaryManifestError("existing support route did not return a local operation ID")
    return value


def _overview_items(overview: Mapping[str, Any], *, key: str) -> list[Mapping[str, Any]]:
    value = overview.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CanaryManifestError(f"diagnostics overview {key} is invalid")
    if not all(isinstance(item, Mapping) for item in value):
        raise CanaryManifestError(f"diagnostics overview {key} is invalid")
    return list(value)


def _canary_overview(overview: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    local_operations = [
        item for item in _overview_items(overview, key="latest_operations")
        if item.get("kind") == "endpoint_operation"
    ]
    endpoint_operations = _overview_items(overview, key="endpoint_operations")
    evidence = [
        item for item in _overview_items(overview, key="latest_evidence")
        if item.get("source_type") == "endpoint_platform"
    ]
    return local_operations, endpoint_operations, evidence


def _observe_overview(overview: Mapping[str, Any]) -> dict[str, object]:
    local_operations, endpoint_operations, evidence = _canary_overview(overview)
    return {
        "status": "observed",
        "local_operation_count": len(local_operations),
        "endpoint_operation_count": len(endpoint_operations),
        "evidence_count": len(evidence),
    }


def _verify_overview(overview: Mapping[str, Any]) -> dict[str, object]:
    local_operations, endpoint_operations, evidence = _canary_overview(overview)
    if len(local_operations) != 1 or len(endpoint_operations) != 1 or len(evidence) != 1:
        raise CanaryManifestError("canary overview must contain exactly one operation and one evidence item")
    local_operation = local_operations[0]
    endpoint_operation = endpoint_operations[0]
    evidence_item = evidence[0]
    local_operation_id = _operation_id(local_operation)
    if (
        local_operation.get("status") != "succeeded"
        or endpoint_operation.get("operation_id") != local_operation_id
        or endpoint_operation.get("status") != "succeeded"
        or endpoint_operation.get("result_available") is not True
        or evidence_item.get("status") != "succeeded"
    ):
        raise CanaryManifestError("canary operation did not reach the required terminal state")
    evidence_id = evidence_item.get("id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise CanaryManifestError("canary evidence ID is invalid")
    return {"status": "verified", "local_operation_id": local_operation_id, "evidence_id": evidence_id}


def run_command(
    command: str, *, manifest: Mapping[str, Any], apply: bool, env: Mapping[str, str],
    staging_proof: Mapping[str, Any] | None = None, adapter: CanaryHttpAdapter | None = None,
) -> dict[str, object]:
    """Run exactly one bounded canary stage through existing Helpdesk routes."""
    validation = validate_manifest(manifest, environment="staging", apply=apply, env=env, staging_proof=staging_proof)
    if command == "preflight":
        return {"status": "preflight_ready", **validation}
    if command not in {"map", "execute", "observe", "verify", "rollback-check", "report"}:
        raise CanaryManifestError("unsupported canary command")
    targets = _mapping(manifest["targets"], name="targets")
    ticket_id = _required_string(targets, "helpdesk_ticket_id")
    canary_id = _required_string(_mapping(manifest["execution"], name="execution"), "canary_id")
    if command in {"map", "execute"} and not apply:
        return {"status": "dry_run", "command": command}
    client = adapter or CanaryHttpAdapter(authorization=env.get("CANARY_HELPDESK_AUTHORIZATION"))
    if command == "map":
        response = client.call(
            method="PUT",
            url=_helpdesk_route(manifest, f"/api/admin/tickets/{ticket_id}/endpoint-device-mapping"),
            payload={"schema_version": "endpoint_device_mapping_request_v1", "endpoint_device_ref": targets["endpoint_device_id"], "replace": False, "expected_previous_ref": None, "reason": None},
            headers={"X-Correlation-ID": canary_id},
        )
        if response.get("status") != "ok" or response.get("verified") is not True:
            raise CanaryManifestError("existing admin mapping route did not verify the device")
        return {"status": "mapped"}
    if command == "execute":
        key = env.get("CANARY_CALLER_IDEMPOTENCY_KEY", "")
        execution = _mapping(manifest["execution"], name="execution")
        if not key or ticket_id in key or sha256(key.encode("utf-8")).hexdigest() != execution.get("caller_idempotency_key_hash"):
            raise CanaryManifestError("caller idempotency key does not match the manifest hash")
        response = client.call(
            method="POST",
            url=_helpdesk_route(manifest, f"/api/tickets/{ticket_id}/diagnostics/capabilities/context.diagnostic.collect/run"),
            payload={"params": {}}, headers={"X-Idempotency-Key": key, "X-Correlation-ID": canary_id},
        )
        if response.get("status") != "queued" or response.get("execution_target") != "endpoint_operation":
            raise CanaryManifestError("existing support route did not queue an Endpoint operation")
        return {"status": "queued", "local_operation_id": _operation_id(response)}
    response = client.call(
        method="GET", url=_helpdesk_route(manifest, f"/api/tickets/{ticket_id}/diagnostics/overview"),
        payload=None, headers={"X-Correlation-ID": canary_id},
    )
    if command == "observe":
        return _observe_overview(response)
    if command == "verify":
        return _verify_overview(response)
    return {"status": "observed", "command": command, "overview_present": bool(response)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("preflight", "validate only; never issues an operation"),
        ("map", "validate mapping authority before the existing admin route"),
        ("execute", "validate execution authority before the existing support route"),
        ("observe", "read existing operation projections only"),
        ("verify", "verify existing canary evidence only"),
        ("rollback-check", "read approved rollback state only"),
        ("report", "write a redacted summary only"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument("--environment", required=True)
        command.add_argument("--apply", action="store_true", help="validate mutable-stage authority only")
        command.add_argument("--staging-proof", type=Path, help="protected technical staging-proof JSON for --apply")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        staging_proof = json.loads(args.staging_proof.read_text(encoding="utf-8")) if args.staging_proof else None
        result = run_command(args.command, manifest=manifest, apply=args.apply, env=os.environ, staging_proof=staging_proof)
    except (OSError, json.JSONDecodeError, CanaryManifestError) as error:
        print(f"canary preflight failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "preflight_ready", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
