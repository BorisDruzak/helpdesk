from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.service_catalog_repo import ServiceCatalogRepo
from scripts.seed_service_catalog import seed_service_catalog


@pytest.mark.asyncio
async def test_service_catalog_seed_dry_run_does_not_mutate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        summary = await seed_service_catalog(session, dry_run=True)
        services = await ServiceCatalogRepo(session).list_services()

    assert summary["dry_run"] is True
    assert summary["would_create"]["services"]
    assert services == []


@pytest.mark.asyncio
async def test_service_catalog_seed_is_idempotent_and_preserves_admin_edits(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        first = await seed_service_catalog(session)
        await session.commit()

    async with session_maker() as session:
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": "workplace",
                "public_title": "Custom workplace title",
                "short_description": "Admin edited description",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()

    async with session_maker() as session:
        second = await seed_service_catalog(session)
        await session.commit()
        repo = ServiceCatalogRepo(session)
        workplace = await repo.get_service_by_code("workplace")
        catalog = await repo.list_offerings(service_code="other", published_only=False)

    assert first["created"]["services"]
    assert second["skipped"]["services"]
    assert workplace["public_title"] == "Custom workplace title"
    assert any(offering["full_code"] == "other.unknown" for offering in catalog)
