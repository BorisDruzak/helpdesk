from __future__ import annotations

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.db_cleanup("knowledge")

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
    assert profiles["profiles"]
    assert all(profile["mode"] in {"auto", "manual_default", "ai"} for profile in profiles["profiles"])


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


@pytest.mark.asyncio
async def test_segment_revalidation_remaps_active_segment_to_new_version(test_client, test_engine) -> None:
    item, source_version = await _create_article(test_client, slug="segment-remap-active")
    selected_text = "Check the tunnel adapter and DNS suffix before escalation."
    source_start = source_version["body"].index(selected_text)
    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={
            "version_id": source_version["version_id"],
            "title": "VPN prerequisite checks",
            "text": selected_text,
            "start_offset": source_start,
            "end_offset": source_start + len(selected_text),
            "visibility": "requester",
        },
    )
    assert create_resp.status == 200
    source_segment = (await create_resp.json())["segment"]

    target_body = (
        "# VPN access\n\n"
        "Before collecting logs, Check the tunnel adapter and DNS suffix before escalation.\n\n"
        "## MFA token\n\n"
        "Ask the requester to retry sign-in."
    )
    target_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": "Connectivity article v2", "body_format": "markdown", "body": target_body},
    )
    assert target_resp.status == 200
    target_version = (await target_resp.json())["version"]

    remap_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/revalidate",
        headers=ADMIN_HEADERS,
        json={"source_version_id": source_version["version_id"], "target_version_id": target_version["version_id"]},
    )
    assert remap_resp.status == 200
    payload = await remap_resp.json()
    assert payload["status"] == "ok"
    assert payload["stats"]["segments_remapped"] == 1
    assert payload["stats"]["segments_stale"] == 0

    remapped = payload["segments"][0]
    assert remapped["version_id"] == target_version["version_id"]
    assert remapped["status"] == "active"
    assert remapped["text"] == selected_text
    assert remapped["start_offset"] == target_body.index(selected_text)
    assert remapped["metadata_json"]["remap_status"] == "matched_exact"
    assert remapped["metadata_json"]["remapped_from_segment_id"] == source_segment["segment_id"]

    async with test_engine.connect() as conn:
        audit_rows = (
            await conn.execute(
                text(
                    "SELECT event_type, severity, details_json FROM agent_runtime_audit "
                    "WHERE event_type = 'knowledge.segmentation.revalidated'"
                )
            )
        ).mappings().all()
    assert audit_rows[0]["severity"] == "info"
    assert audit_rows[0]["details_json"]["segments_remapped"] == 1


@pytest.mark.asyncio
async def test_segment_revalidation_marks_missing_text_stale(test_client) -> None:
    item, source_version = await _create_article(test_client, slug="segment-remap-stale")
    selected_text = "Check the tunnel adapter and DNS suffix before escalation."
    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={"version_id": source_version["version_id"], "title": "VPN prerequisite checks", "text": selected_text},
    )
    assert create_resp.status == 200

    target_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": "Connectivity article v2", "body_format": "markdown", "body": "# VPN access\n\nCollect fresh logs."},
    )
    assert target_resp.status == 200
    target_version = (await target_resp.json())["version"]

    remap_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/revalidate",
        headers=ADMIN_HEADERS,
        json={"source_version_id": source_version["version_id"], "target_version_id": target_version["version_id"]},
    )
    assert remap_resp.status == 200
    payload = await remap_resp.json()
    assert payload["stats"]["segments_remapped"] == 0
    assert payload["stats"]["segments_stale"] == 1
    assert payload["segments"][0]["status"] == "stale"
    assert payload["segments"][0]["start_offset"] is None
    assert payload["segments"][0]["metadata_json"]["remap_status"] == "stale_no_match"


@pytest.mark.asyncio
async def test_ai_segment_proposals_require_markup_policy_and_record_observer_event(test_client, test_engine) -> None:
    item, version = await _create_article(test_client, slug="segment-ai-blocked")

    resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/ai-proposals",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert resp.status == 409
    payload = await resp.json()
    assert payload["error_code"] == "AI_MARKUP_POLICY_BLOCKED"

    async with test_engine.connect() as conn:
        runtime_rows = (
            await conn.execute(
                text(
                    "SELECT event_type, severity, details_json FROM agent_runtime_audit "
                    "WHERE event_type = 'knowledge.segmentation.ai_blocked'"
                )
            )
        ).mappings().all()
    assert runtime_rows[0]["severity"] == "warning"
    assert runtime_rows[0]["details_json"]["item_id"] == item["item_id"]


