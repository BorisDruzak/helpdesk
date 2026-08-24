"""Fail-closed contracts for the Endpoint diagnostic canary orchestrator."""

from __future__ import annotations

import copy
import hashlib

import pytest

from scripts.canary.endpoint_diagnostic_canary import (
    CanaryHttpAdapter,
    CanaryManifestError,
    _parser,
    run_command,
    validate_manifest,
)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "endpoint_diagnostic_canary_v1",
        "environment": {
            "environment_id": "endpoint-helpdesk-staging",
            "environment_class": "staging",
            "change_id": "CHG-ALT-101",
            "observation_owner": "staging-owner",
        },
        "revisions": {
            "endpoint_repository": "BorisDruzak/endpoint_platform",
            "endpoint_commit": "a" * 40,
            "helpdesk_repository": "BorisDruzak/helpdesk",
            "helpdesk_commit": "b" * 40,
            "endpoint_database_revision": "0011_gateway_wss",
            "helpdesk_database_revision": "137",
            "agent_source_revision": "a" * 40,
            "agent_version": "3.1.99",
        },
        "targets": {
            "endpoint_origin": "https://endpoint-staging.sosnadmin.local",
            "helpdesk_origin": "https://helpdesk-staging.sosnadmin.local",
            "agent_host_safe_label": "alt-canary-70",
            "endpoint_device_id": "00000000-0000-4000-8000-000000000701",
            "helpdesk_ticket_id": "ticket-staging-701",
        },
        "baseline": {"ticket_status": "open", "helpdesk_operation_count": 0, "endpoint_operation_count": 0, "evidence_count": 0, "device_outbox_count": 0, "recorded_at": "2026-08-23T00:00:00Z"},
        "execution": {"canary_id": "canary-701", "caller_idempotency_key_hash": "c" * 64, "local_operation_id": None, "remote_operation_id": None, "started_at": None, "completed_at": None, "final_status": "not_started"},
        "rollback": {"started_at": None, "completed_at": None, "final_endpoint_api_mode": "disabled", "final_helpdesk_port_mode": "unavailable", "final_helpdesk_execution_mode": "legacy"},
        "result": {"success": False, "stop_reason": None, "production_changed": False},
    }


def test_manifest_accepts_staging_dry_run_without_any_mutation_authority() -> None:
    result = validate_manifest(_manifest(), environment="staging", apply=False, env={})

    assert result["environment_class"] == "staging"
    assert result["apply"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (("environment", "environment_class"), "production"),
        (("execution", "caller_idempotency_key_hash"), "not-a-hash"),
        (("result", "production_changed"), True),
    ],
)
def test_manifest_rejects_unsafe_environment_or_execution_values(
    field: tuple[str, str], value: object
) -> None:
    manifest = copy.deepcopy(_manifest())
    manifest[field[0]][field[1]] = value  # type: ignore[index]

    with pytest.raises(CanaryManifestError):
        validate_manifest(manifest, environment="staging", apply=False, env={})


def test_apply_requires_exact_environment_approval_and_does_not_accept_secrets() -> None:
    manifest = _windows_manifest()
    env = _apply_environment()

    assert validate_manifest(
        manifest, environment="staging", apply=True, env=env, staging_proof=_staging_proof()
    )["apply"] is True

    manifest["service_token"] = "forbidden"
    with pytest.raises(CanaryManifestError, match="forbidden"):
        validate_manifest(manifest, environment="staging", apply=False, env={})


def test_windows_v2_manifest_accepts_only_the_strict_schema() -> None:
    manifest = _manifest()
    manifest["schema_version"] = "endpoint_diagnostic_canary_v2"
    manifest["agent"] = {
        "platform": "windows_amd64",
        "host_safe_label": "alt-canary-70",
        "device_id": "00000000-0000-4000-8000-000000000701",
        "service_name": "EndpointAgent",
        "updater_service_name": "EndpointAgentUpdater",
        "source_revision": "a" * 40,
        "version": "3.2.16",
        "package_name": "endpoint-agent-3.2.16.msi",
        "package_sha256": "d" * 64,
    }
    manifest["environment"]["production_changed"] = False

    result = validate_manifest(manifest, environment="staging", apply=False, env={})

    assert result["platform"] == "windows_amd64"


def test_windows_v2_manifest_rejects_unknown_agent_field() -> None:
    manifest = _manifest()
    manifest["schema_version"] = "endpoint_diagnostic_canary_v2"
    manifest["agent"] = {
        "platform": "windows_amd64",
        "host_safe_label": "alt-canary-70",
        "device_id": "00000000-0000-4000-8000-000000000701",
        "service_name": "EndpointAgent",
        "updater_service_name": "EndpointAgentUpdater",
        "source_revision": "a" * 40,
        "version": "3.2.16",
        "package_name": "endpoint-agent-3.2.16.msi",
        "package_sha256": "d" * 64,
        "credential": "forbidden",
    }
    manifest["environment"]["production_changed"] = False

    with pytest.raises(CanaryManifestError, match="forbidden|schema"):
        validate_manifest(manifest, environment="staging", apply=False, env={})


def test_canary_parser_registers_all_commands_with_dry_run_default() -> None:
    parser = _parser()

    for command in ("preflight", "map", "execute", "observe", "verify", "rollback-check", "report"):
        args = parser.parse_args([command, "--manifest", "fixture.json", "--environment", "staging"])

        assert args.command == command
        assert args.apply is False


