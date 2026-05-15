from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from knowledge.content_pack_service import KnowledgeContentPackService, load_content_pack_file


PACK_DIR = REPO_ROOT / "content_packs" / "knowledge"


def _pack_paths(pack_code: str | None) -> list[Path]:
    if pack_code:
        candidates = [PACK_DIR / f"{pack_code}.yaml", PACK_DIR / f"{pack_code}.yml", PACK_DIR / f"{pack_code}.json"]
        return [path for path in candidates if path.exists()]
    return sorted([*PACK_DIR.glob("*.yaml"), *PACK_DIR.glob("*.yml"), *PACK_DIR.glob("*.json")])


async def _run(args: argparse.Namespace) -> int:
    await init_db()
    try:
        paths = _pack_paths(args.pack)
        if not paths:
            print(json.dumps({"status": "error", "error": "pack_not_found", "pack": args.pack}, ensure_ascii=False))
            return 1
        results = []
        async with get_session() as session:
            service = KnowledgeContentPackService(session)
            for path in paths:
                pack = load_content_pack_file(path)
                result = await service.apply_pack(
                    pack,
                    actor_id=args.actor,
                    dry_run=args.dry_run,
                    force=args.force,
                    retire_missing=args.retire_missing,
                    publish=args.publish,
                )
                results.append({"path": str(path), **result})
            if not args.dry_run:
                await session.commit()
        print(json.dumps({"status": "ok", "dry_run": args.dry_run, "results": results}, ensure_ascii=False, indent=2))
        return 0
    finally:
        await shutdown_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Install idempotent Knowledge Platform content packs.")
    parser.add_argument("--pack", help="Pack code to install.")
    parser.add_argument("--all", action="store_true", help="Install all content_packs/knowledge/*.yaml|*.yml|*.json packs. This is the default when --pack is omitted.")
    parser.add_argument("--dry-run", action="store_true", help="Report actions without writing pack state or content.")
    parser.add_argument("--force", action="store_true", help="Overwrite changed pack-managed items by creating a new version.")
    parser.add_argument("--retire-missing", action="store_true", help="Archive pack-managed items missing from the selected pack file.")
    parser.add_argument("--publish", action="store_true", help="Allow publishing internal pack entries that are explicitly marked published.")
    parser.add_argument("--actor", default="codex", help="Actor id stored in audit fields.")
    args = parser.parse_args()
    if args.pack and args.all:
        parser.error("--pack and --all are mutually exclusive")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
