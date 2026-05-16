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
from config import DATABASE_URL
from knowledge.content_pack_service import KnowledgeContentPackService, load_content_pack_file


PACK_DIR = REPO_ROOT / "content_packs" / "knowledge"


def _pack_paths(pack_code: str | None) -> list[Path]:
    if pack_code:
        candidates = [PACK_DIR / f"{pack_code}.yaml", PACK_DIR / f"{pack_code}.yml", PACK_DIR / f"{pack_code}.json"]
        return [path for path in candidates if path.exists()]
    return sorted([*PACK_DIR.glob("*.yaml"), *PACK_DIR.glob("*.yml"), *PACK_DIR.glob("*.json")])


async def _run(args: argparse.Namespace) -> int:
    await init_db(args.database_url or DATABASE_URL)
    try:
        paths = _pack_paths(args.pack)
        if not paths:
            print(json.dumps({"status": "error", "error": "pack_not_found", "pack": args.pack}, ensure_ascii=False))
            return 1
        results = []
        async with get_session() as session:
            service = KnowledgeContentPackService(session)
            for path in paths:
                result = await service.repair_pack_bindings(
                    load_content_pack_file(path),
                    actor_id=args.actor,
                    dry_run=args.dry_run,
                )
                results.append({"path": str(path), **result})
            if not args.dry_run:
                await session.commit()
        payload = {"status": "ok", "dry_run": args.dry_run, "results": results}
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
        return 0
    finally:
        await shutdown_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair installed Knowledge content-pack bindings without overwriting article content.")
    parser.add_argument("--pack", help="Pack code to repair.")
    parser.add_argument("--all", action="store_true", help="Repair all content packs. Default when --pack is omitted.")
    parser.add_argument("--dry-run", action="store_true", help="Report binding drift without mutation.")
    parser.add_argument("--json", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--actor", default="codex", help="Actor id stored in audit metadata.")
    parser.add_argument("--database-url", default=None, help="DATABASE_URL override. Defaults to env/server/.env.")
    args = parser.parse_args()
    if args.pack and args.all:
        parser.error("--pack and --all are mutually exclusive")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
