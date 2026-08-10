from __future__ import annotations

from pathlib import Path

from scripts.audit_db_cleanup_schema import RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES
from scripts.registry_retirement_manifest import RETIRED_KNOWLEDGE_AI_TABLES, RETIREMENT_MANIFEST
from scripts.rehearse_registry_retirement import run_preflight


def test_retirement_manifest_preserves_helpdesk_owned_tables() -> None:
    assert RETIREMENT_MANIFEST.retain_tables >= {
        "ui_users",
        "tickets",
        "user_consent_requests",
        "ticket_kb_links",
    }
    assert not RETIREMENT_MANIFEST.target_tables & RETIREMENT_MANIFEST.retain_tables


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
    } <= set(result.blocker_codes)


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


def test_preflight_ignores_test_only_registry_imports(tmp_path: Path) -> None:
    test_module = tmp_path / "server" / "test_registry_fixture.py"
    test_module.parent.mkdir(parents=True)
    test_module.write_text("from app.db.models import RegistryPerson\n", encoding="utf-8")

    result = run_preflight(tmp_path)

    assert "local_registry_consumers_present" not in result.blocker_codes
