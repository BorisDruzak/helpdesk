from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from uuid import NAMESPACE_URL, uuid5

import pytest

from scripts.audit_db_cleanup_schema import RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES
from scripts.registry_retirement_manifest import (
    RETIRED_KNOWLEDGE_AI_TABLES,
    RETIREMENT_MANIFEST,
    RetirementManifest,
    current_target_foreign_key_edges,
    manifest_validation_errors,
)
from scripts.rehearse_registry_retirement import (
    MAX_EVIDENCE_AGE,
    attestable_evidence_payload,
    current_foreign_key_graph_signature,
    main,
    run_preflight,
    workspace_git_revision,
)
from scripts import rehearse_registry_retirement as retirement_preflight


def _immutable_id(number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"registry-retirement-evidence-{number}"))


def _attested_evidence(*, attested_at: datetime | None = None) -> dict[str, object]:
    """Build a complete, redacted evidence bundle for preflight tests only."""

    attested_at = attested_at or datetime.now(timezone.utc)
    backup_at = attested_at - timedelta(minutes=4)
    restore_at = attested_at - timedelta(minutes=3)
    catalog_at = attested_at - timedelta(minutes=2)
    maintenance_at = attested_at - timedelta(minutes=1)
    environment = "retirement-clone"
    revision = "a" * 40
    backup_id = _immutable_id(1)
    clone_id = _immutable_id(2)
    evidence: dict[str, object] = {
        "schema": "pc_client.registry_retirement_evidence.v1",
        "environment": environment,
        "revision": revision,
        "attested_at": attested_at.isoformat(),
        "external_command_acceptance": {
            "acceptance_id": _immutable_id(3),
            "accepted": True,
            "environment": environment,
            "revision": revision,
            "accepted_at": backup_at.isoformat(),
            "operations": sorted(
                {
                    "login_eligibility",
                    "registration_request",
                    "registration_approve",
                    "registration_reject",
                    "binding_revoke",
                    "account_session_create",
                    "account_session_validate",
                    "account_session_logout",
                    "account_session_revoke",
                    "browser_pairing_create",
                    "browser_pairing_confirm",
                    "browser_pairing_pickup",
                    "other_account_approval",
                }
            ),
        },
        "backup": {
            "artifact_id": backup_id,
            "sha256": "b" * 64,
            "environment": environment,
            "revision": revision,
            "created_at": backup_at.isoformat(),
        },
        "restore_drill": {
            "drill_id": _immutable_id(4),
            "clone_id": clone_id,
            "backup_artifact_id": backup_id,
            "backup_sha256": "b" * 64,
            "environment": environment,
            "revision": revision,
            "completed_at": restore_at.isoformat(),
            "passed": True,
        },
        "catalog": {
            "catalog_id": _immutable_id(5),
            "clone_id": clone_id,
            "backup_artifact_id": backup_id,
            "environment": environment,
            "revision": revision,
            "captured_at": catalog_at.isoformat(),
            "table_counts": {table: 0 for table in sorted(RETIREMENT_MANIFEST.target_tables)},
            "foreign_key_signature": current_foreign_key_graph_signature(),
        },
        "maintenance": {
            "plan_id": _immutable_id(6),
            "approved": True,
            "writers_stopped": True,
            "advisory_lock_key": "registry-retirement-v1",
            "environment": environment,
            "revision": revision,
            "approved_at": maintenance_at.isoformat(),
        },
        "attestation": {
            "algorithm": "fixture-sha256",
            "key_id": "fixture-public-key-1",
            "signature": "",
        },
    }
    signature = sha256(attestable_evidence_payload(evidence)).hexdigest()
    evidence["attestation"] = {
        "algorithm": "fixture-sha256",
        "key_id": "fixture-public-key-1",
        "signature": signature,
    }
    return evidence


def _fixture_attestation_verifier(payload: bytes, algorithm: str, key_id: str, signature: str) -> bool:
    return (
        algorithm == "fixture-sha256"
        and key_id == "fixture-public-key-1"
        and signature == sha256(payload).hexdigest()
    )


