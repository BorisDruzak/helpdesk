from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ingestion_service import KnowledgeIngestionService
from knowledge.search_service import KnowledgeSearchService


@pytest.mark.asyncio
async def test_markdown_ingestion_creates_internal_draft_version_and_chunks(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "imports", "title": "Imports", "visibility": "support_internal", "lifecycle_status": "active"}, actor_id="admin")
        result = await KnowledgeIngestionService(session).ingest_text(
            {
                "space_code": "imports",
                "source_kind": "markdown",
                "source_name": "vpn.md",
                "title": "VPN импорт",
                "body": "# VPN\n\nПроверить подключение.\n\n## Ошибка\n\nПереподключить.",
                "visibility": "support_internal",
            },
            actor_id="support",
        )
        await session.commit()

    assert result["job"]["status"] == "review_required"
    assert result["item"]["status"] == "draft"
    assert result["version"]["version_number"] == 1
    assert result["chunk_count"] >= 2

    async with session_maker() as session:
        requester_results = await KnowledgeSearchService(session).search(query="VPN", actor_role="requester")
        support_results = await KnowledgeSearchService(session).search(query="VPN", actor_role="support")

    assert requester_results == []
    assert support_results == []


@pytest.mark.asyncio
async def test_ingestion_failure_redacts_secret_values(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await KnowledgeIngestionService(session).fail_job_redacted(
            space_code="missing",
            source_name="secret.txt",
            error=RuntimeError("token=super-secret-password"),
            actor_id="support",
        )
        await session.commit()

    assert result["status"] == "failed"
    assert "super-secret-password" not in result["error_message_redacted"]
