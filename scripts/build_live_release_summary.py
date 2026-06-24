#!/usr/bin/env python3
"""Build one release summary from critical live evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_live_behavior_suite  # noqa: E402
from scripts.validate_live_evidence import load_manifest, validate_manifest  # noqa: E402

DEFAULT_PACK_PATH = ROOT / "test_data_packs" / "critical_behavior_v1.json"
DEFAULT_LIVE_ROOT = ROOT / "artifacts" / "live"
SCHEMA = "pc_client.live_release_summary.v1"


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pack(path: Path | str) -> Mapping[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("critical behavior pack root must be an object")
    return data


def iter_live_scenarios(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for domain in pack.get("domains") or []:
        if not isinstance(domain, dict):
            continue
        for scenario in domain.get("live_scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            scenarios.append(
                {
                    "domain_key": str(domain.get("key") or ""),
                    "owner": domain.get("owner"),
                    "priority": domain.get("priority"),
                    "scenario_key": str(scenario.get("key") or ""),
                    "surface": str(scenario.get("surface") or ""),
                    "required_evidence": list(scenario.get("required_evidence") or []),
                    "manifest_requirements": list(scenario.get("manifest_requirements") or []),
                    "expected_outcomes": list(scenario.get("expected_outcomes") or []),
                }
            )
    return scenarios


def _manifest_scenario_key(manifest: Mapping[str, Any]) -> str:
    explicit = str(manifest.get("scenario_key") or "").strip()
    if explicit:
        return explicit
    entities = manifest.get("entities")
    if isinstance(entities, dict):
        entity_scenario = str(entities.get("scenario_key") or "").strip()
        if entity_scenario:
            return entity_scenario
    return str(manifest.get("scenario") or "").strip()


def _manifest_release_run_id(manifest: Mapping[str, Any]) -> str:
    explicit = str(manifest.get("release_run_id") or "").strip()
    if explicit:
        return explicit
    release = manifest.get("release")
    if isinstance(release, Mapping):
        return str(release.get("run_id") or "").strip()
    return ""


def _manifest_expected_schema_head(manifest: Mapping[str, Any]) -> str:
    preflight = manifest.get("preflight")
    if isinstance(preflight, Mapping):
        return str(preflight.get("expected_schema_head") or "").strip()
    return ""


def _matches_release_context(
    manifest: Mapping[str, Any],
    *,
    commit: str | None,
    environment: str | None,
    release_run_id: str | None,
    expected_schema_head: str | None,
) -> bool:
    if commit is not None and str(manifest.get("commit") or "").strip() != commit:
        return False
    if environment is not None and str(manifest.get("environment") or "").strip() != environment:
        return False
    if release_run_id is not None and _manifest_release_run_id(manifest) != release_run_id:
        return False
    if expected_schema_head is not None and _manifest_expected_schema_head(manifest) != expected_schema_head:
        return False
    return True


def collect_manifest_summaries(
    live_root: Path,
    *,
    commit: str | None = None,
    environment: str | None = None,
    release_run_id: str | None = None,
    expected_schema_head: str | None = None,
) -> list[dict[str, Any]]:
    if not live_root.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for manifest_path in sorted(live_root.glob("**/manifest.json")):
        try:
            manifest = load_manifest(manifest_path)
            if not _matches_release_context(
                manifest,
                commit=commit,
                environment=environment,
                release_run_id=release_run_id,
                expected_schema_head=expected_schema_head,
            ):
                continue
            errors = validate_manifest(manifest, manifest_dir=manifest_path.parent)
            manifest_status = str(manifest.get("status") or "")
            validation_status = "pass" if manifest_status == "pass" and not errors else "fail"
            summaries.append(
                {
                    "path": _repo_rel(manifest_path),
                    "run_id": manifest.get("run_id"),
                    "release_run_id": _manifest_release_run_id(manifest) or None,
                    "commit": manifest.get("commit"),
                    "environment": manifest.get("environment"),
                    "expected_schema_head": _manifest_expected_schema_head(manifest) or None,
                    "scenario": manifest.get("scenario"),
                    "scenario_key": _manifest_scenario_key(manifest),
                    "status": manifest_status,
                    "validation_status": validation_status,
                    "validation_errors": errors,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive corrupted-artifact path
            summaries.append(
                {
                    "path": _repo_rel(manifest_path),
                    "run_id": None,
                    "scenario": None,
                    "scenario_key": "",
                    "status": "unreadable",
                    "validation_status": "fail",
                    "validation_errors": [str(exc)],
                }
            )
    return summaries


def _suite_plan(pack: Mapping[str, Any]) -> dict[str, int]:
    browser_scenarios = run_live_behavior_suite.discover_browser_scenarios(
        pack,
        surfaces={"requester", "support"},
    )
    agent_scenarios = run_live_behavior_suite.discover_agent_operation_scenarios(pack)
    return {
        "browser_scenarios": len(browser_scenarios),
        "agent_operation_scenarios": len(agent_scenarios),
    }


def build_summary(
    *,
    pack_path: Path,
    live_root: Path,
    commit: str | None = None,
    environment: str | None = None,
    release_run_id: str | None = None,
    expected_schema_head: str | None = None,
) -> dict[str, Any]:
    pack = load_pack(pack_path)
    scenarios = iter_live_scenarios(pack)
    scenario_keys = [scenario["scenario_key"] for scenario in scenarios if scenario["scenario_key"]]
    required_sections = sorted(
        {
            section
            for scenario in scenarios
            for section in scenario["manifest_requirements"]
            if isinstance(section, str) and section
        }
    )
    manifests = collect_manifest_summaries(
        live_root,
        commit=commit,
        environment=environment,
        release_run_id=release_run_id,
        expected_schema_head=expected_schema_head,
    )
    required_key_set = set(scenario_keys)
    scenario_status: dict[str, str] = {}
    for item in manifests:
        scenario_key = str(item.get("scenario_key") or "")
        if scenario_key not in required_key_set:
            continue
        if item.get("validation_status") == "pass":
            scenario_status.setdefault(scenario_key, "pass")
        else:
            scenario_status[scenario_key] = "fail"
    passed_key_set = {key for key, status in scenario_status.items() if status == "pass"}
    failed_key_set = {key for key, status in scenario_status.items() if status == "fail"}
    missing_keys = [key for key in scenario_keys if key not in scenario_status]
    failed_keys = [key for key in scenario_keys if key in failed_key_set]

    release_blockers: list[str] = []
    if failed_keys:
        release_blockers.append(f"failing live evidence manifest for: {', '.join(failed_keys)}")
    if missing_keys:
        release_blockers.append(f"missing passing live evidence manifest for: {', '.join(missing_keys)}")

    if failed_keys:
        status = "fail"
    elif missing_keys:
        status = "blocked"
    else:
        status = "pass"

    return {
        "schema": SCHEMA,
        "generated_at": _utc_now(),
        "status": status,
        "release_context": {
            "commit": commit,
            "environment": environment,
            "release_run_id": release_run_id,
            "expected_schema_head": expected_schema_head,
        },
        "pack": _repo_rel(pack_path),
        "pack_schema": pack.get("schema"),
        "pack_version": pack.get("version"),
        "domain_count": len(pack.get("domains") or []),
        "required_manifest_sections": required_sections,
        "suite_plan": _suite_plan(pack),
        "coverage": {
            "scenario_count": len(scenario_keys),
            "required_scenario_keys": scenario_keys,
            "passed_scenario_keys": [key for key in scenario_keys if key in passed_key_set],
            "failed_scenario_keys": failed_keys,
            "missing_scenario_keys": missing_keys,
        },
        "live_manifests": manifests,
        "release_blockers": release_blockers,
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    blockers = summary.get("release_blockers") if isinstance(summary.get("release_blockers"), list) else []
    release_context = summary.get("release_context") if isinstance(summary.get("release_context"), dict) else {}
    lines = [
        "# Live Release Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generated_at')}`",
        f"- Pack: `{summary.get('pack')}`",
        f"- Commit: `{release_context.get('commit')}`",
        f"- Environment: `{release_context.get('environment')}`",
        f"- Release run: `{release_context.get('release_run_id')}`",
        f"- Expected schema: `{release_context.get('expected_schema_head')}`",
        f"- Scenarios: `{coverage.get('scenario_count', 0)}`",
        f"- Passed: `{len(coverage.get('passed_scenario_keys') or [])}`",
        f"- Missing: `{len(coverage.get('missing_scenario_keys') or [])}`",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Scenarios", "", "| Scenario | Status |", "| --- | --- |"])
    passed = set(coverage.get("passed_scenario_keys") or [])
    failed = set(coverage.get("failed_scenario_keys") or [])
    for key in coverage.get("required_scenario_keys") or []:
        if key in passed:
            status = "pass"
        elif key in failed:
            status = "fail"
        else:
            status = "missing"
        lines.append(f"| `{key}` | {status} |")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK_PATH)
    parser.add_argument("--live-root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--environment")
    parser.add_argument("--release-run-id")
    parser.add_argument("--expected-schema-head")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_summary(
        pack_path=args.pack,
        live_root=args.live_root,
        commit=args.commit,
        environment=args.environment,
        release_run_id=args.release_run_id,
        expected_schema_head=args.expected_schema_head,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(summary), encoding="utf-8")
    if args.json_output or not args.output:
        print(payload, end="")
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