def _resign(evidence: dict[str, object]) -> None:
    evidence["attestation"] = {
        "algorithm": "fixture-sha256",
        "key_id": "fixture-public-key-1",
        "signature": sha256(attestable_evidence_payload(evidence)).hexdigest(),
    }


def _write_evidence(workspace: Path, evidence: dict[str, object]) -> None:
    artifact = workspace / "artifacts" / "registry-retirement-evidence.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(evidence), encoding="utf-8")


def test_retirement_manifest_preserves_helpdesk_owned_tables() -> None:
    assert RETIREMENT_MANIFEST.retain_tables >= {
        "ui_users",
        "tickets",
        "user_consent_requests",
        "ticket_kb_links",
    }
    assert not RETIREMENT_MANIFEST.target_tables & RETIREMENT_MANIFEST.retain_tables


def test_retirement_manifest_protects_actual_session_and_rbac_tables() -> None:
    assert {
        "ui_users",
        "auth_sessions",
        "ui_tokens",
        "access_groups",
        "access_group_members",
        "access_group_permissions",
        "access_group_queue_members",
        "access_audit",
        "ticket_queues",
    } <= RETIREMENT_MANIFEST.retain_tables
    assert {
        "web_sessions",
        "web_session_tokens",
        "rbac_role_bindings",
        "rbac_permissions",
    }.isdisjoint(RETIREMENT_MANIFEST.retain_tables)


def test_retirement_manifest_covers_approved_registry_knowledge_and_fk_detachments() -> None:
    assert {
        "registry_people",
        "device_registration_claims",
        "device_account_sessions",
        "device_browser_pairings",
        "knowledge_items",
        "ai_providers",
        "ticket_knowledge_links",
        "problem_known_error_links",
    } <= RETIREMENT_MANIFEST.target_tables
    assert RETIREMENT_MANIFEST.detach_columns["tickets"] >= {
        "requester_person_id",
        "requester_binding_id",
        "requester_account_session_id",
    }
    assert RETIREMENT_MANIFEST.detach_columns["user_consent_requests"] >= {
        "requester_person_id",
        "requester_binding_id",
        "requester_account_session_id",
    }
    assert RETIREMENT_MANIFEST.detach_columns["helpdesk_services"] >= {
        "owner_person_id",
        "registry_service_id",
    }


def test_cleanup_audit_uses_the_same_knowledge_retirement_target() -> None:
    assert RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES == RETIRED_KNOWLEDGE_AI_TABLES


def test_retirement_manifest_has_unique_dependency_safe_order_from_current_models() -> None:
    ordered = tuple(table for group in RETIREMENT_MANIFEST.drop_order for table in group)
    assert len(ordered) == len(set(ordered)) == len(RETIREMENT_MANIFEST.target_tables)
    positions = {table: index for index, table in enumerate(ordered)}
    for child, parent in current_target_foreign_key_edges():
        assert positions[child] < positions[parent]
    assert manifest_validation_errors() == ()


def test_retirement_manifest_rejects_duplicate_missing_and_dependency_invalid_drop_order() -> None:
    targets = frozenset({"device_account_events", "device_account_sessions"})
    duplicate_and_missing = RetirementManifest(
        target_tables=targets,
        retain_tables=RETIRED_MANIFEST_RETAIN,
        detach_columns={},
        drop_order=(("device_account_events", "device_account_events"),),
    )
    dependency_invalid = replace(
        duplicate_and_missing,
        drop_order=(("device_account_sessions",), ("device_account_events",)),
    )

    duplicate_errors = manifest_validation_errors(duplicate_and_missing)
    assert any("duplicate" in error for error in duplicate_errors)
    assert any("missing" in error for error in duplicate_errors)
    assert any("reverse FK order" in error for error in manifest_validation_errors(dependency_invalid))


RETIRED_MANIFEST_RETAIN = RETIREMENT_MANIFEST.retain_tables


def test_preflight_rejects_active_registry_runtime(tmp_path: Path) -> None:
    (tmp_path / "server" / "registry").mkdir(parents=True)
    (tmp_path / "server" / "registry" / "registration_service.py").write_text(
        "class RegistrationService: pass\n",
        encoding="utf-8",
    )

    result = run_preflight(tmp_path)

    assert result.ready is False
    assert "local_registry_runtime_present" in result.blocker_codes


