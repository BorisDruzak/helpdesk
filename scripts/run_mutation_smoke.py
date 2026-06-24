#!/usr/bin/env python3
"""Run targeted mutation smoke checks for critical pure logic."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path("quality/mutation_smoke_targets.json")
SCHEMA = "pc_client.mutation_smoke.v1"
COPY_ROOTS = ("server", "shared", "scripts", "quality", "mcp_helpdesk_server")
IGNORE_NAMES = {
    ".pytest_cache",
    "__pycache__",
    "artifacts",
    "node_modules",
    ".git",
    ".venvs",
    "venv",
    "dist",
    "build",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _issue(code: str, message: str, *, mutant_id: str | None = None) -> dict[str, str]:
    payload = {"code": code, "message": message}
    if mutant_id:
        payload["mutant_id"] = mutant_id
    return payload


def _load_registry(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, [_issue("missing_registry", f"registry does not exist: {path}")]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("invalid_registry_json", f"{type(exc).__name__}: {exc}")]
    if not isinstance(payload, dict):
        return None, [_issue("invalid_registry", "registry root must be an object")]
    issues: list[dict[str, str]] = []
    if payload.get("schema") != SCHEMA:
        issues.append(_issue("invalid_schema", f"schema must be {SCHEMA}"))
    if not isinstance(payload.get("mutants"), list):
        issues.append(_issue("invalid_mutants", "mutants must be a list"))
    return payload, issues


def _ignore_copy(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES or name.endswith(".pyc")}


def _prepare_temp_workspace(workspace: Path, temp_workspace: Path) -> None:
    for root_name in COPY_ROOTS:
        source = workspace / root_name
        if not source.exists():
            continue
        destination = temp_workspace / root_name
        if source.is_dir():
            shutil.copytree(source, destination, ignore=_ignore_copy)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _apply_replacements(text: str, replacements: list[dict[str, Any]], *, mutant_id: str) -> tuple[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    mutated = text
    for index, replacement in enumerate(replacements):
        old = replacement.get("old") if isinstance(replacement, dict) else None
        new = replacement.get("new") if isinstance(replacement, dict) else None
        count = int(replacement.get("count", 1)) if isinstance(replacement, dict) else 1
        if not isinstance(old, str) or not old:
            issues.append(_issue("invalid_replacement", f"replacement {index} old text is required", mutant_id=mutant_id))
            continue
        if not isinstance(new, str):
            issues.append(_issue("invalid_replacement", f"replacement {index} new text must be a string", mutant_id=mutant_id))
            continue
        occurrences = mutated.count(old)
        if occurrences < count:
            issues.append(
                _issue(
                    "replacement_not_found",
                    f"replacement {index} expected {count} occurrence(s), found {occurrences}",
                    mutant_id=mutant_id,
                )
            )
            continue
        mutated = mutated.replace(old, new, count)
    return mutated, issues


def _run_pytest(workspace: Path, tests: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=short"],
        cwd=workspace,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )


def _output_tail(text: str, *, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_mutation_smoke(
    workspace: Path,
    *,
    registry_path: Path | None = None,
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    registry = registry_path or workspace / DEFAULT_REGISTRY
    if not registry.is_absolute():
        registry = workspace / registry
    payload, issues = _load_registry(registry)
    raw_mutants = payload.get("mutants") if isinstance(payload, dict) and isinstance(payload.get("mutants"), list) else []
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="pc-client-mutation-") as temp_dir:
        temp_workspace = Path(temp_dir) / "workspace"
        temp_workspace.mkdir(parents=True, exist_ok=True)
        _prepare_temp_workspace(workspace, temp_workspace)

        for raw_mutant in raw_mutants:
            if not isinstance(raw_mutant, dict):
                issues.append(_issue("invalid_mutant", "mutant entry must be an object"))
                continue
            mutant_id = str(raw_mutant.get("id") or "").strip()
            if not mutant_id:
                issues.append(_issue("missing_mutant_id", "mutant id is required"))
                continue
            if mutant_id in seen_ids:
                issues.append(_issue("duplicate_mutant_id", f"duplicate mutant id: {mutant_id}", mutant_id=mutant_id))
                continue
            seen_ids.add(mutant_id)
            file_path = str(raw_mutant.get("file") or "").replace("\\", "/").strip()
            tests = raw_mutant.get("tests")
            replacements = raw_mutant.get("replacements")
            result: dict[str, Any] = {
                "id": mutant_id,
                "file": file_path,
                "tests": tests if isinstance(tests, list) else [],
            }
            results.append(result)
            if not file_path:
                result["status"] = "config_error"
                issues.append(_issue("missing_file", "mutant file is required", mutant_id=mutant_id))
                continue
            if not isinstance(tests, list) or not tests:
                result["status"] = "config_error"
                issues.append(_issue("missing_tests", "mutant tests list is required", mutant_id=mutant_id))
                continue
            if not isinstance(replacements, list) or not replacements:
                result["status"] = "config_error"
                issues.append(_issue("missing_replacements", "mutant replacements list is required", mutant_id=mutant_id))
                continue
            target_path = temp_workspace / file_path
            if not target_path.exists():
                result["status"] = "config_error"
                issues.append(_issue("missing_target_file", f"target file does not exist: {file_path}", mutant_id=mutant_id))
                continue
            original = target_path.read_text(encoding="utf-8")
            mutated, replacement_issues = _apply_replacements(original, replacements, mutant_id=mutant_id)
            if replacement_issues:
                result["status"] = "config_error"
                issues.extend(replacement_issues)
                continue
            target_path.write_text(mutated, encoding="utf-8")
            try:
                completed = _run_pytest(temp_workspace, [str(test) for test in tests], timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                result.update(
                    {
                        "status": "killed",
                        "returncode": 124,
                        "timeout": True,
                        "stdout_tail": _output_tail(exc.stdout or ""),
                        "stderr_tail": _output_tail(exc.stderr or ""),
                    }
                )
            else:
                if completed.returncode == 0:
                    status = "survived"
                elif completed.returncode == 1:
                    status = "killed"
                else:
                    status = "infrastructure_error"
                result.update(
                    {
                        "status": status,
                        "returncode": completed.returncode,
                        "timeout": False,
                        "stdout_tail": _output_tail(completed.stdout),
                        "stderr_tail": _output_tail(completed.stderr),
                    }
                )
                if status == "survived":
                    issues.append(_issue("mutant_survived", f"mutant survived: {mutant_id}", mutant_id=mutant_id))
                elif status == "infrastructure_error":
                    issues.append(
                        _issue(
                            "mutation_infrastructure_error",
                            f"pytest returned {completed.returncode} before proving mutant death",
                            mutant_id=mutant_id,
                        )
                    )
            finally:
                target_path.write_text(original, encoding="utf-8")

    return {
        "schema": "pc_client.mutation_smoke_report.v1",
        "registry_path": str(registry),
        "status": "fail" if issues else "ok",
        "mutant_count": len(results),
        "killed_count": sum(1 for result in results if result.get("status") == "killed"),
        "survived_count": sum(1 for result in results if result.get("status") == "survived"),
        "issues": issues,
        "mutants": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_mutation_smoke(args.workspace, registry_path=args.registry, timeout_seconds=args.timeout)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "mutation smoke: "
            f"mutants={report['mutant_count']} killed={report['killed_count']} "
            f"survived={report['survived_count']} issues={len(report['issues'])}"
        )
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue['message']} {issue.get('mutant_id', '')}".rstrip())
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
