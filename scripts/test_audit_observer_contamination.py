from __future__ import annotations

import json
from pathlib import Path

from scripts import audit_observer_contamination


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_evidence(workspace: Path) -> None:
    evidence = workspace / "docs" / "runbooks" / "observer_operation_lifecycle.md"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("# observer evidence\n", encoding="utf-8")


def _valid_manifest() -> dict:
    return {
        "schema": "pc_client.observer_known_contamination.v1",
        "last_reviewed": "2026-06-24",
        "contaminations": [
            {
                "id": "obs-p1-device-outbox-135",
                "status": "active",
                "source_phase": "P1",
                "owner_zone": "observer",
                "linked_issue": "TD-011",
                "entity_type": "device_outbox",
                "entity_id": "135",
                "suppression_scope": "observer_integrity",
                "reason": "Historical P1 malformed probe.",
                "created_at": "2026-06-24T00:00:00+00:00",
                "expires_at": "2099-07-24T00:00:00+00:00",
                "review_status": "reviewed",
                "evidence_path": "docs/runbooks/observer_operation_lifecycle.md",
            }
        ],
    }


def test_audit_observer_contamination_accepts_time_boxed_manifest(tmp_path: Path) -> None:
    _write_evidence(tmp_path)
    manifest_path = tmp_path / "quality" / "observer_known_contamination.json"
    _write_json(manifest_path, _valid_manifest())

    report = audit_observer_contamination.audit_observer_contamination(
        tmp_path,
        manifest_path=manifest_path,
    )

    assert report["status"] == "ok"
    assert report["contamination_count"] == 1
    assert report["active_count"] == 1
    assert report["issues"] == []


def test_audit_observer_contamination_rejects_indefinite_or_unowned_active_rows(tmp_path: Path) -> None:
    _write_evidence(tmp_path)
    manifest = _valid_manifest()
    row = manifest["contaminations"][0]
    row["expires_at"] = None
    row["owner_zone"] = ""
    row["evidence_path"] = "docs/runbooks/missing.md"
    manifest_path = tmp_path / "quality" / "observer_known_contamination.json"
    _write_json(manifest_path, manifest)

    report = audit_observer_contamination.audit_observer_contamination(
        tmp_path,
        manifest_path=manifest_path,
    )

    assert report["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} >= {
        "contamination_missing_owner",
        "contamination_missing_expires_at",
        "missing_evidence_path",
    }
