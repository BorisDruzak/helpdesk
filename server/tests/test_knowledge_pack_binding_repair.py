from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from app.db.models import KnowledgeBinding, KnowledgeContentPackItem, KnowledgeItem, KnowledgeItemVersion, KnowledgeNode
from knowledge.content_pack_service import KnowledgeContentPackService


pytestmark = pytest.mark.db_cleanup("knowledge")

def _stale_pack() -> dict:
    return {
        "code": "it-self-service-baseline",
        "version": 2,
        "title": "IT Self-Service Baseline",
        "spaces": [{"code": "it-self-service", "title": "IT Self-Service", "visibility": "requester"}],
        "items": [
            {
                "slug": "laptop-power-basic",
                "type": "article",
                "space": "it-self-service",
                "title": "Ноутбук не включается: безопасные шаги",
                "summary": "Safe laptop checks.",
                "visibility": "requester",
                "status": "published",
                "owner": "servicedesk",
                "reviewer": "servicedesk",
                "review_due_days": 90,
                "bindings": [
                    {
                        "service_code": "workplace",
                        "offering_code": "workplace.laptop_issue",
                        "request_template_key": "laptop_issue",
                    }
                ],
                "body": "## Steps\n\nOriginal body.",
            }
        ],
    }


def _canonical_pack() -> dict:
    pack = _stale_pack()
    pack["items"][0]["bindings"] = [
        {
            "service_code": "workplace",
            "offering_code": "workplace.laptop_broken",
            "request_template_key": "breakage",
        }
    ]
    return pack


@pytest.mark.asyncio
async def test_repair_bindings_dry_run_does_not_mutate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        await service.apply_pack(_stale_pack(), actor_id="admin-test")
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeContentPackService(session).repair_pack_bindings(
            _canonical_pack(),
            actor_id="admin-test",
            dry_run=True,
        )
        await session.rollback()

    async with session_maker() as session:
        binding = (await session.execute(select(KnowledgeBinding))).scalar_one()

    assert result["summary"]["bindings_repaired"] == 1
    assert binding.offering_code == "workplace.laptop_issue"
    assert binding.request_template_key == "laptop_issue"


@pytest.mark.asyncio
async def test_repair_bindings_updates_stale_pack_item_and_preserves_body_version(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        await service.apply_pack(_stale_pack(), actor_id="admin-test")
        item = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.slug == "laptop-power-basic"))).scalar_one()
        version_before = (
            await session.execute(select(KnowledgeItemVersion).where(KnowledgeItemVersion.item_id == item.item_id))
        ).scalar_one()
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeContentPackService(session).repair_pack_bindings(
            _canonical_pack(),
            actor_id="admin-test",
            dry_run=False,
        )
        await session.commit()

    async with session_maker() as session:
        binding = (await session.execute(select(KnowledgeBinding))).scalar_one()
        versions = (await session.execute(select(KnowledgeItemVersion))).scalars().all()
        audit = (
            await session.execute(
                select(KnowledgeContentPackItem).where(KnowledgeContentPackItem.install_status == "bindings_repaired")
            )
        ).scalar_one()

    assert result["summary"]["bindings_repaired"] == 1
    assert binding.service_code == "workplace"
    assert binding.offering_code == "workplace.laptop_broken"
    assert binding.request_template_key == "breakage"
    assert len(versions) == 1
    assert versions[0].version_id == version_before.version_id
    assert versions[0].body == "## Steps\n\nOriginal body."
    assert audit.metadata_json["old_bindings"][0]["offering_code"] == "workplace.laptop_issue"
    assert audit.metadata_json["new_bindings"][0]["offering_code"] == "workplace.laptop_broken"


@pytest.mark.asyncio
async def test_repair_bindings_updates_graph_binding_edge_and_is_idempotent(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        await service.apply_pack(_stale_pack(), actor_id="admin-test")
        await session.commit()

    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        first = await service.repair_pack_bindings(_canonical_pack(), actor_id="admin-test")
        second = await service.repair_pack_bindings(_canonical_pack(), actor_id="admin-test")
        await session.commit()

    async with session_maker() as session:
        offering_nodes = (
            await session.execute(select(KnowledgeNode).where(KnowledgeNode.node_type == "offering"))
        ).scalars().all()

    assert first["summary"]["bindings_repaired"] == 1
    assert second["summary"]["bindings_repaired"] == 0
    assert {node.stable_key for node in offering_nodes} == {"offering:workplace.laptop_broken"}


@pytest.mark.asyncio
async def test_repair_ignores_non_pack_managed_admin_item(test_engine) -> None:
    pack = _canonical_pack()
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeContentPackService(session)
        repo = service
        await repo.apply_pack({**pack, "items": []}, actor_id="admin-test")
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeContentPackService(session).repair_pack_bindings(pack, actor_id="admin-test")
        await session.commit()

    assert result["summary"]["bindings_repaired"] == 0
