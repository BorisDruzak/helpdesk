"""Static contract for the cross-repository Endpoint acceptance workflow."""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


def test_endpoint_contract_acceptance_runs_on_helpdesk_mainline_with_evidence() -> None:
    workflow = Path(
        ".github/workflows/endpoint-contract-acceptance.yml"
    ).read_text(encoding="utf-8")

    for required in (
        "pull_request:",
        "push:",
        "workflow_dispatch:",
        "codex/helpdesk-process-model",
        "group: endpoint-contract-${{ github.ref }}",
        "cancel-in-progress: true",
        "TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/pc_support_test_endpoint_ci",
        "TEST_DATABASE_ADMIN_URL: postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
        "server/tests/test_endpoint_contract_lock.py",
        "server/tests/test_endpoint_http_adapter.py",
        "server/tests/test_endpoint_operation_reconciler.py",
        "server/tests/test_endpoint_device_reference_service.py",
        "server/tests/test_endpoint_diagnostic_cutover_guards.py",
        "server/tests/migration/test_endpoint_integration_upgrade_rehearsal.py",
        "--junitxml=artifacts/endpoint-contract-acceptance.xml",
        "acceptance-summary.json",
        "artifacts/migration/endpoint-integration-rehearsal.json",
        "endpoint-contract-acceptance",
        '"provider_app": "real"',
        '"gateway_wss": "real"',
        '"agent_client": "protocol_test_client"',
        '"production_changed": False',
    ):
        assert required in workflow

    assert "paths:" not in workflow
    assert "codex/endpoint-integration-hardening-v1" not in workflow
    assert "endpoint_module_platform" not in workflow