def test_preflight_requires_all_release_evidence_after_code_cutover(tmp_path: Path) -> None:
    (tmp_path / "server" / "registry_adapter").mkdir(parents=True)

    result = run_preflight(tmp_path)

    assert result.ready is False
    assert {
        "external_command_acceptance_missing",
        "backup_restore_evidence_missing",
        "maintenance_advisory_lock_plan_missing",
        "row_count_evidence_missing",
        "retirement_evidence_attestation_missing_or_untrusted",
    } <= set(result.blocker_codes)


def test_preflight_requires_a_trusted_attestation_for_complete_evidence(tmp_path: Path) -> None:
    _write_evidence(tmp_path, _attested_evidence())
    (tmp_path / "server" / "config.py").parent.mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(tmp_path)

    assert result.ready is False
    assert "retirement_evidence_attestation_missing_or_untrusted" in result.blocker_codes
    trusted_result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)
    assert trusted_result.ready is True


def test_preflight_rejects_signed_evidence_for_a_different_expected_revision(tmp_path: Path) -> None:
    _write_evidence(tmp_path, _attested_evidence())
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(
        tmp_path,
        attestation_verifier=_fixture_attestation_verifier,
        expected_environment="retirement-clone",
        expected_revision="b" * 40,
    )

    assert result.ready is False
    assert "retirement_evidence_revision_mismatch" in result.blocker_codes


def test_preflight_rejects_signed_evidence_for_a_different_expected_environment(tmp_path: Path) -> None:
    _write_evidence(tmp_path, _attested_evidence())
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(
        tmp_path,
        attestation_verifier=_fixture_attestation_verifier,
        expected_environment="production-retirement",
        expected_revision="a" * 40,
    )

    assert result.ready is False
    assert "retirement_evidence_environment_mismatch" in result.blocker_codes


def test_preflight_rejects_replayed_or_stale_signed_evidence(tmp_path: Path) -> None:
    stale_attestation = datetime.now(timezone.utc) - MAX_EVIDENCE_AGE - timedelta(seconds=1)
    _write_evidence(tmp_path, _attested_evidence(attested_at=stale_attestation))
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)

    assert result.ready is False
    assert "retirement_evidence_replayed_or_stale" in result.blocker_codes


def test_preflight_rejects_future_signed_evidence(tmp_path: Path) -> None:
    future_attestation = datetime.now(timezone.utc) + timedelta(minutes=6)
    _write_evidence(tmp_path, _attested_evidence(attested_at=future_attestation))
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)

    assert result.ready is False
    assert "retirement_evidence_timestamp_in_future" in result.blocker_codes


def test_preflight_rejects_signed_evidence_with_invalid_backup_restore_maintenance_order(tmp_path: Path) -> None:
    evidence = _attested_evidence()
    restore = evidence["restore_drill"]
    catalog = evidence["catalog"]
    assert isinstance(restore, dict)
    assert isinstance(catalog, dict)
    catalog["captured_at"] = restore["completed_at"]
    _resign(evidence)
    _write_evidence(tmp_path, evidence)
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)

    assert result.ready is False
    assert "retirement_evidence_timeline_invalid" in result.blocker_codes


def test_require_ready_derives_workspace_revision_and_requires_matching_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_evidence(tmp_path, _attested_evidence())
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")
    monkeypatch.setattr(retirement_preflight, "workspace_git_revision", lambda _: "a" * 40)
    monkeypatch.setattr(retirement_preflight, "load_attestation_verifier", lambda _: _fixture_attestation_verifier)

    assert main(
        [
            "--workspace",
            str(tmp_path),
            "--require-ready",
            "--expected-environment",
            "retirement-clone",
            "--attestation-verifier",
            "test:fixture",
        ]
    ) == 0
    assert main(
        [
            "--workspace",
            str(tmp_path),
            "--require-ready",
            "--expected-environment",
            "different-environment",
            "--attestation-verifier",
            "test:fixture",
        ]
    ) == 1


