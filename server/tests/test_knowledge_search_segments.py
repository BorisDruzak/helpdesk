from __future__ import annotations

import pytest


pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_search_uses_active_manual_segment_keywords_without_ai(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": "segment-search", "title": "Segment search", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": "segment-search",
            "slug": "connectivity-runbook",
            "item_type": "article",
            "title": "Connectivity runbook",
            "summary": "General access troubleshooting",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={
            "title": "Connectivity runbook",
            "body_format": "markdown",
            "body": "General access troubleshooting. This article intentionally avoids the segment-only lookup term.",
        },
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]

    segment_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={
            "version_id": version["version_id"],
            "segment_type": "manual",
            "title": "Authenticator recovery segment",
            "text": "Operators use this segment when the requester has an authenticator prompt issue.",
            "keywords": ["totp-refresh-marker"],
            "visibility": "requester",
            "boost": 3,
        },
    )
    assert segment_resp.status == 200

    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert publish_resp.status == 200

    search_resp = await test_client.post(
        "/api/web/knowledge/search",
        headers=SUPPORT_HEADERS,
        json={"query": "totp-refresh-marker", "surface": "admin_knowledge_search"},
    )
    assert search_resp.status == 200
    payload = await search_resp.json()
    assert payload["status"] == "ok"
    assert payload["ai_used"] is False
    assert [item["slug"] for item in payload["results"]] == ["connectivity-runbook"]
    assert payload["results"][0]["snippet"] == "Operators use this segment when the requester has an authenticator prompt issue."
