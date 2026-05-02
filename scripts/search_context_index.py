#!/usr/bin/env python3
"""Search the local pc_client context index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import context_index
except ModuleNotFoundError:  # pragma: no cover - package import for pytest
    from scripts import context_index


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search deterministic SQLite context index for pc_client.")
    parser.add_argument("query", help="Search query, for example: run_tool command_result observer")
    parser.add_argument("--db-path", type=Path, default=context_index.DEFAULT_INDEX_PATH, help="SQLite index path")
    parser.add_argument("--workspace", type=Path, default=context_index.REPO_ROOT, help="Repository root")
    parser.add_argument("--limit", type=int, default=12, help="Maximum result count")
    parser.add_argument("--kind", choices=("doc", "topic", "route", "symbol", "test"), help="Filter by result kind")
    parser.add_argument("--profile", choices=context_index.SEARCH_PROFILES, default="default", help="Ranking profile")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--no-build", action="store_true", help="Fail if the index is missing instead of building it")
    parser.add_argument("--no-freshness-warning", action="store_true", help="Do not warn when indexed sources changed")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db_path.exists():
        if args.no_build:
            print(f"Context index not found: {args.db_path}", file=sys.stderr)
            return 2
        context_index.build_index(workspace=args.workspace, db_path=args.db_path, force=True)
    elif not args.no_freshness_warning:
        warning = context_index.format_freshness_warning(
            context_index.freshness_status(workspace=args.workspace, db_path=args.db_path)
        )
        if warning:
            print(warning, file=sys.stderr)
    results = context_index.search_index(
        db_path=args.db_path,
        query=args.query,
        limit=args.limit,
        kind=args.kind,
        profile=args.profile,
    )
    print(context_index.render_search_results(results, json_output=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
