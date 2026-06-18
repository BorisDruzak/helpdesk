from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_PATH = ROOT / "test_data_packs" / "web_first_phase_e.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _check(name: str, passed: bool, message: str, **extra: str) -> dict[str, str]:
    item = {
        "name": name,
        "status": "pass" if passed else "fail",
        "message": message,
    }
    item.update({key: value for key, value in extra.items() if value})
    return item


def _browser_evidence_requirements(pack: dict[str, Any]) -> list[tuple[str, str]]:
    requirements: list[tuple[str, str]] = []
    for row in pack.get("validation_matrix") or []:
        if not isinstance(row, dict):
            continue
        gate = _text(row.get("gate"))
        for evidence in row.get("evidence") or []:
            evidence_key = _text(evidence)
            if gate and evidence_key.startswith("browser_"):
                requirements.append((gate, evidence_key))
    return requirements


def _evidence_items(manifest: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    items: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(manifest, dict):
        return items
    for item in manifest.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        gate = _text(item.get("gate"))
        evidence = _text(item.get("evidence"))
        if gate and evidence:
            items[(gate, evidence)] = item
    return items


def _has_artifact(item: dict[str, Any]) -> bool:
    return bool(
        _text(item.get("path"))
        or _text(item.get("artifact"))
        or _text(item.get("screenshot"))
        or _text(item.get("dom_snapshot"))
    )


def _is_real_browser_pass(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    return item.get("status") == "pass" and item.get("surface") == "real_browser" and _has_artifact(item)


def validate_phase_e_live_gate(
    pack: dict[str, Any],
    vm_snapshot_check: dict[str, Any],
    evidence_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    vm_check_passed = vm_snapshot_check.get("status") == "pass"
    checks.append(
        _check(
            "vm_snapshot_check",
            vm_check_passed,
            "Phase E VM snapshot checker must pass before broad live testing",
        )
    )

    manifest_schema_ok = (
        evidence_manifest is None
        or evidence_manifest.get("schema") == "web_first_phase_e_broad_live_evidence_v1"
    )
    checks.append(
        _check(
            "evidence_manifest_schema",
            manifest_schema_ok,
            "evidence manifest must use schema web_first_phase_e_broad_live_evidence_v1",
        )
    )

    items = _evidence_items(evidence_manifest)
    browser_failures = 0
    for gate, evidence in _browser_evidence_requirements(pack):
        item = items.get((gate, evidence))
        passed = _is_real_browser_pass(item)
        if not passed:
            browser_failures += 1
        checks.append(
            _check(
                "browser_evidence",
                passed,
                "browser-required matrix evidence must be real_browser, pass, and have an artifact path",
                gate=gate,
                evidence=evidence,
            )
        )

    declared_pass = isinstance(evidence_manifest, dict) and evidence_manifest.get("status") == "pass"
    checks.append(
        _check(
            "pass_claim_requires_browser_evidence",
            not declared_pass or browser_failures == 0,
            "broad live status=pass is invalid without required browser evidence",
        )
    )

    failed_checks = sum(1 for item in checks if item["status"] == "fail")
    return {
        "schema": "web_first_phase_e_live_gate_check_v1",
        "status": "pass" if failed_checks == 0 else "fail",
        "summary": {
            "failed_checks": failed_checks,
            "passed_checks": len(checks) - failed_checks,
            "browser_requirements": len(_browser_evidence_requirements(pack)),
        },
        "checks": checks,
    }


def _print_text_report(result: dict[str, Any]) -> None:
    print(f"Phase E live gate check: {result['status']}")
    summary = result["summary"]
    print(
        "Checks: "
        f"{summary['passed_checks']} passed, {summary['failed_checks']} failed, "
        f"{summary['browser_requirements']} browser requirements"
    )
    for check in result["checks"]:
        if check["status"] == "fail":
            suffix = ""
            if "gate" in check and "evidence" in check:
                suffix = f" [{check['gate']}:{check['evidence']}]"
            print(f"- FAIL {check['name']}{suffix}: {check['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase E broad-live gate evidence.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK_PATH)
    parser.add_argument("--vm-check", type=Path, required=True, help="JSON report from check_phase_e_vm_snapshot.py.")
    parser.add_argument("--evidence-manifest", type=Path, help="Broad-live evidence manifest JSON.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    result = validate_phase_e_live_gate(
        _load_json(args.pack),
        _load_json(args.vm_check),
        _load_json(args.evidence_manifest) if args.evidence_manifest else None,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
