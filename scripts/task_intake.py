#!/usr/bin/env python3
"""Canonical intake router for non-trivial pc_client tasks."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

try:
    import navigation_catalog as nav
except ModuleNotFoundError:  # pragma: no cover - package import for pytest
    from scripts import navigation_catalog as nav


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical task intake for pc_client.")
    parser.add_argument("--task", help="Task text to classify and route")
    parser.add_argument("--paths", nargs="*", help="Explicit repo-relative paths to analyze")
    parser.add_argument("--base", help="Git base revision for diff-based intake")
    parser.add_argument("--staged", action="store_true", help="Use staged diff instead of worktree")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    return parser.parse_args()


def _dedupe_topics(*groups: Sequence[nav.Topic]) -> list[nav.Topic]:
    ordered: list[nav.Topic] = []
    seen: set[str] = set()
    for group in groups:
        for topic in group:
            if topic.key in seen:
                continue
            seen.add(topic.key)
            ordered.append(topic)
    return ordered


def _collect_input_paths(
    *,
    task: str | None,
    base: str | None,
    staged: bool,
    explicit_paths: Sequence[str] | None,
) -> list[str]:
    if explicit_paths:
        return [nav.repo_path(path) for path in explicit_paths]
    if task:
        return []
    changes = nav.collect_changed_paths(base=base, staged=staged)
    return [change.path for change in changes]


def _build_warnings(
    *,
    task: str | None,
    topics: Sequence[nav.Topic],
    paths: Sequence[str],
    playbook: str | None,
    plan_required: bool,
) -> list[str]:
    warnings: list[str] = []
    if not topics:
        warnings.append(
            "No curated topic matched; start from docs/QUICK_LOOKUP.md and a targeted python scripts/agent_find.py query."
        )
        return warnings

    normalized_paths = [nav.repo_path(path) for path in paths]
    code_roots = {
        "server" if path.startswith("server/") else "pc_agent"
        for path in normalized_paths
        if path.startswith("server/") or path.startswith("pc_agent/")
    }
    if len(code_roots) > 1:
        warnings.append("Task touches both server and pc_agent; keep docs/CODEMAP and verification aligned across both sides.")

    if len(topics) > 1:
        warnings.append(
            "Multiple curated topics matched; verify the primary intent before editing and keep the first mode as the working default."
        )

    if task and not playbook and len(topics) == 1 and topics[0].key not in {"planning", "run_tool", "auth", "tickets", "modules"}:
        warnings.append("No dedicated playbook is attached to this topic; rely on the listed docs, skills and checks.")

    if plan_required:
        warnings.append("Update PLANS.md before or during the work if the task spans multiple stages or verification loops.")

    return warnings


def build_intake(
    *,
    task: str | None = None,
    paths: Sequence[str] | None = None,
    base: str | None = None,
    staged: bool = False,
) -> dict[str, object]:
    normalized_task = " ".join((task or "").split())
    input_paths = _collect_input_paths(task=normalized_task or None, base=base, staged=staged, explicit_paths=paths)
    topics_from_query = nav.find_topics_for_query(normalized_task) if normalized_task else []
    topics_from_paths = nav.find_topics_for_paths(input_paths) if input_paths else []
    topics = _dedupe_topics(topics_from_query, topics_from_paths)

    recommended_mode = nav.select_mode(topics)
    recommended_playbook = nav.select_playbook(topics)
    open_first = nav.collect_first_files(topics)
    docs_to_read = nav.collect_related_docs(topics)
    checks_to_run = nav.collect_checks(topics, paths=input_paths)
    docs_to_update = nav.collect_docs_to_update(topics, paths=input_paths)
    skills = nav.collect_skills(topics)
    plan_required = nav.is_plan_required(topics, paths=input_paths)
    warnings = _build_warnings(
        task=normalized_task or None,
        topics=topics,
        paths=input_paths,
        playbook=recommended_playbook,
        plan_required=plan_required,
    )

    if not topics:
        open_first = [
            nav.repo_path(nav.QUICK_LOOKUP_PATH),
            nav.repo_path(nav.SERVER_CODEMAP_PATH),
            nav.repo_path(nav.AGENT_CODEMAP_PATH),
        ]
        docs_to_read = open_first.copy()
        checks_to_run = ["python scripts/verify_workspace.py"]
        docs_to_update = ["AGENTS.md", nav.repo_path(nav.QUICK_LOOKUP_PATH)]

    return {
        "recommended_mode": recommended_mode,
        "recommended_playbook": recommended_playbook,
        "open_first": open_first,
        "docs_to_read": docs_to_read,
        "checks_to_run": checks_to_run,
        "plan_required": plan_required,
        "docs_to_update_if_code_changes": docs_to_update,
        "skills": skills,
        "warnings": warnings,
        "matched_topics": [topic.key for topic in topics],
        "input_paths": input_paths,
        "task": normalized_task,
    }


def _is_simple(payload: dict[str, object]) -> bool:
    return (
        not payload["plan_required"]
        and len(payload["warnings"]) <= 1
        and len(payload["matched_topics"]) <= 1
        and len(payload["checks_to_run"]) <= 2
    )


def _print_section(title: str, values: Sequence[str]) -> None:
    if not values:
        return
    print(f"{title}:")
    for value in values:
        print(f" - {value}")


def print_human(payload: dict[str, object]) -> None:
    print(f"Recommended mode: {payload['recommended_mode']}")
    if payload["recommended_playbook"]:
        print(f"Playbook: {payload['recommended_playbook']}")

    if payload["input_paths"]:
        _print_section("Changed or target paths", payload["input_paths"])

    _print_section("Open first", payload["open_first"])

    if not _is_simple(payload):
        _print_section("Docs to read", payload["docs_to_read"])
        _print_section("Skills", payload["skills"])

    _print_section("Checks to run", payload["checks_to_run"])

    if not _is_simple(payload):
        _print_section("Docs to update if code changes", payload["docs_to_update_if_code_changes"])

    if payload["plan_required"]:
        print("Plan required: yes")
    else:
        print("Plan required: no")

    _print_section("Warnings", payload["warnings"])


def main() -> int:
    args = parse_args()
    try:
        payload = build_intake(
            task=args.task,
            paths=args.paths,
            base=args.base,
            staged=args.staged,
        )
    except RuntimeError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
            return 2
        print(f"task_intake error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