@pytest.mark.asyncio
async def test_ai_segment_proposal_approve_and_reject_flow(test_client) -> None:
    item, version = await _create_article(test_client, slug="segment-ai-approval")
    policy_resp = await test_client.post(
        "/api/web/knowledge/ai/policies",
        headers=ADMIN_HEADERS,
        json={
            "policy_id": "markup-policy",
            "scope_type": "global",
            "task_type": "markup",
            "enabled": True,
            "ai_allowed": True,
            "auto_markup_allowed": True,
            "allow_cloud_for_requester_safe": True,
        },
    )
    assert policy_resp.status == 200

    proposal_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/ai-proposals",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert proposal_resp.status == 200
    payload = await proposal_resp.json()
    assert payload["job"]["mode"] == "ai"
    assert payload["stats"]["segments_proposed"] == 2
    assert [segment["segment_type"] for segment in payload["segments"]] == ["ai_proposed", "ai_proposed"]
    assert {segment["status"] for segment in payload["segments"]} == {"draft"}

    approve_resp = await test_client.post(
        f"/api/web/knowledge/segments/{payload['segments'][0]['segment_id']}/approve",
        headers=ADMIN_HEADERS,
        json={},
    )
    assert approve_resp.status == 200
    approved = await approve_resp.json()
    assert approved["segment"]["segment_type"] == "ai_approved"
    assert approved["segment"]["status"] == "active"

    reject_resp = await test_client.post(
        f"/api/web/knowledge/segments/{payload['segments'][1]['segment_id']}/reject",
        headers=ADMIN_HEADERS,
        json={"reason": "duplicate"},
    )
    assert reject_resp.status == 200
    rejected = await reject_resp.json()
    assert rejected["segment"]["segment_type"] == "ai_proposed"
    assert rejected["segment"]["status"] == "rejected"
    assert rejected["segment"]["metadata_json"]["reject_reason"] == "duplicate"


@pytest.mark.asyncio
async def test_segment_index_sync_writes_active_segments_to_chunks(test_client, test_engine) -> None:
    item, version = await _create_article(test_client, slug="segment-index-sync")
    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={
            "version_id": version["version_id"],
            "title": "Indexable segment",
            "text": "Segment text that should become a retrieval chunk.",
            "visibility": "requester",
            "embedding_enabled": True,
            "full_text_enabled": True,
        },
    )
    assert create_resp.status == 200
    segment = (await create_resp.json())["segment"]

    sync_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/index-sync",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert sync_resp.status == 200
    payload = await sync_resp.json()
    assert payload["status"] == "ok"
    assert payload["stats"]["chunks_synced"] == 1
    assert payload["stats"]["embedding_pending"] == 1

    async with test_engine.connect() as conn:
        chunk_rows = (
            await conn.execute(
                text(
                    "SELECT text, content_hash, embedding_ref, metadata_json FROM knowledge_chunks "
                    "WHERE version_id = :version_id AND metadata_json->>'source' = 'article_segment'"
                ),
                {"version_id": version["version_id"]},
            )
        ).mappings().all()
        audit_rows = (
            await conn.execute(
                text(
                    "SELECT severity, details_json FROM agent_runtime_audit "
                    "WHERE event_type = 'knowledge.segmentation.index_synced'"
                )
            )
        ).mappings().all()

    assert chunk_rows[0]["text"] == "Segment text that should become a retrieval chunk."
    assert chunk_rows[0]["content_hash"] == segment["content_hash"]
    assert chunk_rows[0]["embedding_ref"] is None
    assert chunk_rows[0]["metadata_json"]["segment_id"] == segment["segment_id"]
    assert chunk_rows[0]["metadata_json"]["embedding_status"] == "pending"
    assert audit_rows[0]["severity"] == "info"
    assert audit_rows[0]["details_json"]["chunks_synced"] == 1
