from __future__ import annotations

import json
from pathlib import Path

from scripts import audit_active_risks


REQUIRED_SOURCE_IDS = {
    "archive.1.1.outbox_ack",
    "archive.1.2.command_idempotency",
    "archive.1.3.scheduler_rpc",
    "archive.1.4.consent_orchestrator",
    "archive.1.5.module_manager_handshake",
    "archive.2.2.device_outbox_dispatch",
    "archive.2.3.sync_run_tool_wait",
    "archive.2.4.run_tool_entry_paths",
    "archive.3.3.server_public_base_url",
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_supporting_files(workspace: Path) -> None:
    archive = workspace / "docs" / "archive" / "BOTTLENECKS_AND_RISKS.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("# risks\n", encoding="utf-8")
    test_path = workspace / "scripts" / "test_example.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_example():\n    pass\n", encoding="utf-8")


def _valid_registry() -> dict:
    return {
        "schema": "pc_client.active_risks.v1",
        "last_reviewed": "2026-06-24",
        "risks": [
            {
                "id": "TD-012",
                "priority": "P2",
                "status": "active",
                "owner_zone": "quality",
                "risk": "Archive risks can drift away from executable coverage.",
                "affected_contracts": ["PLANS.md active debt registry"],
                "source_refs": [
                    {
                        "source_id": source_id,
                        "path": "docs/archive/BOTTLENECKS_AND_RISKS.md",
                        "section": source_id,
                    }
                    for source_id in sorted(REQUIRED_SOURCE_IDS)
                ],
                "evidence_refs": ["docs/archive/BOTTLENECKS_AND_RISKS.md"],
                "escalation_trigger": "A source archive section marked active is not represented in the registry.",
                "acceptance_criteria": [
                    {
                        "metric": "active risk audit issues",
                        "target": "0 issues from scripts/audit_active_risks.py --strict",
                    }
                ],
                "linked_tests": [
                    {
                        "ref": "scripts/test_example.py::test_example",
                        "purpose": "Keeps registry metadata executable.",
                    }
                ],
                "last_reviewed": "2026-06-24",
            }
        ],
    }


def test_audit_active_risks_accepts_complete_registry(tmp_path: Path) -> None:
    _write_supporting_files(tmp_path)
    registry_path = tmp_path / "quality" / "active_risks.json"
    _write_json(registry_path, _valid_registry())

    report = audit_active_risks.audit_active_risks(tmp_path, registry_path=registry_path)

    assert report["status"] == "ok"
    assert report["risk_count"] == 1
    assert report["active_count"] == 1
    assert report["issues"] == []


def test_audit_active_risks_reports_missing_active_gate_fields_and_refs(tmp_path: Path) -> None:
    _write_supporting_files(tmp_path)
    registry = _valid_registry()
    risk = registry["risks"][0]
    risk["owner_zone"] = ""
    risk["linked_tests"] = [{"ref": "scripts/test_example.py::test_missing", "purpose": "bad ref"}]
    risk["acceptance_criteria"] = []
    risk["source_refs"] = risk["source_refs"][:-1]
    registry_path = tmp_path / "quality" / "active_risks.json"
    _write_json(registry_path, registry)

    report = audit_active_risks.audit_active_risks(tmp_path, registry_path=registry_path)

    assert report["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} >= {
        "active_risk_missing_owner",
        "active_risk_missing_acceptance",
        "missing_test_node",
        "active_archive_source_not_registered",
    }
