from __future__ import annotations

import json
from pathlib import Path

from scripts import audit_branch_coverage


def _write_registry(workspace: Path, payload: dict) -> Path:
    registry_path = workspace / "quality" / "critical_branch_coverage.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    return registry_path


def test_audit_branch_coverage_accepts_existing_module_and_test_refs(tmp_path):
    module_path = tmp_path / "shared" / "redaction.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("def redact_sensitive_payload():\n    return None\n", encoding="utf-8")
    test_path = tmp_path / "server" / "tests" / "test_property_state_contracts_no_db.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        "def test_redaction_property_nested_payloads_are_non_mutating_idempotent_and_secret_free():\n"
        "    pass\n",
        encoding="utf-8",
    )
    registry_path = _write_registry(
        tmp_path,
        {
            "schema": "pc_client.critical_branch_coverage.v1",
            "packages": [
                {
                    "path": "shared/redaction.py",
                    "owner": "observer",
                    "branches": [
                        {
                            "id": "redaction.nested_sensitive_values",
                            "description": "nested sensitive keys and bearer values are redacted",
                            "criticality": "P1",
                            "tested_by": [
                                "server/tests/test_property_state_contracts_no_db.py::"
                                "test_redaction_property_nested_payloads_are_non_mutating_idempotent_and_secret_free"
                            ],
                        }
                    ],
                }
            ],
        },
    )

    report = audit_branch_coverage.audit_branch_coverage(tmp_path, registry_path=registry_path)

    assert report["status"] == "ok"
    assert report["package_count"] == 1
    assert report["branch_count"] == 1
    assert report["issues"] == []


def test_audit_branch_coverage_reports_missing_refs_and_duplicate_ids(tmp_path):
    module_path = tmp_path / "shared" / "redaction.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("def redact_sensitive_payload():\n    return None\n", encoding="utf-8")
    test_path = tmp_path / "server" / "tests" / "test_property_state_contracts_no_db.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_existing_contract():\n    pass\n", encoding="utf-8")
    registry_path = _write_registry(
        tmp_path,
        {
            "schema": "pc_client.critical_branch_coverage.v1",
            "packages": [
                {
                    "path": "shared/redaction.py",
                    "owner": "observer",
                    "branches": [
                        {
                            "id": "redaction.nested_sensitive_values",
                            "description": "missing tests",
                            "criticality": "P1",
                            "tested_by": [],
                        },
                        {
                            "id": "redaction.nested_sensitive_values",
                            "description": "missing node",
                            "criticality": "P1",
                            "tested_by": [
                                "server/tests/test_property_state_contracts_no_db.py::test_missing_contract"
                            ],
                        },
                    ],
                }
            ],
        },
    )

    report = audit_branch_coverage.audit_branch_coverage(tmp_path, registry_path=registry_path)

    assert report["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} == {
        "duplicate_branch_id",
        "missing_tested_by",
        "missing_test_node",
    }
