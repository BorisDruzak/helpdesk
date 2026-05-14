from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import RequestTemplate, TicketQueue
from app.repos.service_catalog_repo import ServiceCatalogRepo
from config import DATABASE_URL
from tickets.service_catalog_defaults import (
    DEFAULT_SERVICE_CATALOG_OFFERINGS,
    DEFAULT_SERVICE_CATALOG_SERVICES,
)


def _summary(*, dry_run: bool) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "created": {"services": [], "offerings": [], "request_templates": []},
        "updated": {"services": [], "offerings": [], "request_templates": []},
        "skipped": {"services": [], "offerings": [], "request_templates": []},
        "would_create": {"services": [], "offerings": [], "request_templates": []},
        "missing_dependencies": [],
    }


def _offline_dry_run_summary(error: Exception) -> dict[str, Any]:
    summary = _summary(dry_run=True)
    summary["would_create"]["services"] = [str(item.get("code")) for item in DEFAULT_SERVICE_CATALOG_SERVICES]
    summary["would_create"]["offerings"] = [
        str(item.get("full_code") or f"{item.get('service_code')}.{item.get('code')}")
        for item in DEFAULT_SERVICE_CATALOG_OFFERINGS
    ]
    summary["would_create"]["request_templates"] = list(
        dict.fromkeys(
            str(item.get("request_template_key"))
            for item in DEFAULT_SERVICE_CATALOG_OFFERINGS
            if item.get("request_template_key")
        )
    )
    summary["missing_dependencies"].append(
        {
            "kind": "database_unavailable",
            "message": str(error),
            "effect": "offline dry-run cannot check existing rows, queues or idempotency state",
        }
    )
    return summary


async def _default_queue_id(session: Any) -> int | None:
    row = (
        await session.execute(
            select(TicketQueue).where(TicketQueue.is_active.is_(True)).order_by(TicketQueue.id.asc()).limit(1)
        )
    ).scalar_one_or_none()
    return int(row.id) if row is not None else None


async def _request_template_exists(session: Any, template_code: str) -> bool:
    row = (
        await session.execute(
            select(RequestTemplate).where(
                RequestTemplate.template_code == template_code,
                RequestTemplate.is_active.is_(True),
            )
        )
    ).first()
    return row is not None


async def _ensure_request_template(
    session: Any,
    *,
    template_code: str,
    public_title: str,
    ticket_type: str,
    default_queue_id: int | None,
    dry_run: bool,
    force: bool,
    summary: dict[str, Any],
) -> None:
    exists = await _request_template_exists(session, template_code)
    if exists and not force:
        summary["skipped"]["request_templates"].append(template_code)
        return
    if dry_run:
        summary["would_create" if not exists else "updated"]["request_templates"].append(template_code)
        return
    if exists and force:
        # Keep existing versions intact. Seed never rewrites admin-managed template rows.
        summary["skipped"]["request_templates"].append(template_code)
        return
    session.add(
        RequestTemplate(
            template_code=template_code,
            version="seed-1",
            public_title=public_title,
            ticket_type=ticket_type or "service_request",
            config_json={
                "default_queue_id": default_queue_id,
                "no_sla": True,
                "seeded_by": "scripts/seed_service_catalog.py",
            },
            is_active=True,
            published_at=datetime.now(timezone.utc),
            created_by="seed_service_catalog",
        )
    )
    summary["created"]["request_templates"].append(template_code)


async def seed_service_catalog(session: Any, *, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    repo = ServiceCatalogRepo(session)
    summary = _summary(dry_run=dry_run)
    queue_id = await _default_queue_id(session)
    if queue_id is None:
        summary["missing_dependencies"].append("active_ticket_queue")

    existing_services = {service["code"]: service for service in await repo.list_services(include_retired=True)}
    for service in DEFAULT_SERVICE_CATALOG_SERVICES:
        code = service["code"]
        if code in existing_services and not force:
            summary["skipped"]["services"].append(code)
            continue
        payload = deepcopy(service)
        if queue_id is not None:
            payload.setdefault("owner_queue_id", queue_id)
            payload.setdefault("default_queue_id", queue_id)
            payload["lifecycle_status"] = "published"
        else:
            payload["lifecycle_status"] = "draft"
            payload["metadata"] = {"seed_missing_dependencies": ["active_ticket_queue"]}
        if dry_run:
            summary["would_create" if code not in existing_services else "updated"]["services"].append(code)
            continue
        await repo.upsert_service_draft(payload, actor_id="seed_service_catalog", actor_role="admin")
        if payload["lifecycle_status"] == "published":
            await repo.publish_service(code, actor_id="seed_service_catalog", actor_role="admin")
        summary["created" if code not in existing_services else "updated"]["services"].append(code)

    existing_offerings = {offering["full_code"]: offering for offering in await repo.list_offerings()}
    for offering in DEFAULT_SERVICE_CATALOG_OFFERINGS:
        full_code = f"{offering['service_code']}.{offering['code']}"
        template_key = str(offering.get("request_template_key") or "").strip()
        await _ensure_request_template(
            session,
            template_code=template_key,
            public_title=str(offering.get("public_title") or template_key),
            ticket_type=str(offering.get("request_type") or "service_request"),
            default_queue_id=queue_id,
            dry_run=dry_run,
            force=force,
            summary=summary,
        )
        if full_code in existing_offerings and not force:
            summary["skipped"]["offerings"].append(full_code)
            continue
        payload = deepcopy(offering)
        if queue_id is not None:
            payload.setdefault("default_queue_id", queue_id)
            payload["lifecycle_status"] = "published"
        else:
            payload["lifecycle_status"] = "draft"
            payload["metadata"] = {"seed_missing_dependencies": ["active_ticket_queue"]}
        if dry_run:
            summary["would_create" if full_code not in existing_offerings else "updated"]["offerings"].append(full_code)
            continue
        saved = await repo.upsert_offering_draft(payload, actor_id="seed_service_catalog", actor_role="admin")
        if payload["lifecycle_status"] == "published":
            await repo.publish_offering(saved["full_code"], actor_id="seed_service_catalog", actor_role="admin")
        summary["created" if full_code not in existing_offerings else "updated"]["offerings"].append(full_code)

    return summary


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Seed baseline Service Catalog services and offerings.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing DB rows.")
    parser.add_argument("--force", action="store_true", help="Update existing seed-managed catalog rows.")
    args = parser.parse_args()
    try:
        await init_db(DATABASE_URL)
    except Exception as exc:
        if args.dry_run:
            print(json.dumps(_offline_dry_run_summary(exc), ensure_ascii=False, indent=2, default=str))
            return 0
        raise
    try:
        async with get_session() as session:
            summary = await seed_service_catalog(session, dry_run=args.dry_run, force=args.force)
            if not args.dry_run:
                await session.commit()
    finally:
        await shutdown_db()
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
