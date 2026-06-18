from __future__ import annotations

import json

import pytest

import scripts.check_phase_e_live_gate as live_gate


pytestmark = pytest.mark.no_db


def _pack() -> dict:
    return {
        "schema": "web_first_phase_e_test_data_pack_v1",
        "validation_matrix": [
            {
                "gate": "ticket_context_v1",
                "evidence": ["pytest", "browser_ticket_create"],
            },
            {
                "gate": "support_detail_context",
                "evidence": ["pytest", "browser_support_ticket_detail"],
            },
        ],
    }


def _vm_check(status: str = "pass") -> dict:
    return {
        "schema": "web_first_phase_e_vm_snapshot_check_v1",
        "status": status,
        "summary": {"failed_checks": 0 if status == "pass" else 2},
    }


def _manifest(*items: dict, status: str = "pass") -> dict:
    return {
        "schema": "web_first_phase_e_broad_live_evidence_v1",
        "status": status,
        "evidence": list(items),
    }


def _browser_item(gate: str, evidence: str) -> dict:
    return {
        "gate": gate,
        "evidence": evidence,
        "status": "pass",
        "surface": "real_browser",
        "path": f"artifacts/browser_live_validation/run/{gate}-{evidence}.png",
    }


def test_phase_e_live_gate_blocks_failed_vm_snapshot_check() -> None:
    result = live_gate.validate_phase_e_live_gate(
        _pack(),
        _vm_check("fail"),
        _manifest(
            _browser_item("ticket_context_v1", "browser_ticket_create"),
            _browser_item("support_detail_context", "browser_support_ticket_detail"),
        ),
    )

    assert result["status"] == "fail"
    assert any(check["name"] == "vm_snapshot_check" and check["status"] == "fail" for check in result["checks"])


def test_phase_e_live_gate_rejects_green_claim_without_browser_evidence() -> None:
    result = live_gate.validate_phase_e_live_gate(
        _pack(),
        _vm_check("pass"),
        _manifest(
            {"gate": "ticket_context_v1", "evidence": "pytest", "status": "pass", "surface": "pytest"},
            {"gate": "support_detail_context", "evidence": "pytest", "status": "pass", "surface": "pytest"},
        ),
    )

    assert result["status"] == "fail"
    assert any(
        check["name"] == "browser_evidence"
        and check["gate"] == "ticket_context_v1"
        and check["status"] == "fail"
        for check in result["checks"]
    )
    assert any(check["name"] == "pass_claim_requires_browser_evidence" for check in result["checks"])


def test_phase_e_live_gate_passes_with_vm_check_and_required_browser_evidence() -> None:
    result = live_gate.validate_phase_e_live_gate(
        _pack(),
        _vm_check("pass"),
        _manifest(
            _browser_item("ticket_context_v1", "browser_ticket_create"),
            _browser_item("support_detail_context", "browser_support_ticket_detail"),
        ),
    )

    assert result["status"] == "pass"
    assert result["summary"]["failed_checks"] == 0


def test_phase_e_live_gate_cli_returns_nonzero_for_blocked_gate(tmp_path) -> None:
    pack_path = tmp_path / "pack.json"
    vm_check_path = tmp_path / "vm-check.json"
    manifest_path = tmp_path / "manifest.json"
    pack_path.write_text(json.dumps(_pack()), encoding="utf-8")
    vm_check_path.write_text(json.dumps(_vm_check("fail")), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(_manifest(_browser_item("ticket_context_v1", "browser_ticket_create"))),
        encoding="utf-8",
    )

    assert live_gate.main(
        [
            "--pack",
            str(pack_path),
            "--vm-check",
            str(vm_check_path),
            "--evidence-manifest",
            str(manifest_path),
            "--json",
        ]
    ) == 1


def test_phase_e_live_gate_cli_accepts_powershell_utf8_bom_reports(tmp_path) -> None:
    pack_path = tmp_path / "pack.json"
    vm_check_path = tmp_path / "vm-check.json"
    manifest_path = tmp_path / "manifest.json"
    pack_path.write_text(json.dumps(_pack()), encoding="utf-8")
    vm_check_path.write_text(json.dumps(_vm_check("pass")), encoding="utf-8-sig")
    manifest_path.write_text(
        json.dumps(
            _manifest(
                _browser_item("ticket_context_v1", "browser_ticket_create"),
                _browser_item("support_detail_context", "browser_support_ticket_detail"),
            )
        ),
        encoding="utf-8-sig",
    )

    assert live_gate.main(
        [
            "--pack",
            str(pack_path),
            "--vm-check",
            str(vm_check_path),
            "--evidence-manifest",
            str(manifest_path),
            "--json",
        ]
    ) == 0
