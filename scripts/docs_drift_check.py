#!/usr/bin/env python3
"""Fail fast when navigation or contract docs were likely forgotten."""

from __future__ import annotations

import argparse
import sys

from navigation_catalog import collect_changed_paths, iter_triggered_drift_rules, repo_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверка дрифта между кодом и docs/CODEMAP.")
    parser.add_argument("--base", help="Git base revision for docs drift check")
    parser.add_argument("--staged", action="store_true", help="Смотреть staged diff вместо worktree")
    parser.add_argument("--paths", nargs="*", help="Ограничить анализ указанными путями")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changes = collect_changed_paths(base=args.base, staged=args.staged, pathspecs=args.paths)
    except RuntimeError as exc:
        print(f"docs_drift_check error: {exc}", file=sys.stderr)
        return 2

    if not changes:
        print("docs_drift_check: no changes found.")
        return 0

    changed_docs = {repo_path(change.path) for change in changes if change.path.endswith(".md")}
    triggered = iter_triggered_drift_rules(changes)

    if not triggered:
        print("docs_drift_check: no documentation-sensitive changes detected.")
        return 0

    failures: list[str] = []
    for rule, matched in triggered:
        if any(doc in changed_docs for doc in rule.required_docs):
            continue
        matched_paths = ", ".join(sorted(change.path for change in matched))
        required_docs = ", ".join(rule.required_docs)
        failures.append(
            f"{rule.title}: {rule.reason} "
            f"Changed: {matched_paths}. Update at least one of: {required_docs}"
        )

    if failures:
        print("docs_drift_check failed:")
        for item in failures:
            print(f" - {item}")
        return 1

    print("docs_drift_check: ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
