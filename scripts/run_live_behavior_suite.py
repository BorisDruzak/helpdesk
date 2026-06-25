#!/usr/bin/env python3
"""Run or plan live behavior browser scenarios from a critical behavior pack."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import live_evidence_pack  # noqa: E402

DEFAULT_PACK_PATH = ROOT / "test_data_packs" / "critical_behavior_v1.json"
DEFAULT_BROWSER_SCRIPT = Path("webapp/scripts/live-browser-scenarios.mjs")
DEFAULT_UIA_PROBE = Path("scripts/live_agent_uia_state_probe.py")
DEFAULT_WS_PROBE = Path("scripts/live_ws_v3_probe.py")
DEFAULT_BROWSER_SURFACES = ("requester", "support", "admin", "reports")
DEFAULT_BROWSER_SURFACES_CSV = ",".join(DEFAULT_BROWSER_SURFACES)
DEFAULT_BASE_URL = (
    os.environ.get("PC_CLIENT_BROWSER_BASE_URL")
    or os.environ.get("REMOTE_SMOKE_BASE_URL")
    or "https://192.168.100.17:9443"
)
DEFAULT_OUT_DIR = ROOT / "artifacts" / "live_behavior_suite"
AGENT_OPERATION_SURFACES = {"native_agent", "operation_lifecycle", "protocol_v3"}
BROWSER_EVIDENCE_SURFACES = set(DEFAULT_BROWSER_SURFACES)


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _split_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def load_pack(path: Path | str) -> Mapping[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("critical behavior pack root must be an object")
    return data


def discover_browser_scenarios(
    pack: Mapping[str, Any],
    *,
    surfaces: set[str] | None = None,
    scenario_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for domain in pack.get("domains") or []:
        if not isinstance(domain, dict):
            continue
        for scenario in domain.get("live_scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            surface = str(scenario.get("surface") or "")
            scenario_key = str(scenario.get("key") or "")
            required_evidence = list(scenario.get("required_evidence") or [])
            if "browser" not in required_evidence:
                continue
            if surfaces and surface not in surfaces:
                continue
            if scenario_keys and scenario_key not in scenario_keys:
                continue
            selected.append(
                {
                    "domain_key": domain.get("key"),
                    "owner": domain.get("owner"),
                    "priority": domain.get("priority"),
                    "scenario_key": scenario_key,
                    "surface": surface,
                    "required_evidence": required_evidence,
                    "manifest_requirements": list(scenario.get("manifest_requirements") or []),
                    "data_refs": scenario.get("data_refs") or {},
                    "expected_outcomes": list(scenario.get("expected_outcomes") or []),
                }
            )
    return selected


def discover_agent_operation_scenarios(
    pack: Mapping[str, Any],
    *,
    surfaces: set[str] | None = None,
    scenario_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for domain in pack.get("domains") or []:
        if not isinstance(domain, dict):
            continue
        for scenario in domain.get("live_scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            surface = str(scenario.get("surface") or "")
            scenario_key = str(scenario.get("key") or "")
            required_evidence = list(scenario.get("required_evidence") or [])
            is_agent_operation = surface in AGENT_OPERATION_SURFACES or "uia" in required_evidence
            if not is_agent_operation:
                continue
            if surfaces and surface not in surfaces:
                continue
            if scenario_keys and scenario_key not in scenario_keys:
                continue
            selected.append(
                {
                    "domain_key": domain.get("key"),
                    "owner": domain.get("owner"),
                    "priority": domain.get("priority"),
                    "scenario_key": scenario_key,
                    "surface": surface,
                    "required_evidence": required_evidence,
                    "manifest_requirements": list(scenario.get("manifest_requirements") or []),
                    "data_refs": scenario.get("data_refs") or {},
                    "expected_outcomes": list(scenario.get("expected_outcomes") or []),
                }
            )
    return selected


def _scenario_out_dir(out_dir: Path, scenario: Mapping[str, Any]) -> Path:
    return out_dir / f"{scenario['domain_key']}__{scenario['scenario_key']}"


def _evidence_run_id(scenario: Mapping[str, Any], release_run_id: str | None) -> str:
    scenario_key = str(scenario["scenario_key"])
    if release_run_id:
        return f"{release_run_id}__{scenario_key}"
    return f"{scenario['domain_key']}__{scenario_key}"


def build_browser_command(
    scenario: Mapping[str, Any],
    *,
    base_url: str,
    out_dir: Path,
    browser_script: Path = DEFAULT_BROWSER_SCRIPT,
) -> list[str]:
    scenario_out_dir = _scenario_out_dir(out_dir, scenario)
    return [
        "node",
        browser_script.as_posix(),
        "--base-url",
        base_url,
        "--out-dir",
        str(scenario_out_dir),
        "--domain",
        str(scenario["domain_key"]),
        "--scenario-key",
        str(scenario["scenario_key"]),
        "--surface",
        str(scenario["surface"]),
    ]


def build_agent_operation_command(
    scenario: Mapping[str, Any],
    *,
    out_dir: Path,
    uia_probe: Path = DEFAULT_UIA_PROBE,
    ws_probe: Path = DEFAULT_WS_PROBE,
) -> list[str]:
    scenario_out_dir = _scenario_out_dir(out_dir, scenario)
    surface = str(scenario["surface"])
    scenario_key = str(scenario["scenario_key"])
    if surface == "native_agent":
        return [
            "python",
            uia_probe.as_posix(),
            "--expect-connected",
            "--output",
            str(scenario_out_dir / "uia-state.json"),
            "--screenshot",
            str(scenario_out_dir / "uia-state.png"),
        ]
    if surface == "operation_lifecycle":
        return [
            "python",
            ws_probe.as_posix(),
            "--timeout",
            "15",
            "malformed-outbox",
            "--run-id",
            scenario_key,
        ]
    return [
        "python",
        ws_probe.as_posix(),
        "--timeout",
        "15",
        "double-connect",
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK_PATH)
    parser.add_argument("--mode", choices=["browser", "agent-operation"], default="browser")
    parser.add_argument("--surfaces", default=DEFAULT_BROWSER_SURFACES_CSV)
    parser.add_argument("--scenario-key", action="append", dest="scenario_keys")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--release-run-id")
    parser.add_argument("--commit")
    parser.add_argument("--deployed-commit")
    parser.add_argument("--environment")
    parser.add_argument("--branch")
    parser.add_argument("--expected-schema-head")
    parser.add_argument("--actual-schema-head")
    parser.add_argument("--browser-script", type=Path, default=DEFAULT_BROWSER_SCRIPT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def _render_text(summary: Mapping[str, Any]) -> str:
    lines = [
        f"live behavior suite: mode={summary['mode']} scenarios={summary['scenario_count']}",
        f"pack: {summary['pack']}",
        f"browser_script: {summary['browser_script']}",
    ]
    for item in summary["scenarios"]:
        lines.append(
            f"- {item['domain_key']}::{item['scenario_key']} surface={item['surface']} "
            f"exit_code={item.get('exit_code', 'n/a')}"
        )
        lines.append(f"  command: {' '.join(item['command'])}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pack = load_pack(args.pack)
    surfaces = _split_csv(args.surfaces)
    scenario_keys = set(args.scenario_keys or [])
    browser_script = args.browser_script
    if args.mode == "browser":
        scenarios = discover_browser_scenarios(pack, surfaces=surfaces, scenario_keys=scenario_keys or None)
    else:
        scenarios = discover_agent_operation_scenarios(pack, surfaces=surfaces, scenario_keys=scenario_keys or None)
    if not scenarios:
        print(f"No matching {args.mode} scenarios found.", flush=True)
        return 1
    if not args.dry_run and not (ROOT / browser_script).is_file():
        print(f"Browser script not found: {browser_script}", flush=True)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    exit_code = 0
    for scenario in scenarios:
        scenario_out_dir = _scenario_out_dir(args.out_dir, scenario)
        scenario_out_dir.mkdir(parents=True, exist_ok=True)
        if args.mode == "browser":
            command = build_browser_command(
                scenario,
                base_url=args.base_url,
                out_dir=args.out_dir,
                browser_script=browser_script,
            )
        else:
            command = build_agent_operation_command(
                scenario,
                out_dir=args.out_dir,
            )
        item = {
            **scenario,
            "command": command,
        }
        if args.evidence_root is not None:
            evidence = live_evidence_pack.create_pack(
                run_id=_evidence_run_id(scenario, args.release_run_id),
                surface=str(scenario["surface"]),
                artifacts_root=args.evidence_root,
                scenario_key=str(scenario["scenario_key"]),
                release_run_id=args.release_run_id,
                commit=args.commit,
                deployed_commit=args.deployed_commit,
                environment=args.environment,
                branch=args.branch,
                expected_schema_head=args.expected_schema_head,
                actual_schema_head=args.actual_schema_head,
            )
            item["evidence_manifest"] = str(evidence.output_dir / "manifest.json")
        if not args.dry_run:
            completed = subprocess.run(command, cwd=ROOT, check=False)
            item["exit_code"] = completed.returncode
            if completed.returncode != 0:
                exit_code = completed.returncode or 1
        items.append(item)

    summary = {
        "schema": "pc_client.live_behavior_suite_run.v1",
        "mode": "dry_run" if args.dry_run else "run",
        "runner_mode": args.mode,
        "pack": _repo_rel(args.pack),
        "browser_script": browser_script.as_posix(),
        "base_url": args.base_url,
        "scenario_count": len(items),
        "scenarios": items,
    }
    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(_render_text(summary))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
