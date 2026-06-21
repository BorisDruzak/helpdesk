from __future__ import annotations

import base64
import io
import zipfile

import pytest

from knowledge import ingestion_service as ingestion_module


pytestmark = pytest.mark.db_cleanup("knowledge")

def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


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


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_defaults_to_internal_draft_and_rag_inherit(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "import-safe-defaults",
            "title": "Import Safe Defaults",
            "visibility": "support_internal",
            "lifecycle_status": "active",
            "allow_rag": False,
        },
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-safe-defaults",
            "source_kind": "markdown",
            "source_name": "safe-defaults.md",
            "slug": "safe-defaults-import-api",
            "item_type": "article",
            "title": "Safe Defaults Import API",
            "body": "# Safe Defaults Import API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    assert payload["job"]["status"] == "review_required"
    assert payload["item"]["status"] == "draft"
    assert payload["item"]["visibility"] == "support_internal"
    assert payload["item"]["metadata"]["ai_rag_policy"] == "inherit"
    assert payload["item"]["metadata"]["import_mode"] == "safe_draft"


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_rejects_rag_policy_that_conflicts_with_section(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "import-rag-disabled",
            "title": "Import RAG Disabled",
            "visibility": "support_internal",
            "lifecycle_status": "active",
            "allow_rag": False,
        },
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-rag-disabled",
            "source_kind": "markdown",
            "source_name": "rag-conflict.md",
            "slug": "rag-conflict-import-api",
            "item_type": "article",
            "title": "RAG Conflict Import API",
            "visibility": "support_internal",
            "metadata": {"ai_rag_policy": "allowed"},
            "body": "# RAG Conflict Import API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 400
    payload = await resp.json()
    assert payload["error"] == "validation_error"
    assert "ai_rag_policy=allowed" in payload["details"]


