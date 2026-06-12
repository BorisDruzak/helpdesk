from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.repos.knowledge_repo import KnowledgeRepo


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


async def _published_item(
    test_client,
    *,
    space_code: str,
    slug: str,
    title: str,
    body: str,
    visibility: str = "requester",
) -> dict:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": space_code, "title": f"Space {space_code}", "visibility": visibility, "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": space_code,
            "slug": slug,
            "item_type": "article",
            "title": title,
            "summary": f"{title} summary",
            "visibility": visibility,
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
            "tags": ["vpn", "access"],
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]
    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": title, "body_format": "markdown", "body": body},
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]
    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert publish_resp.status == 200
    return (await publish_resp.json())["item"]


@pytest.mark.asyncio
async def test_knowledge_portal_home_lists_only_requester_safe_published_articles(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    requester_item = await _published_item(
        test_client,
        space_code=f"portal-{suffix}",
        slug=f"portal-vpn-{suffix}",
        title="VPN portal article",
        body="Requester-safe VPN instructions.",
        visibility="requester",
    )
    await _published_item(
        test_client,
        space_code=f"portal-int-{suffix}",
        slug=f"portal-internal-{suffix}",
        title="Internal runbook",
        body="Support-only runbook.",
        visibility="support_internal",
    )

    resp = await test_client.get("/api/knowledge/portal/home")
    assert resp.status == 200
    payload = await resp.json()

    assert payload["status"] == "ok"
    assert any(space["code"] == f"portal-{suffix}" for space in payload["spaces"])
    assert all(space["visibility"] in {"public", "requester", "agent_requester_safe"} for space in payload["spaces"])
    article_slugs = {article["slug"] for article in payload["recent_articles"]}
    assert requester_item["slug"] in article_slugs
    assert f"portal-internal-{suffix}" not in article_slugs
    assert all("current_version" not in article for article in payload["recent_articles"])


@pytest.mark.asyncio
async def test_knowledge_portal_home_ranks_popular_articles_from_persisted_portal_signals(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    low_signal = await _published_item(
        test_client,
        space_code=f"popular-low-{suffix}",
        slug=f"popular-low-{suffix}",
        title="Low signal VPN",
        body="Low signal body.",
        visibility="requester",
    )
    high_signal = await _published_item(
        test_client,
        space_code=f"popular-high-{suffix}",
        slug=f"popular-high-{suffix}",
        title="High signal VPN",
        body="High signal body.",
        visibility="requester",
    )

    await test_client.get(f"/api/knowledge/articles/{low_signal['slug']}")
    await test_client.get(f"/api/knowledge/articles/{high_signal['slug']}")
    await test_client.post(f"/api/knowledge/articles/{high_signal['slug']}/bookmark", json={"session_id": "rank-session"})
    await test_client.post(f"/api/knowledge/articles/{high_signal['slug']}/feedback", json={"helpful": True})

    resp = await test_client.get("/api/knowledge/portal/home")
    assert resp.status == 200
    payload = await resp.json()
    popular_slugs = [article["slug"] for article in payload["popular_articles"]]

    assert popular_slugs.index(high_signal["slug"]) < popular_slugs.index(low_signal["slug"])


@pytest.mark.asyncio
async def test_knowledge_article_detail_returns_body_for_requester_safe_slug(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    item = await _published_item(
        test_client,
        space_code=f"article-{suffix}",
        slug=f"article-vpn-{suffix}",
        title="VPN reader",
        body="# VPN\nUse the company profile to reconnect.",
        visibility="requester",
    )

    resp = await test_client.get(f"/api/knowledge/articles/{item['slug']}")
    assert resp.status == 200
    payload = await resp.json()

    assert payload["status"] == "ok"
    assert payload["article"]["slug"] == item["slug"]
    assert payload["article"]["title"] == "VPN reader"
    assert payload["version"]["body"] == "# VPN\nUse the company profile to reconnect."
    assert payload["segments"] == []
    assert payload["related_articles"] == []
    assert "source_refs" not in payload["version"]


@pytest.mark.asyncio
async def test_knowledge_article_detail_hides_support_internal_articles(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    item = await _published_item(
        test_client,
        space_code=f"article-int-{suffix}",
        slug=f"article-internal-{suffix}",
        title="Internal article",
        body="Internal-only body.",
        visibility="support_internal",
    )

    resp = await test_client.get(f"/api/knowledge/articles/{item['slug']}")
    assert resp.status == 404
    payload = await resp.json()
    assert payload["error"] == "not_found"


@pytest.mark.asyncio
async def test_knowledge_portal_service_sanitizes_direct_article_reads(test_engine) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from knowledge.portal_service import KnowledgePortalService

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        suffix = uuid.uuid4().hex[:8]
        await repo.upsert_space(
            {"code": f"service-{suffix}", "title": "Service portal", "visibility": "requester", "lifecycle_status": "active"},
            actor_id="admin",
        )
        item = await repo.create_item_draft(
            {
                "space_code": f"service-{suffix}",
                "slug": f"service-vpn-{suffix}",
                "item_type": "article",
                "title": "Service VPN",
                "summary": "Safe summary",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
                "metadata": {"portal_note": "hidden"},
            },
            actor_id="admin",
            actor_role="admin",
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": "Service VPN",
                "body_format": "markdown",
                "body": "Safe body",
                "source_refs": [{"kind": "document", "id": "ref-1"}],
                "metadata": {"portal_ref": "hidden"},
            },
            actor_id="admin",
            actor_role="admin",
        )
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin", actor_role="admin")
        await session.commit()

    async with session_maker() as session:
        detail = await KnowledgePortalService(session).article_detail(f"service-vpn-{suffix}", actor_role="requester")

    assert detail["article"]["slug"] == f"service-vpn-{suffix}"
    assert detail["version"]["body"] == "Safe body"
    assert "source_refs" not in detail["version"]
    assert "metadata" not in detail["article"]


@pytest.mark.asyncio
async def test_knowledge_article_feedback_and_correction_write_safe_events(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    item = await _published_item(
        test_client,
        space_code=f"feedback-{suffix}",
        slug=f"feedback-vpn-{suffix}",
        title="Feedback VPN",
        body="Feedback-safe body.",
        visibility="requester",
    )

    feedback_resp = await test_client.post(
        f"/api/knowledge/articles/{item['slug']}/feedback",
        json={"helpful": True, "session_id": "safe-session"},
    )
    assert feedback_resp.status == 200
    feedback_payload = await feedback_resp.json()
    assert feedback_payload["status"] == "ok"
    assert feedback_payload["event"]["event_type"] == "helpful"
    assert feedback_payload["event"]["item_id"] == item["item_id"]

    correction_resp = await test_client.post(
        f"/api/knowledge/articles/{item['slug']}/correction-request",
        json={"comment": "Step 2 is outdated", "session_id": "safe-session"},
    )
    assert correction_resp.status == 200
    correction_payload = await correction_resp.json()
    assert correction_payload["status"] == "ok"
    assert correction_payload["event"]["event_type"] == "not_helpful"
    assert correction_payload["event"]["result"] == "correction_requested"
    assert correction_payload["event"]["metadata"]["comment"] == "Step 2 is outdated"

    async with test_engine.connect() as conn:
        count = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM knowledge_feedback_events
                    WHERE item_id = :item_id
                      AND source_surface = 'requester_portal'
                      AND actor_role = 'requester'
                    """
                ),
                {"item_id": item["item_id"]},
            )
        ).scalar_one()
    assert count >= 2


@pytest.mark.asyncio
async def test_knowledge_article_portal_actions_write_dedicated_tables(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    item = await _published_item(
        test_client,
        space_code=f"portal-actions-{suffix}",
        slug=f"portal-actions-vpn-{suffix}",
        title="Portal actions VPN",
        body="Portal actions body.",
        visibility="requester",
    )

    detail_resp = await test_client.get(f"/api/knowledge/articles/{item['slug']}")
    assert detail_resp.status == 200
    correction_resp = await test_client.post(
        f"/api/knowledge/articles/{item['slug']}/correction-request",
        json={"comment": "Add split tunnel note", "session_id": "safe-session"},
    )
    assert correction_resp.status == 200
    bookmark_resp = await test_client.post(
        f"/api/knowledge/articles/{item['slug']}/bookmark",
        json={"session_id": "safe-session"},
    )
    assert bookmark_resp.status == 200

    async with test_engine.connect() as conn:
        view_count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM knowledge_article_views WHERE item_id = :item_id"),
                {"item_id": item["item_id"]},
            )
        ).scalar_one()
        correction_count = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM knowledge_correction_requests
                    WHERE item_id = :item_id
                      AND comment = 'Add split tunnel note'
                      AND status = 'open'
                    """
                ),
                {"item_id": item["item_id"]},
            )
        ).scalar_one()
        bookmark_count = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM knowledge_user_bookmarks
                    WHERE item_id = :item_id
                      AND bookmark_state = 'active'
                    """
                ),
                {"item_id": item["item_id"]},
            )
        ).scalar_one()
    assert view_count >= 1
    assert correction_count == 1
    assert bookmark_count == 1


@pytest.mark.asyncio
async def test_knowledge_article_bookmark_routes_require_requester_safe_article(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    requester_item = await _published_item(
        test_client,
        space_code=f"bookmark-{suffix}",
        slug=f"bookmark-vpn-{suffix}",
        title="Bookmark VPN",
        body="Bookmark-safe body.",
        visibility="requester",
    )
    internal_item = await _published_item(
        test_client,
        space_code=f"bookmark-int-{suffix}",
        slug=f"bookmark-internal-{suffix}",
        title="Bookmark internal",
        body="Internal bookmark body.",
        visibility="support_internal",
    )

    bookmark_resp = await test_client.post(
        f"/api/knowledge/articles/{requester_item['slug']}/bookmark",
        json={"session_id": "safe-session"},
    )
    assert bookmark_resp.status == 200
    assert (await bookmark_resp.json())["bookmark"]["bookmarked"] is True

    remove_resp = await test_client.delete(f"/api/knowledge/articles/{requester_item['slug']}/bookmark")
    assert remove_resp.status == 200
    assert (await remove_resp.json())["bookmark"]["bookmarked"] is False

    internal_resp = await test_client.post(
        f"/api/knowledge/articles/{internal_item['slug']}/bookmark",
        json={"session_id": "safe-session"},
    )
    assert internal_resp.status == 404


@pytest.mark.asyncio
async def test_knowledge_portal_space_and_tag_collections_are_requester_safe(test_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    requester_item = await _published_item(
        test_client,
        space_code=f"collection-{suffix}",
        slug=f"collection-vpn-{suffix}",
        title="Collection VPN",
        body="Collection-safe body.",
        visibility="requester",
    )
    internal_item = await _published_item(
        test_client,
        space_code=f"collection-int-{suffix}",
        slug=f"collection-internal-{suffix}",
        title="Collection internal",
        body="Internal collection body.",
        visibility="support_internal",
    )

    space_resp = await test_client.get(f"/api/knowledge/portal/spaces/collection-{suffix}")
    assert space_resp.status == 200
    space_payload = await space_resp.json()
    assert space_payload["status"] == "ok"
    assert space_payload["space"]["code"] == f"collection-{suffix}"
    assert [article["slug"] for article in space_payload["articles"]] == [requester_item["slug"]]

    tag_resp = await test_client.get("/api/knowledge/portal/tags/vpn")
    assert tag_resp.status == 200
    tag_payload = await tag_resp.json()
    tag_slugs = {article["slug"] for article in tag_payload["articles"]}
    assert requester_item["slug"] in tag_slugs
    assert internal_item["slug"] not in tag_slugs

    internal_space_resp = await test_client.get(f"/api/knowledge/portal/spaces/collection-int-{suffix}")
    assert internal_space_resp.status == 404
