from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_PATH = ROOT / "test_data_packs" / "web_first_phase_e.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(name: str, passed: bool, message: str, *, agent: str | None = None) -> dict[str, str]:
    item = {
        "name": name,
        "status": "pass" if passed else "fail",
        "message": message,
    }
    if agent is not None:
        item["agent"] = agent
    return item


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _module_snapshot_is_collected(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("collected") is not True:
        return False
    modules = value.get("modules")
    if isinstance(modules, list) and len(modules) > 0:
        return True
    module_count = value.get("module_count")
    return isinstance(module_count, int) and module_count > 0


def _manual_review_is_clean(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    reviewer = value.get("reviewed_by") or value.get("reviewer")
    return value.get("status") == "clean" and _non_empty_text(reviewer)


def validate_phase_e_vm_snapshot(pack: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    agent_results: list[dict[str, Any]] = []

    checks.append(
        _check(
            "snapshot_schema",
            snapshot.get("schema") == "web_first_phase_e_vm_snapshot_v1",
            "snapshot schema must be web_first_phase_e_vm_snapshot_v1",
        )
    )

    required_agents = pack.get("vm_agents") or []
    snapshot_agents = {
        item.get("key"): item
        for item in snapshot.get("agents", [])
        if isinstance(item, dict) and _non_empty_text(item.get("key"))
    }

    required_device_ids: list[tuple[str, str]] = []
    for required in required_agents:
        key = str(required.get("key") or "")
        actual = snapshot_agents.get(key)
        agent_checks: list[dict[str, str]] = []
        present = isinstance(actual, dict)
        agent_checks.append(_check("agent_present", present, "required VM agent is present", agent=key))

        if not present:
            checks.extend(agent_checks)
            agent_results.append({"key": key, "status": "fail", "checks": agent_checks})
            continue

        device_id = actual.get("device_id")
        if _non_empty_text(device_id):
            required_device_ids.append((key, str(device_id)))

        registry_device = actual.get("registry_device")
        registry_source = registry_device.get("source") if isinstance(registry_device, dict) else None
        registry_device_id = registry_device.get("device_id") if isinstance(registry_device, dict) else None

        agent_checks.extend(
            [
                _check(
                    "os",
                    actual.get("os") == required.get("os"),
                    f"agent OS must match pack value {required.get('os')}",
                    agent=key,
                ),
                _check("device_id", _non_empty_text(device_id), "live registry device_id is present", agent=key),
                _check(
                    "registry_device",
                    registry_source == required.get("device_id_source") and registry_device_id == device_id,
                    "registry_device evidence must come from live_registry and match device_id",
                    agent=key,
                ),
                _check(
                    "bound_requester",
                    actual.get("bound_requester") == required.get("bound_requester"),
                    "bound requester must match the Phase E data pack",
                    agent=key,
                ),
                _check(
                    "primary_active_binding",
                    required.get("primary_active_binding_required") is not True
                    or actual.get("primary_active_binding") is True,
                    "primary active binding must be true",
                    agent=key,
                ),
                _check("agent_online", actual.get("agent_online") is True, "agent online snapshot must be true", agent=key),
                _check(
                    "module_snapshot",
                    required.get("module_snapshot_required") is not True
                    or _module_snapshot_is_collected(actual.get("module_snapshot")),
                    "module snapshot must be collected and non-empty",
                    agent=key,
                ),
                _check(
                    "manual_contamination_review",
                    required.get("manual_contamination_check_required") is not True
                    or _manual_review_is_clean(actual.get("manual_contamination_review")),
                    "manual contamination review must be clean and reviewed",
                    agent=key,
                ),
            ]
        )

        checks.extend(agent_checks)
        agent_results.append(
            {
                "key": key,
                "device_id": device_id,
                "status": "pass" if all(item["status"] == "pass" for item in agent_checks) else "fail",
                "checks": agent_checks,
            }
        )

    duplicate_ids = {
        device_id
        for _, device_id in required_device_ids
        if sum(1 for _, candidate in required_device_ids if candidate == device_id) > 1
    }
    duplicate_agents = sorted(key for key, device_id in required_device_ids if device_id in duplicate_ids)
    checks.append(
        _check(
            "unique_device_id",
            not duplicate_ids,
            "required VM agents must have unique live registry device_id values"
            if not duplicate_ids
            else f"duplicate device_id across agents: {', '.join(duplicate_agents)}",
        )
    )

    failed_checks = sum(1 for item in checks if item["status"] == "fail")
    return {
        "schema": "web_first_phase_e_vm_snapshot_check_v1",
        "status": "pass" if failed_checks == 0 else "fail",
        "summary": {
            "required_agents": len(required_agents),
            "passed_checks": len(checks) - failed_checks,
            "failed_checks": failed_checks,
        },
        "agents": agent_results,
        "checks": checks,
    }


def _print_text_report(result: dict[str, Any]) -> None:
    print(f"Phase E VM snapshot check: {result['status']}")
    summary = result["summary"]
    print(
        "Checks: "
        f"{summary['passed_checks']} passed, {summary['failed_checks']} failed, "
        f"{summary['required_agents']} required agents"
    )
    for check in result["checks"]:
        if check["status"] == "fail":
            agent = f" [{check['agent']}]" if "agent" in check else ""
            print(f"- FAIL {check['name']}{agent}: {check['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase E VM-agent live snapshot evidence.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK_PATH)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    result = validate_phase_e_vm_snapshot(_load_json(args.pack), _load_json(args.snapshot))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
