#!/usr/bin/env python3
"""Summarize the current diff into navigation, docs and test hints."""

from __future__ import annotations

import argparse
import json
import sys

from navigation_catalog import (
    QUICK_LOOKUP_PATH,
    collect_changed_paths,
    collect_first_files,
    collect_related_docs,
    find_topics_for_paths,
    recommend_checks,
    repo_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Операционный контекст по текущему diff.")
    parser.add_argument("--base", help="Git base revision for diff_context (например origin/main)")
    parser.add_argument("--staged", action="store_true", help="Смотреть staged diff вместо worktree")
    parser.add_argument("--json", action="store_true", help="Печатать результат в JSON")
    parser.add_argument("--paths", nargs="*", help="Ограничить анализ указанными путями")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changes = collect_changed_paths(base=args.base, staged=args.staged, pathspecs=args.paths)
    except RuntimeError as exc:
        print(f"diff_context error: {exc}", file=sys.stderr)
        return 2

    if not changes:
        print("Изменений не найдено.")
        return 0

    paths = [change.path for change in changes]
    topics = find_topics_for_paths(paths)
    docs = collect_related_docs(topics)
    first_files = collect_first_files(topics)
    checks = recommend_checks(paths)

    if args.json:
        payload = {
            "changed_files": [{"status": change.status, "path": change.path, "old_path": change.old_path} for change in changes],
            "topics": [
                {
                    "key": topic.key,
                    "title": topic.title,
                    "summary": topic.summary,
                    "first_files": list(topic.first_files),
                    "related_docs": list(topic.related_docs),
                }
                for topic in topics
            ],
            "docs": docs,
            "first_files": first_files,
            "checks": checks,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Changed files:")
    for change in changes:
        if change.old_path:
            print(f" - {change.status} {change.old_path} -> {change.path}")
        else:
            print(f" - {change.status} {change.path}")

    print("\nLikely topics:")
    if topics:
        for topic in topics:
            print(f" - {topic.title}: {topic.summary}")
    else:
        print(" - No curated topic matched. Start from CODEMAP and a targeted agent_find query.")

    print("\nOpen first:")
    if first_files:
        for path in first_files[:8]:
            print(f" - {path}")
    else:
        print(" - server/docs/CODEMAP.md")
        print(" - pc_agent/docs/CODEMAP.md")
        print(f" - {repo_path(QUICK_LOOKUP_PATH)}")

    print("\nDocs to inspect or update:")
    if docs:
        for path in docs:
            print(f" - {path}")
    else:
        print(f" - {repo_path(QUICK_LOOKUP_PATH)}")

    print("\nSuggested checks:")
    for check in checks:
        print(f" - {check}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
