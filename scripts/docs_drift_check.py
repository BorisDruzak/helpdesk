#!/usr/bin/env python3
"""Fail fast when navigation or contract docs were likely forgotten."""

from __future__ import annotations

import argparse
import json
import sys

from navigation_catalog import collect_changed_paths, iter_triggered_drift_rules, repo_path


TRACKED_ARTIFACT_SUFFIXES = (".md", ".mdc", ".toml")
TRACKED_ARTIFACT_FILES = {"PLANS.md"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверка дрифта между кодом и docs/CODEMAP.")
    parser.add_argument("--base", help="Git base revision for docs drift check")
    parser.add_argument("--staged", action="store_true", help="Смотреть staged diff вместо worktree")
    parser.add_argument("--paths", nargs="*", help="Ограничить анализ указанными путями")
    parser.add_argument("--json", action="store_true", help="Печатать результат в JSON")
    return parser.parse_args()


def is_tracked_artifact(path: str) -> bool:
    normalized = repo_path(path)
    if normalized.endswith("/SKILL.md"):
        return True
    if normalized in TRACKED_ARTIFACT_FILES:
        return True
    return normalized.endswith(TRACKED_ARTIFACT_SUFFIXES)


def main() -> int:
    args = parse_args()
    try:
        changes = collect_changed_paths(base=args.base, staged=args.staged, pathspecs=args.paths)
    except RuntimeError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
            return 2
        print(f"docs_drift_check error: {exc}", file=sys.stderr)
        return 2

    if not changes:
        if args.json:
            print(json.dumps({"status": "ok", "message": "no changes found", "failures": []}, ensure_ascii=False, indent=2))
            return 0
        print("docs_drift_check: no changes found.")
        return 0

    changed_artifacts = {repo_path(change.path) for change in changes if is_tracked_artifact(change.path)}
    triggered = iter_triggered_drift_rules(changes)

    if not triggered:
        if args.json:
            print(
                json.dumps(
                    {"status": "ok", "message": "no documentation-sensitive changes detected", "failures": []},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print("docs_drift_check: no documentation-sensitive changes detected.")
        return 0

    failures: list[dict[str, object]] = []
    for rule, matched in triggered:
        if any(doc in changed_artifacts for doc in rule.required_docs):
            continue
        matched_paths = ", ".join(sorted(change.path for change in matched))
        required_docs = ", ".join(rule.required_docs)
        failures.append(
            {
                "rule": rule.key,
                "title": rule.title,
                "reason": rule.reason,
                "changed": sorted(change.path for change in matched),
                "required_artifacts": list(rule.required_docs),
                "message": (
                    f"{rule.title}: {rule.reason} "
                    f"Changed: {matched_paths}. Update at least one of: {required_docs}"
                ),
            }
        )

    if failures:
        if args.json:
            print(json.dumps({"status": "failed", "failures": failures}, ensure_ascii=False, indent=2))
            return 1
        print("docs_drift_check failed:")
        for item in failures:
            print(f" - {item['message']}")
        return 1

    if args.json:
        print(json.dumps({"status": "ok", "message": "ok", "failures": []}, ensure_ascii=False, indent=2))
        return 0
    print("docs_drift_check: ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
