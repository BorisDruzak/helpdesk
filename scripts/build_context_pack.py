#!/usr/bin/env python3
"""Build a compact Codex context pack from navigation_catalog metadata."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable, Sequence

try:
    import navigation_catalog as nav
    import task_intake
except ModuleNotFoundError:  # pragma: no cover - package import for pytest
    from scripts import navigation_catalog as nav
    from scripts import task_intake


DEFAULT_MAX_ITEMS = 12

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact Codex context pack for a pc_client topic.")
    parser.add_argument("--topic", required=True, help="Task or topic text, for example: обновление агента")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, help="Maximum items per section")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    return parser.parse_args()


def dedupe(values: Iterable[str], *, limit: int = DEFAULT_MAX_ITEMS) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
        if len(ordered) >= limit:
            break
    return ordered


def topics_for_keys(keys: Sequence[str]) -> list[nav.Topic]:
    by_key = {topic.key: topic for topic in nav.TOPICS}
    return [by_key[key] for key in keys if key in by_key]


def build_context_pack(topic: str, *, max_items: int = DEFAULT_MAX_ITEMS) -> dict[str, object]:
    payload = task_intake.build_intake(task=topic)
    topics = topics_for_keys(payload["matched_topics"])
    suggested_commands = dedupe(
        command
        for matched_topic in topics
        for command in matched_topic.suggested_commands
    )
    summaries = dedupe(
        f"{matched_topic.title}: {matched_topic.summary}"
        for matched_topic in topics
    )

    return {
        "topic": topic,
        "recommended_mode": payload["recommended_mode"],
        "recommended_playbook": payload["recommended_playbook"],
        "matched_topics": payload["matched_topics"],
        "topic_summaries": summaries,
        "open_first": dedupe(payload["open_first"], limit=max_items),
        "docs_to_read": dedupe(payload["docs_to_read"], limit=max_items),
        "skills": dedupe(payload["skills"], limit=max_items),
        "checks_to_run": dedupe(payload["checks_to_run"], limit=max_items),
        "suggested_commands": suggested_commands[:max_items],
        "docs_to_update_if_code_changes": dedupe(payload["docs_to_update_if_code_changes"], limit=max_items),
        "plan_required": payload["plan_required"],
        "warnings": payload["warnings"],
    }


def render_list(title: str, values: Sequence[str]) -> list[str]:
    if not values:
        return []
    return [f"## {title}", *(f"- {value}" for value in values)]


def render_context_pack(pack: dict[str, object]) -> str:
    lines: list[str] = [
        f"# Context Pack: {pack['topic']}",
        f"Recommended mode: {pack['recommended_mode']}",
    ]
    if pack["recommended_playbook"]:
        lines.append(f"Playbook: {pack['recommended_playbook']}")
    lines.append(f"Plan required: {'yes' if pack['plan_required'] else 'no'}")
    if pack["matched_topics"]:
        lines.append(f"Matched topics: {', '.join(pack['matched_topics'])}")

    sections = [
        ("Topic Summary", pack["topic_summaries"]),
        ("Open First", pack["open_first"]),
        ("Read Next", pack["docs_to_read"]),
        ("Skills", pack["skills"]),
        ("Checks", pack["checks_to_run"]),
        ("Search And Commands", pack["suggested_commands"]),
        ("Docs To Update If Code Changes", pack["docs_to_update_if_code_changes"]),
        ("Warnings", pack["warnings"]),
    ]
    for title, values in sections:
        rendered = render_list(title, values)
        if rendered:
            lines.append("")
            lines.extend(rendered)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    pack = build_context_pack(args.topic, max_items=args.max_items)
    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        print(render_context_pack(pack))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
