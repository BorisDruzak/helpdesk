from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import KnowledgePropertyDefinition, KnowledgeQualityModel, KnowledgeSpace, KnowledgeTaxonomyTerm
from config import DATABASE_URL
from knowledge.metadata_service import KnowledgeMetadataService


DEFAULT_METADATA_PACK_PATH = REPO_ROOT / "content_packs" / "knowledge" / "default_metadata.json"
REQUESTER_VISIBLE = {"public", "requester", "agent_requester_safe"}
RESTRICTED_CLASSIFICATIONS = {"admin_internal", "security_restricted"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _summary() -> dict[str, int]:
    return {
        "create_spaces": 0,
        "update_spaces": 0,
        "skip_spaces": 0,
        "create_taxonomy_terms": 0,
        "update_taxonomy_terms": 0,
        "skip_taxonomy_terms": 0,
        "create_property_definitions": 0,
        "update_property_definitions": 0,
        "skip_property_definitions": 0,
        "create_quality_models": 0,
        "update_quality_models": 0,
        "skip_quality_models": 0,
    }


def _list(value: Any) -> list[dict[str, Any]]:
    return deepcopy(value) if isinstance(value, list) else []


def _metadata(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _validate_seed_safety(pack: dict[str, Any]) -> None:
    for term in _list(pack.get("taxonomy_terms")):
        metadata = _metadata(term.get("metadata"))
        classification = str(metadata.get("classification") or metadata.get("visibility_class") or "").strip()
        visibility = str(term.get("visibility") or "support_internal")
        if classification in RESTRICTED_CLASSIFICATIONS and visibility in REQUESTER_VISIBLE:
            raise ValueError("restricted seed term cannot be requester-visible")


def load_metadata_seed_pack(path: str | Path | None = None, *, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if data is None:
        target = Path(path or DEFAULT_METADATA_PACK_PATH)
        with target.open("r", encoding="utf-8") as handle:
            pack = json.load(handle)
    else:
        pack = deepcopy(data)
    if not isinstance(pack, dict):
        raise ValueError("metadata seed pack must be an object")
    for key in ("code", "version", "spaces", "taxonomy_terms"):
        if key not in pack:
            raise ValueError(f"metadata seed pack missing {key}")
    _validate_seed_safety(pack)
    return pack


async def _space_by_code(session: AsyncSession, code: str) -> KnowledgeSpace | None:
    return (await session.execute(select(KnowledgeSpace).where(KnowledgeSpace.code == code))).scalar_one_or_none()


async def _term_by_code(session: AsyncSession, space_id: str, code: str, term_type: str | None = None) -> KnowledgeTaxonomyTerm | None:
    stmt = select(KnowledgeTaxonomyTerm).where(KnowledgeTaxonomyTerm.space_id == space_id, KnowledgeTaxonomyTerm.code == code)
    if term_type:
        stmt = stmt.where(KnowledgeTaxonomyTerm.term_type == term_type)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _property_by_code(session: AsyncSession, space_id: str, code: str) -> KnowledgePropertyDefinition | None:
    return (
        await session.execute(
            select(KnowledgePropertyDefinition).where(KnowledgePropertyDefinition.space_id == space_id, KnowledgePropertyDefinition.code == code)
        )
    ).scalar_one_or_none()


async def _quality_model_by_code(session: AsyncSession, space_id: str | None, code: str) -> KnowledgeQualityModel | None:
    stmt = select(KnowledgeQualityModel).where(KnowledgeQualityModel.code == code)
    stmt = stmt.where(KnowledgeQualityModel.space_id.is_(None) if space_id is None else KnowledgeQualityModel.space_id == space_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _ensure_spaces(
    session: AsyncSession,
    pack: dict[str, Any],
    *,
    actor_id: str,
    dry_run: bool,
    force: bool,
    result: dict[str, Any],
) -> dict[str, KnowledgeSpace]:
    now = datetime.now(timezone.utc)
    spaces_by_code: dict[str, KnowledgeSpace] = {}
    for raw in _list(pack.get("spaces")):
        code = str(raw.get("code") or "").strip()
        if not code:
            raise ValueError("metadata seed space code is required")
        existing = await _space_by_code(session, code)
        if existing is None:
            result["summary"]["create_spaces"] += 1
            result["operations"].append({"action": "create", "type": "space", "code": code, "title": raw.get("title")})
            if dry_run:
                existing = KnowledgeSpace(
                    space_id=f"dry-run-{code}",
                    code=code,
                    title=str(raw.get("title") or code),
                    visibility=str(raw.get("visibility") or "requester"),
                    lifecycle_status=str(raw.get("lifecycle_status") or "active"),
                )
            else:
                existing = KnowledgeSpace(
                    space_id=_new_id(),
                    code=code,
                    title=str(raw.get("title") or code),
                    description=raw.get("description"),
                    visibility=str(raw.get("visibility") or "requester"),
                    lifecycle_status=str(raw.get("lifecycle_status") or "active"),
                    metadata_json=_metadata(raw.get("metadata")),
                    created_at=now,
                    updated_at=now,
                    created_by=actor_id,
                    updated_by=actor_id,
                )
                session.add(existing)
                await session.flush()
        elif force:
            result["summary"]["update_spaces"] += 1
            result["operations"].append({"action": "update", "type": "space", "code": code, "title": raw.get("title")})
            if not dry_run:
                existing.title = str(raw.get("title") or existing.title)
                existing.description = raw.get("description")
                existing.visibility = str(raw.get("visibility") or existing.visibility)
                existing.lifecycle_status = str(raw.get("lifecycle_status") or existing.lifecycle_status)
                existing.metadata_json = _metadata(raw.get("metadata"))
                existing.updated_at = now
                existing.updated_by = actor_id
        else:
            result["summary"]["skip_spaces"] += 1
            result["operations"].append({"action": "skip", "type": "space", "code": code, "reason": "exists"})
        if existing is not None:
            spaces_by_code[code] = existing
    return spaces_by_code


async def apply_metadata_seed_pack(
    session: AsyncSession,
    pack: dict[str, Any],
    *,
    actor_id: str = "codex",
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    pack = load_metadata_seed_pack(data=pack)
    result: dict[str, Any] = {"status": "ok", "dry_run": dry_run, "force": force, "summary": _summary(), "operations": []}
    spaces_by_code = await _ensure_spaces(session, pack, actor_id=actor_id, dry_run=dry_run, force=force, result=result)
    service = KnowledgeMetadataService(session)

    for raw in _list(pack.get("taxonomy_terms")):
        space_code = str(raw.get("space_code") or "").strip()
        space = spaces_by_code.get(space_code) or await _space_by_code(session, space_code)
        if space is None:
            raise ValueError(f"metadata seed taxonomy space not found: {space_code}")
        code = str(raw.get("code") or "").strip()
        term_type = str(raw.get("term_type") or "tag")
        existing = await _term_by_code(session, space.space_id, code, term_type)
        if existing is not None and not force:
            result["summary"]["skip_taxonomy_terms"] += 1
            result["operations"].append({"action": "skip", "type": "taxonomy_term", "code": code, "reason": "exists"})
            continue
        parent_term_id = None
        parent_code = str(raw.get("parent_code") or "").strip()
        if parent_code:
            parent = await _term_by_code(session, space.space_id, parent_code)
            if parent is None and not dry_run:
                raise ValueError(f"metadata seed parent taxonomy term not found: {parent_code}")
            parent_term_id = parent.term_id if parent is not None else None
        result["summary"]["update_taxonomy_terms" if existing is not None else "create_taxonomy_terms"] += 1
        result["operations"].append({"action": "update" if existing is not None else "create", "type": "taxonomy_term", "code": code, "title": raw.get("title")})
        if not dry_run:
            await service.upsert_taxonomy_term(
                {
                    "space_id": space.space_id,
                    "term_type": term_type,
                    "code": code,
                    "title": raw.get("title"),
                    "description": raw.get("description"),
                    "parent_term_id": parent_term_id,
                    "visibility": raw.get("visibility") or "requester",
                    "status": raw.get("status") or "active",
                    "sort_order": raw.get("sort_order") or 0,
                    "metadata": raw.get("metadata") or {},
                },
                actor_id=actor_id,
                actor_role="admin",
            )
            await session.flush()

    for raw in _list(pack.get("property_definitions")):
        space_code = str(raw.get("space_code") or "").strip()
        space = spaces_by_code.get(space_code) or await _space_by_code(session, space_code)
        if space is None:
            raise ValueError(f"metadata seed property space not found: {space_code}")
        code = str(raw.get("code") or "").strip()
        existing = await _property_by_code(session, space.space_id, code)
        if existing is not None and not force:
            result["summary"]["skip_property_definitions"] += 1
            result["operations"].append({"action": "skip", "type": "property_definition", "code": code, "reason": "exists"})
            continue
        result["summary"]["update_property_definitions" if existing is not None else "create_property_definitions"] += 1
        result["operations"].append({"action": "update" if existing is not None else "create", "type": "property_definition", "code": code, "title": raw.get("title")})
        if not dry_run:
            await service.upsert_property_definition(
                {
                    "space_id": space.space_id,
                    "code": code,
                    "title": raw.get("title"),
                    "description": raw.get("description"),
                    "value_type": raw.get("value_type") or "text",
                    "required": bool(raw.get("required")),
                    "allowed_values": raw.get("allowed_values") or [],
                    "applies_to_item_types": raw.get("applies_to_item_types") or [],
                    "quality_weight": raw.get("quality_weight") or 0,
                    "status": raw.get("status") or "active",
                    "metadata": raw.get("metadata") or {},
                },
                actor_id=actor_id,
                actor_role="admin",
            )

    for raw in _list(pack.get("quality_models")):
        space_code = str(raw.get("space_code") or "").strip()
        space = spaces_by_code.get(space_code) or await _space_by_code(session, space_code)
        if space_code and space is None:
            raise ValueError(f"metadata seed quality model space not found: {space_code}")
        space_id = space.space_id if space is not None else None
        code = str(raw.get("code") or "").strip()
        existing = await _quality_model_by_code(session, space_id, code)
        if existing is not None and not force:
            result["summary"]["skip_quality_models"] += 1
            result["operations"].append({"action": "skip", "type": "quality_model", "code": code, "reason": "exists"})
            continue
        result["summary"]["update_quality_models" if existing is not None else "create_quality_models"] += 1
        result["operations"].append({"action": "update" if existing is not None else "create", "type": "quality_model", "code": code, "title": raw.get("title")})
        if not dry_run:
            await service.upsert_quality_model(
                {
                    "space_id": space_id,
                    "code": code,
                    "title": raw.get("title"),
                    "is_default": bool(raw.get("is_default")),
                    "status": raw.get("status") or "active",
                    "weights": raw.get("weights") or {},
                    "thresholds": raw.get("thresholds") or {},
                    "metadata": raw.get("metadata") or {},
                },
                actor_id=actor_id,
                actor_role="admin",
            )
    return result


async def _run(args: argparse.Namespace) -> int:
    pack = load_metadata_seed_pack(args.path)
    await init_db(args.database_url or DATABASE_URL)
    try:
        async with get_session() as session:
            result = await apply_metadata_seed_pack(
                session,
                pack,
                actor_id=args.actor,
                dry_run=not args.apply,
                force=args.force,
            )
            if args.apply:
                await session.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        await shutdown_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Посеять редактируемые метаданные базы знаний.")
    parser.add_argument("--path", default=str(DEFAULT_METADATA_PACK_PATH), help="Путь к JSON seed pack.")
    parser.add_argument("--dry-run", action="store_true", help="Показать план без записи. Это режим по умолчанию.")
    parser.add_argument("--apply", action="store_true", help="Применить seed pack к базе данных.")
    parser.add_argument("--force", action="store_true", help="Обновить уже существующие seed-записи значениями из pack.")
    parser.add_argument("--actor", default="codex", help="Actor id для audit-полей.")
    parser.add_argument("--database-url", default=None, help="DATABASE_URL override. Defaults to env/server/.env.")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
