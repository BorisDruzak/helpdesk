#!/usr/bin/env python3
"""Inventory project documentation and validate local markdown links."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_ROOTS = (Path("docs"), Path("server/docs"), Path("pc_agent/docs"))
EXTRA_DOCS = (Path("AGENTS.md"), Path("PLANS.md"))
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdc"}
ARCHIVE_PARTS = ("archive",)
PLAN_PARTS = ("superpowers", "plans")
SPEC_PARTS = ("superpowers", "specs")
HISTORICAL_NAME_MARKERS = (
    "analysis",
    "gap",
    "roadmap",
    "bottleneck",
    "risk",
    "progress",
    "handoff",
    "migration_plan",
)
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\((?P<target>[^)\n]+)\)")
IGNORED_SCHEMES = {"http", "https", "mailto", "tel", "data"}
ACTIVE_LINK_STATUSES = {"canonical", "plan", "spec"}
LEGACY_REPO_PREFIXES = (
    "/192.168.100.17/NTFS_Share/pc_client/",
    "//192.168.100.17/NTFS_Share/pc_client/",
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class DocRecord:
    path: Path
    status: str
    title: str | None
    line_count: int
    size_bytes: int


@dataclass(frozen=True)
class BrokenLink:
    source: Path
    line: int
    target: str
    resolved: Path


@dataclass(frozen=True)
class Inventory:
    docs: list[DocRecord]
    status_counts: Counter[str]
    broken_links: list[BrokenLink]
    duplicate_basenames: dict[str, list[Path]]


def repo_path(value: str | Path) -> Path:
    return Path(str(value).replace("\\", "/").strip("/"))


def collect_docs(workspace: Path = REPO_ROOT) -> list[Path]:
    docs: set[Path] = set()
    for root in DOC_ROOTS:
        absolute_root = workspace / root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in MARKDOWN_SUFFIXES:
                docs.add(path.relative_to(workspace))
    for path in EXTRA_DOCS:
        if (workspace / path).is_file():
            docs.add(path)
    return sorted(docs, key=lambda item: item.as_posix().lower())


def classify_doc(path: Path) -> str:
    normalized = repo_path(path)
    parts = tuple(part.lower() for part in normalized.parts)
    name = normalized.name.lower()
    stem = normalized.stem.lower()

    if any(part in ARCHIVE_PARTS for part in parts):
        return "archive"
    if _contains_ordered_parts(parts, PLAN_PARTS):
        return "plan"
    if _contains_ordered_parts(parts, SPEC_PARTS):
        return "spec"
    if normalized in {Path("AGENTS.md"), Path("PLANS.md")}:
        return "canonical" if normalized.name == "AGENTS.md" else "plan"
    if parts[:1] == ("docs",) and "plan" in stem:
        return "plan"
    if normalized.parts[:2] in (("server", "docs"), ("pc_agent", "docs")):
        return "canonical"
    if any(marker in stem for marker in HISTORICAL_NAME_MARKERS):
        return "historical"
    if name in {"readme.md", "quick_lookup.md", "local_workflow.md"}:
        return "canonical"
    return "canonical"


def _contains_ordered_parts(parts: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    if len(parts) < len(expected):
        return False
    return any(parts[index:index + len(expected)] == expected for index in range(len(parts) - len(expected) + 1))


def build_doc_record(workspace: Path, path: Path) -> DocRecord:
    absolute = workspace / path
    text = absolute.read_text(encoding="utf-8", errors="replace")
    title = next((line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")), None)
    return DocRecord(
        path=path,
        status=classify_doc(path),
        title=title or None,
        line_count=len(text.splitlines()),
        size_bytes=absolute.stat().st_size,
    )


def find_duplicate_basenames(docs: Iterable[Path]) -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = defaultdict(list)
    for path in docs:
        buckets[path.name.lower()].append(path)
    status_order = {"canonical": 0, "historical": 1, "plan": 2, "spec": 3, "archive": 4}
    return {
        name: sorted(paths, key=lambda item: (status_order.get(classify_doc(item), 9), item.as_posix().lower()))
        for name, paths in sorted(buckets.items())
        if len(paths) > 1
    }


def find_broken_links(workspace: Path = REPO_ROOT, docs: Iterable[Path] | None = None) -> list[BrokenLink]:
    broken: list[BrokenLink] = []
    for source in docs or collect_docs(workspace):
        absolute_source = workspace / source
        text = absolute_source.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                original_target = match.group("target").strip()
                local_target = normalize_local_link_target(original_target)
                if local_target is None:
                    continue
                resolved = resolve_link_target(workspace, source, local_target)
                if not resolved.exists():
                    broken.append(
                        BrokenLink(
                            source=source,
                            line=line_number,
                            target=original_target,
                            resolved=resolved.relative_to(workspace) if _is_relative_to(resolved, workspace) else resolved,
                        )
                    )
    return broken


def normalize_local_link_target(target: str) -> str | None:
    stripped = target.strip()
    if not stripped:
        return None
    if stripped.startswith("<") and ">" in stripped:
        stripped = stripped[1:stripped.index(">")]
    else:
        stripped = stripped.split()[0]

    parsed = urlparse(stripped)
    if parsed.scheme.lower() in IGNORED_SCHEMES:
        return None
    if stripped.startswith("#"):
        return None

    without_fragment = stripped.split("#", 1)[0]
    if not without_fragment:
        return None
    return unquote(without_fragment)


def resolve_link_target(workspace: Path, source: Path, target: str) -> Path:
    normalized_target = target.replace("\\", "/")
    for prefix in LEGACY_REPO_PREFIXES:
        if normalized_target.startswith(prefix):
            return (workspace / normalized_target[len(prefix):]).resolve()
    target_path = Path(target)
    if target.startswith("/"):
        return (workspace / target.lstrip("/")).resolve()
    return (workspace / source.parent / target_path).resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def build_inventory(workspace: Path = REPO_ROOT) -> Inventory:
    docs = collect_docs(workspace)
    records = [build_doc_record(workspace, path) for path in docs]
    return Inventory(
        docs=records,
        status_counts=Counter(record.status for record in records),
        broken_links=find_broken_links(workspace, docs),
        duplicate_basenames=find_duplicate_basenames(docs),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List project docs, statuses, broken links and duplicate doc names.")
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT)
    parser.add_argument("--status", choices=("canonical", "archive", "plan", "spec", "historical"), help="Show only docs with this status")
    parser.add_argument("--check-links", action="store_true", help="Exit non-zero when local markdown links are broken")
    parser.add_argument("--all-link-statuses", action="store_true", help="Check archive and historical docs too")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    return parser.parse_args()


def inventory_to_json(inventory: Inventory) -> dict[str, object]:
    return {
        "docs": [
            {
                "path": record.path.as_posix(),
                "status": record.status,
                "title": record.title,
                "line_count": record.line_count,
                "size_bytes": record.size_bytes,
            }
            for record in inventory.docs
        ],
        "status_counts": dict(inventory.status_counts),
        "broken_links": [
            {
                "source": item.source.as_posix(),
                "line": item.line,
                "target": item.target,
                "resolved": item.resolved.as_posix() if isinstance(item.resolved, Path) else str(item.resolved),
            }
            for item in inventory.broken_links
        ],
        "duplicate_basenames": {
            name: [path.as_posix() for path in paths]
            for name, paths in inventory.duplicate_basenames.items()
        },
    }


def print_human(inventory: Inventory, *, status_filter: str | None = None) -> None:
    print("Docs inventory")
    print("Statuses:")
    for status, count in sorted(inventory.status_counts.items()):
        print(f" - {status}: {count}")

    print("Docs:")
    for record in inventory.docs:
        if status_filter and record.status != status_filter:
            continue
        title = f" — {record.title}" if record.title else ""
        print(f" - [{record.status}] {record.path.as_posix()}{title}")

    if inventory.broken_links:
        print("Broken links:")
        for item in inventory.broken_links:
            print(f" - {item.source.as_posix()}:{item.line} -> {item.target} (resolved: {item.resolved})")
    else:
        print("Broken links: none")

    if inventory.duplicate_basenames:
        print("Duplicate basenames:")
        for name, paths in inventory.duplicate_basenames.items():
            joined = ", ".join(path.as_posix() for path in paths)
            print(f" - {name}: {joined}")
    else:
        print("Duplicate basenames: none")


def print_link_check(broken_links: list[BrokenLink]) -> None:
    if not broken_links:
        print("docs_inventory: all local markdown links are valid.")
        return
    print("docs_inventory: broken local markdown links:")
    for item in broken_links:
        print(f" - {item.source.as_posix()}:{item.line} -> {item.target} (resolved: {item.resolved})")


def main() -> int:
    args = parse_args()
    inventory = build_inventory(args.workspace)
    link_check_docs = collect_docs(args.workspace)
    if args.check_links and not args.all_link_statuses:
        link_check_docs = [path for path in link_check_docs if classify_doc(path) in ACTIVE_LINK_STATUSES]
    link_check_failures = find_broken_links(args.workspace, link_check_docs)
    if args.json:
        print(json.dumps(inventory_to_json(inventory), ensure_ascii=False, indent=2))
    elif args.check_links:
        print_link_check(link_check_failures)
    else:
        print_human(inventory, status_filter=args.status)
    if args.check_links and link_check_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