def _windows_manifest() -> dict[str, object]:
    manifest = _manifest()
    manifest["schema_version"] = "endpoint_diagnostic_canary_v2"
    manifest["environment"]["production_changed"] = False
    manifest["agent"] = {
        "platform": "windows_amd64",
        "host_safe_label": "alt-canary-70",
        "device_id": "00000000-0000-4000-8000-000000000701",
        "service_name": "EndpointAgent",
        "updater_service_name": "EndpointAgentUpdater",
        "source_revision": "a" * 40,
        "version": "3.2.16",
        "package_name": "endpoint-agent-3.2.16.msi",
        "package_sha256": "d" * 64,
    }
    return manifest


def _apply_environment() -> dict[str, str]:
    caller_key = "canary-key-without-ticket-reference"
    return {
        "CANARY_APPROVED": "true",
        "CANARY_ENVIRONMENT": "staging",
        "CANARY_CHANGE_ID": "CHG-ALT-101",
        "CANARY_ENDPOINT_HOST": "endpoint-staging.sosnadmin.local",
        "CANARY_HELPDESK_HOST": "helpdesk-staging.sosnadmin.local",
        "CANARY_AGENT_HOST": "alt-canary-70",
        "CANARY_ENDPOINT_DEVICE_ID": "00000000-0000-4000-8000-000000000701",
        "CANARY_HELPDESK_TICKET_ID": "ticket-staging-701",
        "CANARY_EVIDENCE_ROOT": "/var/lib/helpdesk/canary-evidence",
        "CANARY_AGENT_PLATFORM": "windows_amd64",
        "CANARY_WINDOWS_SERVICE": "EndpointAgent",
        "CANARY_WINDOWS_UPDATER_SERVICE": "EndpointAgentUpdater",
        "CANARY_WINDOWS_MSI_VERSION": "3.2.16",
        "CANARY_WINDOWS_MSI_SHA256": "d" * 64,
        "CANARY_WINDOWS_SOURCE_REVISION": "a" * 40,
        "CANARY_CALLER_IDEMPOTENCY_KEY": caller_key,
    }


def _staging_proof() -> dict[str, object]:
    return {
        "schema_version": "windows_canary_staging_proof_v1",
        "environment_class": "staging",
        "endpoint_host": "endpoint-staging.sosnadmin.local",
        "helpdesk_host": "helpdesk-staging.sosnadmin.local",
        "agent_host_safe_label": "alt-canary-70",
        "dedicated_windows_vm": True,
        "snapshot_or_recovery_point": "snapshot-staging-701",
        "production_identifiers": [],
        "endpoint_database_revision": "0011_gateway_wss",
        "helpdesk_database_revision": "137",
    }


def test_apply_requires_matching_windows_identity_and_technical_staging_proof() -> None:
    manifest = _windows_manifest()
    environment = _apply_environment()

    result = validate_manifest(
        manifest,
        environment="staging",
        apply=True,
        env=environment,
        staging_proof=_staging_proof(),
    )

    assert result["platform"] == "windows_amd64"
    proof = _staging_proof()
    proof["dedicated_windows_vm"] = False
    with pytest.raises(CanaryManifestError, match="dedicated"):
        validate_manifest(manifest, environment="staging", apply=True, env=environment, staging_proof=proof)


def test_apply_accepts_staging_proof_without_snapshot() -> None:
    proof = _staging_proof()
    proof.pop("snapshot_or_recovery_point")

    assert validate_manifest(
        _windows_manifest(), environment="staging", apply=True, env=_apply_environment(), staging_proof=proof
    )["apply"] is True


def test_map_dry_run_does_not_call_route_and_apply_uses_only_existing_admin_route() -> None:
    manifest = _windows_manifest()
    calls: list[dict[str, object]] = []
    adapter = CanaryHttpAdapter(
        request=lambda **request: calls.append(request) or {"status": "ok", "verified": True}
    )

    dry_run = run_command("map", manifest=manifest, apply=False, env={}, adapter=adapter)
    applied = run_command(
        "map",
        manifest=manifest,
        apply=True,
        env=_apply_environment(),
        staging_proof=_staging_proof(),
        adapter=adapter,
    )

    assert dry_run["status"] == "dry_run"
    assert calls == [{
        "method": "PUT",
        "url": "https://helpdesk-staging.sosnadmin.local/api/admin/tickets/ticket-staging-701/endpoint-device-mapping",
        "payload": {
            "schema_version": "endpoint_device_mapping_request_v1",
            "endpoint_device_ref": "00000000-0000-4000-8000-000000000701",
            "replace": False,
            "expected_previous_ref": None,
            "reason": None,
        },
        "headers": {"X-Correlation-ID": "canary-701"},
    }]
    assert applied["status"] == "mapped"


def test_execute_uses_one_hashed_idempotency_key_and_never_includes_ticket_in_payload() -> None:
    manifest = _windows_manifest()
    key = _apply_environment()["CANARY_CALLER_IDEMPOTENCY_KEY"]
    manifest["execution"]["caller_idempotency_key_hash"] = hashlib.sha256(key.encode()).hexdigest()
    calls: list[dict[str, object]] = []
    adapter = CanaryHttpAdapter(
        request=lambda **request: calls.append(request) or {"status": "queued", "operation_id": "local-701", "execution_target": "endpoint_operation"}
    )

    result = run_command(
        "execute",
        manifest=manifest,
        apply=True,
        env=_apply_environment(),
        staging_proof=_staging_proof(),
        adapter=adapter,
    )

    assert result == {"status": "queued", "local_operation_id": "local-701"}
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/api/tickets/ticket-staging-701/diagnostics/capabilities/context.diagnostic.collect/run")
    assert calls[0]["payload"] == {"params": {}}
    assert calls[0]["headers"] == {"X-Idempotency-Key": key, "X-Correlation-ID": "canary-701"}
