"""Exact-revision production acceptance validation and immutable manifest."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.production_readiness_audit import validate_risk_audit
from scripts.build_webapp_bundle import archive_bundle_digest
from scripts.validate_production_config import read_environment
from scripts.validate_endpoint_contract_lock import validate
from shared.production_security import production_config_errors


REQUIRED_ACCEPTANCE = (
    "contract_acceptance", "backup_status", "restore_drill_status", "business_smoke",
    "windows_endpoint_acceptance", "endpoint_degraded_acceptance",
)


def validate_acceptance_evidence(payload: dict, commit: str, provider: str, openapi: str,
                                 schema: str, web_digest: str) -> None:
    expected = dict(helpdesk_git_sha=commit, endpoint_provider_sha=provider,
                    endpoint_openapi_sha256=openapi, schema_revision=schema,
                    webapp_build_digest=web_digest, configuration_profile="production-v1",
                    environment="staging")
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"acceptance identity mismatch: {key}")
    for key in REQUIRED_ACCEPTANCE:
        if payload.get(key) != "success":
            raise ValueError(f"required staging acceptance missing or failed: {key}")


def validate_production_release(workspace: Path, commit: str, bundle: Path, *, environment_file: Path,
                                risk_audit: Path, evidence: Path, provider_root: Path, schema: str) -> Path:
    values = read_environment(environment_file)
    errors = production_config_errors(values)
    if values.get("APP_ENV") != "prod" or errors:
        raise ValueError("production configuration rejected: " + "; ".join(errors))
    validate_risk_audit(json.loads(risk_audit.read_text(encoding="utf-8")), commit)
    lock_path = workspace / "integration/endpoint_contract.lock.json"
    validate(lock_path=lock_path, provider_root=provider_root)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    metadata = json.loads(bundle.with_name(bundle.name + ".manifest.json").read_text(encoding="utf-8"))
    with bundle.open("rb") as handle:
        archive_digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if metadata.get("helpdesk_git_sha") != commit or metadata.get("archive_sha256") != archive_digest:
        raise ValueError("web bundle identity or archive digest mismatch")
    web_digest = metadata.get("webapp_build_digest", "")
    if len(web_digest) != 64 or any(char not in "0123456789abcdef" for char in web_digest):
        raise ValueError("web content digest missing")
    if archive_bundle_digest(bundle) != web_digest:
        raise ValueError("web archive content differs from its recorded digest")
    acceptance = json.loads(evidence.read_text(encoding="utf-8"))
    validate_acceptance_evidence(acceptance, commit, lock["provider_commit"], lock["openapi_sha256"], schema, web_digest)
    manifest = dict(helpdesk_git_sha=commit, helpdesk_schema_revision=schema,
                    webapp_build_digest=web_digest, endpoint_provider_sha=lock["provider_commit"],
                    endpoint_openapi_sha256=lock["openapi_sha256"],
                    configuration_profile="production-v1", ci_status="success",
                    release_timestamp=datetime.now(timezone.utc).isoformat())
    manifest.update({key: "success" for key in REQUIRED_ACCEPTANCE})
    output = workspace / "artifacts/release" / commit / "release-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if {key: value for key, value in existing.items() if key != "release_timestamp"} != {
            key: value for key, value in manifest.items() if key != "release_timestamp"
        }:
            raise ValueError("immutable manifest differs from verified candidate")
        return output
    # Never overwrite an accepted identity or copy arbitrary evidence fields.
    with output.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2); handle.write("\n")
    return output
