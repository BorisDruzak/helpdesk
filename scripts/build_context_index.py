#!/usr/bin/env python3
"""Build the local pc_client context index."""

from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Build deterministic SQLite context index for pc_client.")
    parser.add_argument("--db-path", type=Path, default=context_index.DEFAULT_INDEX_PATH, help="SQLite index path")
    parser.add_argument("--workspace", type=Path, default=context_index.REPO_ROOT, help="Repository root")
    parser.add_argument("--force", action="store_true", help="Rebuild the index even if it exists")
    parser.add_argument("--json", action="store_true", help="Print JSON stats")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stats = context_index.build_index(workspace=args.workspace, db_path=args.db_path, force=args.force)
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(f"Context index built: {args.db_path}")
        for key in ("items", "docs", "chunks", "topics", "routes", "symbols", "tests", "fts_enabled"):
            print(f"- {key}: {stats.get(key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
