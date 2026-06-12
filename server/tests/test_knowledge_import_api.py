from __future__ import annotations

import pytest


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


@pytest.mark.asyncio
async def test_knowledge_import_preview_parses_markdown_without_ai(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "markdown",
            "source_name": "vpn-runbook.md",
            "body": "# VPN Runbook\n\n## Symptoms\nCan not connect.\n\n## Fix\nRestart VPN.",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    preview = payload["preview"]
    assert preview["source_kind"] == "markdown"
    assert preview["source_name"] == "vpn-runbook.md"
    assert preview["body_format"] == "markdown"
    assert preview["detected_title"] == "VPN Runbook"
    assert preview["section_count"] == 2
    assert [section["heading"] for section in preview["sections"]] == ["Symptoms", "Fix"]
    assert preview["ai_enrichment"]["enabled"] is False
    assert preview["ai_enrichment"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_uses_preview_payload_without_ai(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "import-api", "title": "Import API", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-api",
            "source_kind": "markdown",
            "source_name": "vpn-import.md",
            "slug": "vpn-import-api",
            "item_type": "article",
            "title": "VPN Import API",
            "visibility": "support_internal",
            "body": "# VPN Import API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    assert payload["ai_enrichment"]["status"] == "disabled"
    assert payload["job"]["status"] == "review_required"
    assert payload["item"]["slug"] == "vpn-import-api"
    assert payload["item"]["visibility"] == "support_internal"
    assert payload["version"]["body_format"] == "markdown"
    assert payload["preview"]["detected_title"] == "VPN Import API"
