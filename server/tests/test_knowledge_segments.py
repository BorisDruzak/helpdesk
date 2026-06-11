from __future__ import annotations

import pytest


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}
REQUESTER_HEADERS = {"Authorization": "Bearer test-ui-user:knowledge-requester"}


async def _create_article(test_client, *, slug: str = "segmented-vpn", body: str | None = None) -> tuple[dict, dict]:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": f"{slug}-space", "title": f"{slug} space", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": f"{slug}-space",
            "slug": slug,
            "item_type": "article",
            "title": "Connectivity article",
            "summary": "Baseline article for segmentation",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    article_body = body or (
        "# VPN access\n\n"
        "Check the tunnel adapter and DNS suffix before escalation.\n\n"
        "## MFA token\n\n"
        "Ask the requester to refresh the authenticator prompt and retry sign-in."
    )
    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": "Connectivity article", "body_format": "markdown", "body": article_body},
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]
    return item, version


@pytest.mark.asyncio
async def test_manual_segment_create_and_list(test_client) -> None:
    item, version = await _create_article(test_client)
    body = version["body"]
    selected_text = "Check the tunnel adapter and DNS suffix before escalation."
    start_offset = body.index(selected_text)
    end_offset = start_offset + len(selected_text)

    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={
            "version_id": version["version_id"],
            "segment_type": "manual",
            "title": "VPN prerequisite checks",
            "summary": "Manual retrieval segment for first-line VPN checks",
            "text": selected_text,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "keywords": ["vpn", "dns", "adapter"],
            "boost": 2.5,
            "visibility": "requester",
            "embedding_enabled": False,
            "full_text_enabled": True,
        },
    )
    assert create_resp.status == 200
    created = await create_resp.json()
    assert created["status"] == "ok"
    assert created["display_message"] == "Сегмент знаний сохранён"
    segment = created["segment"]
    assert segment["segment_type"] == "manual"
    assert segment["status"] == "active"
    assert segment["title"] == "VPN prerequisite checks"
    assert segment["keywords"] == ["vpn", "dns", "adapter"]
    assert segment["content_hash"]

    list_resp = await test_client.get(f"/api/web/knowledge/items/{item['item_id']}/segments", headers=SUPPORT_HEADERS)
    assert list_resp.status == 200
    payload = await list_resp.json()
    assert payload["status"] == "ok"
    assert [row["segment_id"] for row in payload["segments"]] == [segment["segment_id"]]


@pytest.mark.asyncio
async def test_manual_segment_update_and_archive(test_client) -> None:
    item, version = await _create_article(test_client, slug="segment-update-archive")
    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"], "title": "Old title", "text": "Segment update body", "keywords": ["old"]},
    )
    assert create_resp.status == 200
    segment = (await create_resp.json())["segment"]

    patch_resp = await test_client.patch(
        f"/api/web/knowledge/segments/{segment['segment_id']}",
        headers=ADMIN_HEADERS,
        json={"title": "Updated title", "keywords": ["updated"], "boost": 4},
    )
    assert patch_resp.status == 200
    updated = await patch_resp.json()
    assert updated["display_message"] == "Сегмент знаний обновлён"
    assert updated["segment"]["title"] == "Updated title"
    assert updated["segment"]["keywords"] == ["updated"]

    delete_resp = await test_client.delete(f"/api/web/knowledge/segments/{segment['segment_id']}", headers=ADMIN_HEADERS)
    assert delete_resp.status == 200
    archived = await delete_resp.json()
    assert archived["display_message"] == "Сегмент знаний архивирован"
    assert archived["segment"]["status"] == "archived"

    list_resp = await test_client.get(f"/api/web/knowledge/items/{item['item_id']}/segments", headers=SUPPORT_HEADERS)
    assert list_resp.status == 200
    payload = await list_resp.json()
    assert payload["segments"] == []


@pytest.mark.asyncio
async def test_requester_cannot_create_segments(test_client) -> None:
    item, version = await _create_article(test_client, slug="requester-segment-denied")
    resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=REQUESTER_HEADERS,
        json={"version_id": version["version_id"], "title": "Denied", "text": "Denied"},
    )
    assert resp.status == 403
    payload = await resp.json()
    assert payload["error_code"] == "FORBIDDEN"
    assert payload["display_message"] == "Недостаточно прав для разметки знаний"


@pytest.mark.asyncio
async def test_auto_segmentation_splits_headings_without_ai(test_client) -> None:
    item, version = await _create_article(test_client, slug="auto-segmented-vpn")
    resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/auto",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"], "profile_code": "default-auto"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["status"] == "ok"
    assert payload["display_message"] == "Авторазметка выполнена без AI"
    assert payload["job"]["mode"] == "auto"
    assert payload["job"]["status"] == "completed"
    assert [segment["segment_type"] for segment in payload["segments"]] == ["auto", "auto"]
    assert [segment["title"] for segment in payload["segments"]] == ["VPN access", "MFA token"]

    profiles_resp = await test_client.get("/api/web/knowledge/segmentation-profiles", headers=SUPPORT_HEADERS)
    assert profiles_resp.status == 200
    profiles = await profiles_resp.json()
    assert profiles["profiles"][0]["code"] == "default-auto"
    assert profiles["profiles"][0]["mode"] == "auto"


@pytest.mark.asyncio
async def test_admin_can_create_segmentation_profile(test_client) -> None:
    create_resp = await test_client.post(
        "/api/web/knowledge/segmentation-profiles",
        headers=ADMIN_HEADERS,
        json={
            "code": "paragraph-auto",
            "title": "Paragraph auto split",
            "mode": "auto",
            "split_by_headings": False,
            "split_by_paragraphs": True,
            "default_segment_boost": 1.5,
        },
    )
    assert create_resp.status == 200
    created = await create_resp.json()
    assert created["display_message"] == "Профиль разметки сохранён"
    assert created["profile"]["code"] == "paragraph-auto"
    assert created["profile"]["split_by_headings"] is False

    profiles_resp = await test_client.get("/api/web/knowledge/segmentation-profiles", headers=SUPPORT_HEADERS)
    assert profiles_resp.status == 200
    profiles = await profiles_resp.json()
    codes = {profile["code"] for profile in profiles["profiles"]}
    assert "paragraph-auto" in codes