def test_require_ready_rejects_missing_expected_environment(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--workspace", str(tmp_path), "--require-ready"])

    assert exc_info.value.code == 2


def test_dry_run_stays_informational_and_does_not_write_evidence(tmp_path: Path) -> None:
    assert main(["--workspace", str(tmp_path), "--dry-run"]) == 0
    assert not (tmp_path / "artifacts" / "registry-retirement-evidence.json").exists()


def test_workspace_revision_rejects_a_dirty_checkout(tmp_path: Path) -> None:
    def git(*arguments: str) -> None:
        subprocess.run(("git", "-C", str(tmp_path), *arguments), check=True, capture_output=True, text=True)

    git("init")
    git("config", "user.email", "preflight@example.test")
    git("config", "user.name", "Preflight Test")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    git("add", "tracked.txt")
    git("commit", "-m", "test: establish immutable revision")

    assert workspace_git_revision(tmp_path) is not None
    tracked.write_text("dirty\n", encoding="utf-8")
    assert workspace_git_revision(tmp_path) is None


def test_preflight_rejects_tampered_or_unlinked_complete_evidence(tmp_path: Path) -> None:
    evidence = _attested_evidence()
    restore = evidence["restore_drill"]
    assert isinstance(restore, dict)
    restore["backup_artifact_id"] = _immutable_id(99)
    evidence["attestation"] = {
        "algorithm": "fixture-sha256",
        "key_id": "fixture-public-key-1",
        "signature": sha256(attestable_evidence_payload(evidence)).hexdigest(),
    }
    _write_evidence(tmp_path, evidence)
    (tmp_path / "server").mkdir(parents=True)
    (tmp_path / "server" / "config.py").write_text("REGISTRY_PORT_MODE = 'external'\n", encoding="utf-8")

    result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)

    assert result.ready is False
    assert "backup_restore_evidence_missing" in result.blocker_codes


def test_preflight_rejects_local_adapter_and_local_config_despite_trusted_complete_evidence(tmp_path: Path) -> None:
    _write_evidence(tmp_path, _attested_evidence())
    adapter = tmp_path / "server" / "registry_adapter" / "local.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("from app.repos.registration_repo import RegistrationRepo\n", encoding="utf-8")
    (tmp_path / "server" / "config.py").write_text(
        "REGISTRY_PORT_MODE = (os.getenv('REGISTRY_PORT_MODE', 'local') or 'local').strip().lower()\n",
        encoding="utf-8",
    )

    result = run_preflight(tmp_path, attestation_verifier=_fixture_attestation_verifier)

    assert result.ready is False
    assert {
        "local_registry_runtime_present",
        "local_registry_configuration_present",
        "local_registry_consumers_present",
    } <= set(result.blocker_codes)
    assert "retirement_evidence_attestation_missing_or_untrusted" not in result.blocker_codes


def test_preflight_rejects_multiline_legacy_registry_model_import(tmp_path: Path) -> None:
    consumer = tmp_path / "server" / "tickets" / "legacy_consumer.py"
    consumer.parent.mkdir(parents=True)
    consumer.write_text(
        "from app.db.models import (\n    RegistryPerson,\n)\n",
        encoding="utf-8",
    )

    result = run_preflight(tmp_path)

    assert result.ready is False
    assert "local_registry_consumers_present" in result.blocker_codes


def test_preflight_rejects_direct_registration_repository_import(tmp_path: Path) -> None:
    consumer = tmp_path / "server" / "tickets" / "legacy_registration_consumer.py"
    consumer.parent.mkdir(parents=True)
    consumer.write_text(
        "from app.repos.registration_repo import RegistrationRepo\n",
        encoding="utf-8",
    )

    result = run_preflight(tmp_path)

    assert result.ready is False
    assert "local_registry_consumers_present" in result.blocker_codes


def test_preflight_ignores_test_only_registry_imports(tmp_path: Path) -> None:
    test_module = tmp_path / "server" / "test_registry_fixture.py"
    test_module.parent.mkdir(parents=True)
    test_module.write_text("from app.db.models import RegistryPerson\n", encoding="utf-8")

    result = run_preflight(tmp_path)

    assert "local_registry_consumers_present" not in result.blocker_codes