@pytest.mark.asyncio
async def test_knowledge_import_jobs_list_and_detail_are_acl_safe(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "import-job-detail", "title": "Import Job Detail", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    create_resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-job-detail",
            "source_kind": "markdown",
            "source_name": "detail-secret-token.md",
            "slug": "import-job-detail-api",
            "item_type": "article",
            "title": "Import Job Detail API",
            "visibility": "support_internal",
            "body": "# Import Job Detail API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )
    assert create_resp.status == 200
    created = await create_resp.json()
    job_id = created["job"]["job_id"]

    list_resp = await test_client.get("/api/web/knowledge/import/jobs", headers=_auditor_headers())
    assert list_resp.status == 200
    jobs_payload = await list_resp.json()
    listed = next(job for job in jobs_payload["jobs"] if job["job_id"] == job_id)
    assert listed["source_name"] == "detail-secret-token.md"
    assert listed["status"] == "review_required"

    detail_resp = await test_client.get(f"/api/web/knowledge/import/jobs/{job_id}", headers=_auditor_headers())
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    job = detail_payload["job"]
    assert job["job_id"] == job_id
    assert job["status"] == "review_required"
    assert job["space"]["code"] == "import-job-detail"
    assert job["created_item_id"] == created["item"]["item_id"]
    assert job["created_version_id"] == created["version"]["version_id"]
    assert job["stats_json"]["chunk_count"] >= 1
    assert job["metadata_json"] == {}
    assert "body" not in str(detail_payload).lower()

    missing_resp = await test_client.get("/api/web/knowledge/import/jobs/not-a-job", headers=_auditor_headers())
    assert missing_resp.status == 404


@pytest.mark.asyncio
async def test_knowledge_import_observer_events_are_recorded_and_redacted(test_client) -> None:
    preview_resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "markdown",
            "source_name": "observer-secret-token.md",
            "body": "# Observer Import\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": True,
        },
    )
    assert preview_resp.status == 200

    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "import-observer", "title": "Import Observer", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    create_resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-observer",
            "source_kind": "markdown",
            "source_name": "observer-secret-token.md",
            "slug": "import-observer-api",
            "item_type": "article",
            "title": "Import Observer API",
            "visibility": "support_internal",
            "body": "# Import Observer API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )
    assert create_resp.status == 200
    created = await create_resp.json()

    blocked_resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "url",
            "source_name": "blocked-secret-token",
            "url": "https://outside.example.test/runbook.md?token=secret-token&password=hidden",
        },
    )
    assert blocked_resp.status == 400

    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import AgentRuntimeAudit

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AgentRuntimeAudit)
                .where(AgentRuntimeAudit.source == "knowledge_import")
                .order_by(AgentRuntimeAudit.created_at.asc())
            )
        ).scalars().all()

    event_types = [row.event_type for row in rows]
    assert "knowledge.import.preview_created" in event_types
    assert "knowledge.import.ai_enrichment_blocked" in event_types
    assert "knowledge.import.drafts_created" in event_types
    assert "knowledge.import.failed" in event_types
    assert any((row.details_json or {}).get("job_id") == created["job"]["job_id"] for row in rows)
    audit_dump = str([row.details_json for row in rows])
    assert "secret-token" not in audit_dump
    assert "password=hidden" not in audit_dump
    assert "outside.example.test" not in audit_dump


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_can_run_auto_segmentation_profile(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "import-segments", "title": "Import Segments", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-segments",
            "source_kind": "markdown",
            "source_name": "segmented-import.md",
            "slug": "segmented-import-api",
            "item_type": "article",
            "title": "Segmented Import API",
            "visibility": "support_internal",
            "body": "# Segmented Import API\n\n## Symptoms\nCan not connect.\n\n## Fix\nRestart VPN.",
            "ai_enrichment_enabled": False,
            "auto_segment_after_import": True,
            "segmentation_profile_code": "default-auto",
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    assert payload["segmentation"]["enabled"] is True
    assert payload["segmentation"]["status"] == "completed"
    assert payload["segmentation"]["profile_code"] == "default-auto"
    assert payload["segmentation"]["job"]["mode"] == "auto"
    assert [segment["title"] for segment in payload["segmentation"]["segments"]] == ["Symptoms", "Fix"]


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_queues_indexing_when_enabled(test_client) -> None:
    settings_resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=_admin_headers(),
        json={
            "search_mode": "hybrid_vector",
            "keyword_enabled": True,
            "full_text_enabled": True,
            "vector_enabled": True,
        },
    )
    assert settings_resp.status == 200

    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "import-indexing",
            "title": "Import Indexing",
            "visibility": "support_internal",
            "lifecycle_status": "active",
        },
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-indexing",
            "source_kind": "markdown",
            "source_name": "indexed-import.md",
            "slug": "indexed-import-api",
            "item_type": "article",
            "title": "Indexed Import API",
            "visibility": "support_internal",
            "body": "# Indexed Import API\n\n## Steps\nReconnect VPN.",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    assert payload["indexing"]["enabled"] is True
    assert payload["indexing"]["status"] in {"completed", "failed"}
    assert payload["indexing"]["job"]["scope_type"] == "item"
    assert payload["indexing"]["job"]["scope_ref"] == payload["item"]["item_id"]
    assert payload["indexing"]["job"]["metadata_json"]["version_id"] == payload["version"]["version_id"]
    assert payload["indexing"]["stats"]["chunks_seen"] >= 1
    assert "embedding_vector" not in str(payload["indexing"])


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_creates_governed_ai_enrichment_proposals(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "import-ai-proposals",
            "title": "Import AI Proposals",
            "visibility": "support_internal",
            "lifecycle_status": "active",
        },
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-ai-proposals",
            "source_kind": "markdown",
            "source_name": "vpn-secret-token.md",
            "slug": "import-ai-proposals-api",
            "item_type": "article",
            "title": "Import AI Proposals API",
            "visibility": "support_internal",
            "body": "# Import AI Proposals API\n\n## Symptoms\nVPN disconnects for remote users.\n\n## Fix\nReconnect VPN and refresh DNS.",
            "ai_enrichment_enabled": True,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    proposals = payload["ai_enrichment"]["proposals"]
    proposal_types = {proposal["proposal_type"] for proposal in proposals}
    assert payload["ai_enrichment"]["status"] == "review_required"
    assert {"summary", "tags", "glossary_term", "graph_node", "duplicate"} <= proposal_types
    assert all(proposal["status"] == "pending" for proposal in proposals)
    assert all(proposal["target_ref"] for proposal in proposals)
    assert "secret-token" not in str(proposals)
    assert "VPN disconnects for remote users" not in str(proposals)

    graph_proposal = next(proposal for proposal in proposals if proposal["proposal_type"] == "graph_node")
    review_resp = await test_client.post(
        f"/api/web/knowledge/ai/proposals/{graph_proposal['proposal_id']}/review",
        headers=_admin_headers(),
        json={"action": "approve", "note": "apply graph proposal"},
    )
    assert review_resp.status == 200
    reviewed = await review_resp.json()
    assert reviewed["proposal"]["status"] == "approved"
    assert reviewed["proposal"]["applied_refs"]["node_ids"]


def _docx_base64(text: str) -> str:
    buffer = io.BytesIO()
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(f"<w:p><w:r><w:t>{part}</w:t></w:r></w:p>" for part in text.splitlines() if part.strip())
        + "</w:body></w:document>"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_knowledge_import_preview_parses_uploaded_docx_and_pdf(test_client) -> None:
    docx_resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "docx",
            "source_name": "vpn-secret-token.docx",
            "file_content_base64": _docx_base64("VPN DOCX Runbook\nRestart the VPN client."),
        },
    )

    assert docx_resp.status == 200
    docx_payload = await docx_resp.json()
    docx_preview = docx_payload["preview"]
    assert docx_preview["source_kind"] == "docx"
    assert docx_preview["body_format"] == "plain_text"
    assert docx_preview["detected_title"] == "VPN DOCX Runbook"
    assert docx_preview["section_count"] >= 1

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nstream\nBT (VPN PDF Runbook) Tj (Reconnect client) Tj ET\nendstream\nendobj\n%%EOF"
    pdf_resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "pdf",
            "source_name": "vpn.pdf",
            "file_content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        },
    )

    assert pdf_resp.status == 200
    pdf_preview = (await pdf_resp.json())["preview"]
    assert pdf_preview["source_kind"] == "pdf"
    assert pdf_preview["detected_title"] == "VPN PDF Runbook Reconnect client"
    assert pdf_preview["word_count"] >= 5


