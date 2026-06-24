"""Summarize pytest fixture timing JSONL artifacts."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable


DEFAULT_FIXTURE_TIMING_BUDGETS: dict[str, dict[str, dict[str, float]]] = {
    "run_migrations": {"setup": {"p95_seconds": 120.0, "max_seconds": 180.0}},
    "cleanup_db": {"setup": {"p95_seconds": 30.0, "max_seconds": 45.0}},
    "_cleanup_db_async": {"call": {"p95_seconds": 30.0, "max_seconds": 45.0}},
    "test_app": {"setup": {"p95_seconds": 5.0, "max_seconds": 8.0}, "teardown": {"p95_seconds": 5.0, "max_seconds": 8.0}},
    "test_app_light": {
        "setup": {"p95_seconds": 3.0, "max_seconds": 5.0},
        "teardown": {"p95_seconds": 3.0, "max_seconds": 5.0},
    },
    "test_client": {"setup": {"p95_seconds": 5.0, "max_seconds": 8.0}, "teardown": {"p95_seconds": 5.0, "max_seconds": 8.0}},
    "test_client_light": {
        "setup": {"p95_seconds": 3.0, "max_seconds": 5.0},
        "teardown": {"p95_seconds": 3.0, "max_seconds": 5.0},
    },
    "test_agent": {"setup": {"p95_seconds": 60.0, "max_seconds": 90.0}, "teardown": {"p95_seconds": 30.0, "max_seconds": 45.0}},
}


def _round_seconds(value: float) -> float:
    return round(float(value), 6)


def _percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _stats(values: list[float]) -> dict[str, float | int]:
    total = sum(values)
    return {
        "count": len(values),
        "total_seconds": _round_seconds(total),
        "avg_seconds": _round_seconds(total / len(values)) if values else 0.0,
        "p50_seconds": _round_seconds(median(values)) if values else 0.0,
        "p95_seconds": _round_seconds(_percentile_nearest_rank(values, 95.0)),
        "max_seconds": _round_seconds(max(values)) if values else 0.0,
    }


def _timing_files(timings_dir: Path) -> list[Path]:
    if not timings_dir.exists():
        return []
    return sorted(path for path in timings_dir.glob("*.jsonl") if path.is_file())


def _load_records(files: Iterable[Path]) -> tuple[dict[str, dict[str, list[float]]], int, int]:
    grouped: dict[str, dict[str, list[float]]] = {}
    valid_count = 0
    invalid_count = 0
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    fixture = str(record["fixture"])
                    phase = str(record.get("phase") or "unknown")
                    duration_seconds = float(record["duration_seconds"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    invalid_count += 1
                    continue
                grouped.setdefault(fixture, {}).setdefault(phase, []).append(duration_seconds)
                profile = record.get("profile")
                if isinstance(profile, str) and profile:
                    profile_fixture = f"{fixture}:{profile}"
                    grouped.setdefault(profile_fixture, {}).setdefault(phase, []).append(duration_seconds)
                valid_count += 1
    return grouped, valid_count, invalid_count


def _apply_budgets(
    fixtures: dict[str, dict[str, dict[str, float | int]]],
    budgets: dict[str, dict[str, dict[str, float]]],
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for fixture, phases in fixtures.items():
        fixture_budget = budgets.get(fixture)
        if not fixture_budget:
            continue
        for phase, stats in phases.items():
            phase_budget = fixture_budget.get(phase)
            if not phase_budget:
                continue
            stats["budget"] = {metric: _round_seconds(limit) for metric, limit in sorted(phase_budget.items())}
            for metric, limit in sorted(phase_budget.items()):
                actual = float(stats.get(metric) or 0.0)
                if actual > limit:
                    violations.append(
                        {
                            "fixture": fixture,
                            "phase": phase,
                            "metric": metric,
                            "actual_seconds": _round_seconds(actual),
                            "budget_seconds": _round_seconds(limit),
                        }
                    )
    return violations


def summarize_artifact_dir(
    artifact_dir: Path | str,
    *,
    timings_dir: Path | str | None = None,
    output_path: Path | str | None = None,
    budgets: dict[str, dict[str, dict[str, float]]] | None = None,
) -> dict[str, object]:
    artifact_dir = Path(artifact_dir)
    timings_dir = Path(timings_dir) if timings_dir is not None else artifact_dir / "fixture-timings"
    output_path = Path(output_path) if output_path is not None else artifact_dir / "fixture-timings-summary.json"

    files = _timing_files(timings_dir)
    grouped, valid_count, invalid_count = _load_records(files)
    fixtures = {
        fixture: {phase: _stats(values) for phase, values in sorted(phases.items())}
        for fixture, phases in sorted(grouped.items())
    }
    budget_violations = _apply_budgets(fixtures, DEFAULT_FIXTURE_TIMING_BUDGETS if budgets is None else budgets)
    if not valid_count:
        budget_status = "no_data"
    elif budget_violations:
        budget_status = "fail"
    else:
        budget_status = "pass"
    summary: dict[str, object] = {
        "schema": "pc_client.fixture_timings_summary.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": str(artifact_dir),
        "timings_dir": str(timings_dir),
        "files": [str(path) for path in files],
        "record_count": valid_count,
        "invalid_record_count": invalid_count,
        "budget_profile": "default" if budgets is None else "custom",
        "budget_status": budget_status,
        "budget_violations": budget_violations,
        "fixtures": fixtures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return summary


def _print_summary(summary: dict[str, object]) -> None:
    fixtures = summary.get("fixtures", {})
    print("fixture phase count total avg p50 p95 max")
    if not isinstance(fixtures, dict):
        return
    for fixture, phases in fixtures.items():
        if not isinstance(phases, dict):
            continue
        for phase, stats in phases.items():
            if not isinstance(stats, dict):
                continue
            print(
                f"{fixture} {phase} {stats.get('count', 0)} "
                f"{stats.get('total_seconds', 0.0)} {stats.get('avg_seconds', 0.0)} "
                f"{stats.get('p50_seconds', 0.0)} {stats.get('p95_seconds', 0.0)} "
                f"{stats.get('max_seconds', 0.0)}"
            )
    print(f"fixture timing budget: {summary.get('budget_status')}")
    violations = summary.get("budget_violations")
    if isinstance(violations, list):
        for item in violations:
            if not isinstance(item, dict):
                continue
            print(
                f"budget violation: {item.get('fixture')}/{item.get('phase')} "
                f"{item.get('metric')}={item.get('actual_seconds')} > {item.get('budget_seconds')}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path, help="CI artifact dir, for example artifacts/ci/<sha>.")
    parser.add_argument("--timings-dir", type=Path, help="Override fixture-timings JSONL directory.")
    parser.add_argument("--output", type=Path, help="Override summary JSON output path.")
    parser.add_argument("--enforce-budget", action="store_true", help="Exit non-zero when fixture timing budgets fail.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = summarize_artifact_dir(
        args.artifact_dir,
        timings_dir=args.timings_dir,
        output_path=args.output,
    )
    _print_summary(summary)
    return 1 if args.enforce_budget and summary.get("budget_status") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
