from __future__ import annotations

import pytest


pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


@pytest.mark.asyncio
async def test_knowledge_search_settings_admin_get_and_update(test_client) -> None:
    defaults_resp = await test_client.get("/api/web/knowledge/search-settings", headers=ADMIN_HEADERS)
    assert defaults_resp.status == 200
    defaults = await defaults_resp.json()
    assert defaults["status"] == "ok"
    assert defaults["settings"]["settings_id"] == "global"
    assert defaults["settings"]["search_mode"] == "keyword_only"
    assert defaults["settings"]["keyword_enabled"] is True
    assert defaults["settings"]["vector_enabled"] is False
    assert defaults["settings"]["rerank_enabled"] is False
    assert defaults["settings"]["ai_query_rewrite_enabled"] is False
    assert defaults["settings"]["effective_mode"] == "keyword_only"
    assert defaults["settings"]["ai_enabled"] is False
    assert defaults["display_message"] == "Настройки поиска загружены"

    update_resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=ADMIN_HEADERS,
        json={
            "search_mode": "hybrid_no_ai",
            "full_text_enabled": True,
            "vector_enabled": False,
            "rerank_enabled": False,
            "ai_query_rewrite_enabled": False,
            "rag_answer_enabled": False,
            "max_results": 5,
            "snippet_length": 120,
            "keyword_weight": 1.25,
            "full_text_weight": 1.1,
            "metadata_json": {"note": "AI выключен"},
        },
    )
    assert update_resp.status == 200
    updated = await update_resp.json()
    assert updated["status"] == "ok"
    assert updated["settings"]["search_mode"] == "hybrid_no_ai"
    assert updated["settings"]["effective_mode"] == "hybrid_no_ai"
    assert updated["settings"]["ai_enabled"] is False
    assert updated["settings"]["max_results"] == 5
    assert updated["settings"]["snippet_length"] == 120
    assert updated["settings"]["metadata_json"]["note"] == "AI выключен"
    assert updated["display_message"] == "Настройки поиска сохранены"


@pytest.mark.asyncio
async def test_knowledge_search_settings_denies_support_mutation(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=SUPPORT_HEADERS,
        json={"search_mode": "hybrid_no_ai"},
    )
    assert resp.status == 403
    payload = await resp.json()
    assert payload["error_code"] == "FORBIDDEN"
    assert payload["display_message"] == "Недостаточно прав для настройки поиска"


@pytest.mark.asyncio
async def test_web_knowledge_search_uses_ai_off_keyword_baseline(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": "search-api", "title": "Search API", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": "search-api",
            "slug": "vpn-keyword-baseline",
            "item_type": "article",
            "title": "VPN keyword baseline",
            "summary": "Keyword search result without AI",
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
            "title": "VPN keyword baseline",
            "body_format": "markdown",
            "body": "Инструкция по восстановлению VPN без обращения к AI.",
        },
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]

    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert publish_resp.status == 200

    settings_resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=ADMIN_HEADERS,
        json={
            "search_mode": "keyword_only",
            "keyword_enabled": True,
            "full_text_enabled": False,
            "vector_enabled": False,
            "rerank_enabled": False,
            "ai_query_rewrite_enabled": False,
            "rag_answer_enabled": False,
            "max_results": 10,
        },
    )
    assert settings_resp.status == 200

    search_resp = await test_client.post(
        "/api/web/knowledge/search",
        headers=SUPPORT_HEADERS,
        json={"query": "VPN", "surface": "admin_knowledge_search"},
    )
    assert search_resp.status == 200
    payload = await search_resp.json()
    assert payload["status"] == "ok"
    assert payload["search_mode"] == "keyword_only"
    assert payload["effective_mode"] == "keyword_only"
    assert payload["ai_used"] is False
    assert payload["display_message"] == "Поиск выполнен без AI"
    assert [item["slug"] for item in payload["results"]] == ["vpn-keyword-baseline"]