@pytest.mark.asyncio
async def test_knowledge_import_preview_blocks_url_and_git_without_fetch_policy_and_redacts_secrets(test_client) -> None:
    for source_kind, field_name in (("url", "url"), ("git", "repo_url")):
        resp = await test_client.post(
            "/api/web/knowledge/import/preview",
            headers=_admin_headers(),
            json={
                "source_kind": source_kind,
                "source_name": f"{source_kind}-secret-token",
                field_name: f"https://example.invalid/private?token=secret-token&password=hidden",
            },
        )

        assert resp.status == 400
        payload = await resp.json()
        assert payload["error"] == "remote_import_blocked"
        assert "secret-token" not in str(payload)
        assert "password=hidden" not in str(payload)


@pytest.mark.asyncio
async def test_knowledge_import_preview_blocks_remote_host_outside_allowlist(test_client, monkeypatch) -> None:
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ENABLED", True, raising=False)
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS", ("docs.example.test",), raising=False)

    resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "url",
            "source_name": "outside-secret-token",
            "url": "https://outside.example.test/safe/runbook.md?token=secret-token&password=hidden",
        },
    )

    assert resp.status == 400
    payload = await resp.json()
    assert payload["error"] == "remote_import_blocked"
    assert "outside.example.test" not in str(payload)
    assert "secret-token" not in str(payload)
    assert "password=hidden" not in str(payload)


@pytest.mark.asyncio
async def test_knowledge_import_preview_allows_url_through_explicit_allowlist(test_client, monkeypatch) -> None:
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ENABLED", True, raising=False)
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS", ("docs.example.test",), raising=False)

    def fake_fetch(self, payload):  # noqa: ANN001
        return ingestion_module.RemoteImportContent(
            source_kind="url",
            source_name="docs.example.test",
            body="# Remote URL Import\n\n## Fix\nReconnect VPN.",
            body_format="markdown",
            remote_source={"source_kind": "url", "host": "docs.example.test", "path": "/safe/runbook.md", "bytes": 43},
        )

    monkeypatch.setattr(ingestion_module.KnowledgeRemoteImportFetcher, "fetch", fake_fetch)

    resp = await test_client.post(
        "/api/web/knowledge/import/preview",
        headers=_admin_headers(),
        json={
            "source_kind": "url",
            "source_name": "url-secret-token",
            "url": "https://docs.example.test/safe/runbook.md?token=secret-token&password=hidden",
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    preview = payload["preview"]
    assert preview["source_kind"] == "url"
    assert preview["source_name"] == "docs.example.test"
    assert preview["detected_title"] == "Remote URL Import"
    assert preview["remote_source"] == {
        "source_kind": "url",
        "host": "docs.example.test",
        "path": "/safe/runbook.md",
        "bytes": 43,
    }
    assert "secret-token" not in str(payload)
    assert "password=hidden" not in str(payload)


@pytest.mark.asyncio
async def test_knowledge_import_create_drafts_allows_git_through_explicit_allowlist(test_client, monkeypatch) -> None:
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ENABLED", True, raising=False)
    monkeypatch.setattr(ingestion_module.config, "KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS", ("git.example.test",), raising=False)

    def fake_fetch(self, payload):  # noqa: ANN001
        return ingestion_module.RemoteImportContent(
            source_kind="git",
            source_name="git.example.test/team/runbooks",
            body="# Remote Git Import\n\n## Fix\nReconnect VPN.",
            body_format="markdown",
            remote_source={
                "source_kind": "git",
                "host": "git.example.test",
                "repo": "git.example.test/team/runbooks",
                "ref": "main",
                "file_count": 1,
                "bytes": 42,
            },
        )

    monkeypatch.setattr(ingestion_module.KnowledgeRemoteImportFetcher, "fetch", fake_fetch)

    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "import-remote-git",
            "title": "Import Remote Git",
            "visibility": "support_internal",
            "lifecycle_status": "active",
        },
    )
    assert space_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/import/create-drafts",
        headers=_admin_headers(),
        json={
            "space_code": "import-remote-git",
            "source_kind": "git",
            "repo_url": "https://git.example.test/team/runbooks.git?token=secret-token",
            "ref": "main",
            "slug": "remote-git-import-api",
            "item_type": "article",
            "title": "Remote Git Import API",
            "visibility": "support_internal",
            "ai_enrichment_enabled": False,
        },
    )

    assert resp.status == 200
    payload = await resp.json()
    assert payload["preview"]["source_kind"] == "git"
    assert payload["preview"]["remote_source"]["host"] == "git.example.test"
    assert payload["item"]["source_kind"] == "imported_document"
    assert payload["version"]["body_format"] == "markdown"
    assert payload["job"]["status"] == "review_required"
    assert "secret-token" not in str(payload)
