from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeTaxonomyTerm
from scripts.seed_knowledge_metadata import DEFAULT_METADATA_PACK_PATH, apply_metadata_seed_pack, load_metadata_seed_pack


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_default_metadata_seed_dry_run_apply_and_idempotency(test_engine) -> None:
    pack = load_metadata_seed_pack(DEFAULT_METADATA_PACK_PATH)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        dry_run = await apply_metadata_seed_pack(session, pack, actor_id="seed-test", dry_run=True)
        assert dry_run["dry_run"] is True
        assert dry_run["summary"]["create_taxonomy_terms"] >= 20
        assert not (await session.execute(select(KnowledgeTaxonomyTerm))).scalars().all()

    async with session_maker() as session:
        applied = await apply_metadata_seed_pack(session, pack, actor_id="seed-test")
        await session.commit()
        assert applied["dry_run"] is False
        assert applied["summary"]["create_taxonomy_terms"] >= 20

    async with session_maker() as session:
        second = await apply_metadata_seed_pack(session, pack, actor_id="seed-test")
        await session.commit()
        assert second["summary"]["skip_taxonomy_terms"] >= applied["summary"]["create_taxonomy_terms"]
        assert second["summary"]["create_taxonomy_terms"] == 0


@pytest.mark.asyncio
async def test_metadata_seed_does_not_override_admin_changes_without_force(test_engine) -> None:
    pack = load_metadata_seed_pack(DEFAULT_METADATA_PACK_PATH)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        await apply_metadata_seed_pack(session, pack, actor_id="seed-test")
        term = (
            await session.execute(select(KnowledgeTaxonomyTerm).where(KnowledgeTaxonomyTerm.code == "vpn"))
        ).scalar_one()
        term.title = "Админская категория VPN"
        await session.commit()

    async with session_maker() as session:
        skipped = await apply_metadata_seed_pack(session, pack, actor_id="seed-test")
        term = (
            await session.execute(select(KnowledgeTaxonomyTerm).where(KnowledgeTaxonomyTerm.code == "vpn"))
        ).scalar_one()
        assert skipped["summary"]["skip_taxonomy_terms"] > 0
        assert term.title == "Админская категория VPN"

    async with session_maker() as session:
        forced = await apply_metadata_seed_pack(session, pack, actor_id="seed-test", force=True)
        term = (
            await session.execute(select(KnowledgeTaxonomyTerm).where(KnowledgeTaxonomyTerm.code == "vpn"))
        ).scalar_one()
        assert forced["summary"]["update_taxonomy_terms"] > 0
        assert term.title == "VPN"


def test_metadata_seed_rejects_restricted_content_marked_requester_visible() -> None:
    pack = load_metadata_seed_pack(DEFAULT_METADATA_PACK_PATH)
    bad_pack = deepcopy(pack)
    bad_pack["taxonomy_terms"][0]["visibility"] = "requester"
    bad_pack["taxonomy_terms"][0]["metadata"] = {"classification": "security_restricted"}

    with pytest.raises(ValueError, match="restricted seed term cannot be requester-visible"):
        load_metadata_seed_pack(data=bad_pack)
