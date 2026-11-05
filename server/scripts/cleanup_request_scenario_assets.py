"""Bounded cleanup of expired, unsubmitted requester files (dry-run by default).

Requires explicit DATABASE_URL. Author material, ticket artifacts and live
sessions are always retained. No other upload-directory files are scanned.
"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.request_scenario_models import RequestStudioAsset, RequestStudioSession
from config import UPLOAD_DIR


async def cleanup(*, apply=False, limit=100, grace_hours=24):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("Explicit DATABASE_URL is required")
    engine = create_async_engine(database_url, hide_parameters=True)
    paths, count = [], 0
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=grace_hours)
            rows = (await session.scalars(select(RequestStudioAsset).join(
                RequestStudioSession, RequestStudioSession.id == RequestStudioAsset.session_id,
            ).where(RequestStudioAsset.artifact_id.is_(None), RequestStudioSession.linked_ticket_id.is_(None),
                    RequestStudioSession.expires_at < cutoff).order_by(RequestStudioAsset.id).limit(limit)
                .with_for_update(skip_locked=True))).all()
            root = UPLOAD_DIR.resolve()
            for row in rows:
                path = (root / row.storage_path).resolve()
                if path.parent != root or path.name != f"studio_{row.id}.bin":
                    raise ValueError("Unexpected Studio storage path; cleanup refused")
                count += 1
                if apply:
                    paths.append(path)
                    await session.delete(row)
            if apply:
                # An uncertain commit must retain blobs. File deletion begins
                # only after a confirmed ownership-row deletion transaction.
                await session.commit()
            else:
                await session.rollback()
        for path in paths:
            path.unlink(missing_ok=True)
        return {"mode": "apply" if apply else "dry-run", "eligible": count, "limit": limit,
                "retained": "all author material, ticket files and unexpired sessions"}
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--grace-hours", type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.limit <= 500 or not 24 <= args.grace_hours <= 8760:
        parser.error("limit must be 1..500 and grace-hours 24..8760")
    import json
    print(json.dumps(asyncio.run(cleanup(apply=args.apply, limit=args.limit, grace_hours=args.grace_hours))))


if __name__ == "__main__":
    main()
