from pathlib import Path


DOCS_ROOT = Path("server/docs")


def test_segmentation_docs_define_external_knowledge_contract_without_fallback() -> None:
    boundaries = (DOCS_ROOT / "SEGMENTATION_BOUNDARIES.md").read_text(encoding="utf-8")
    adr = (DOCS_ROOT / "adr/0001-helpdesk-external-domain-ports.md").read_text(
        encoding="utf-8"
    )
    api = (DOCS_ROOT / "KNOWLEDGE_PLATFORM_API_V1.md").read_text(encoding="utf-8")
    normalized_boundaries = " ".join(boundaries.split())
    normalized_adr = " ".join(adr.split())
    normalized_api = " ".join(api.split())

    assert "KnowledgePort" in boundaries
    assert "no local fallback" in boundaries
    assert "preceding verified application release" in normalized_boundaries
    assert "PR-11" in boundaries
    assert "not a Helpdesk route" in api
    assert "knowledge_unavailable" in api
    assert "never authorises a local Knowledge lookup or a local fallback" in normalized_api
    assert "opaque" in api
    assert "correlation_id" in api
    assert "cursor pagination" in api
    assert "redacted" in api
    for operation in (
        "POST /v1/search",
        "POST /v1/suggestions",
        "GET /v1/items/{item_ref}/versions/{version_ref}",
        "POST /v1/resolution-drafts",
        "POST /v1/feedback",
    ):
        assert operation in api
    for scope in (
        "knowledge.search",
        "knowledge.suggest",
        "knowledge.read_projection",
        "knowledge.resolution_draft",
        "knowledge.feedback",
    ):
        assert scope in api
    assert "preceding verified application release" in normalized_adr
    assert "PR-11" in adr


def test_docs_reference_external_knowledge_contract_not_removed_runtime() -> None:
    architecture = Path("docs/ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
    ticket_system = (DOCS_ROOT / "TICKET_SYSTEM.md").read_text(encoding="utf-8")
    database = (DOCS_ROOT / "DATABASE.md").read_text(encoding="utf-8")

    assert "external Knowledge Platform" in architecture
    assert "server/knowledge/" not in architecture
    assert "KnowledgePort" in ticket_system
    assert "knowledge_unavailable" in ticket_system
    assert "PR-11" in database
    assert "Retained historical Knowledge tables" in database


def test_codemaps_do_not_advertise_removed_local_knowledge_runtime() -> None:
    server_codemap = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8")
    agent_runtime = Path("pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md").read_text(
        encoding="utf-8"
    )

    for text in (server_codemap, agent_runtime):
        for removed_surface in (
            "server/knowledge/",
            "server/ai/",
            "/api/knowledge/",
            "/api/web/knowledge/",
            "/app/knowledge",
            "KNOWLEDGE_PLATFORM.md",
        ):
            assert removed_surface not in text
    assert "KnowledgePort" in server_codemap
    assert "PR-7" in server_codemap
    assert "PR-11" in server_codemap


def test_server_codemap_does_not_preserve_deleted_knowledge_platform_claims() -> None:
    server_codemap = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8")

    for deleted_artifact in (
        "test_knowledge_ask.py",
        "test_knowledge_access_service.py",
        "webapp/src/features/knowledge/",
        "knowledge.metadata.manage",
        "seed_knowledge_metadata.py",
        "content_packs/knowledge/",
        "server/web_api/knowledge_handlers.py",
        "knowledge_audience_live_smoke.py",
        "/app/admin/knowledge/",
        "test_knowledge_portal.py",
        "knowledge_feedback_events",
        "knowledge_correction_requests",
        "knowledge_user_bookmarks",
        "KNOWLEDGE_REMOTE_IMPORT_",
        "knowledge_audience_rule",
        "knowledge_provider.py",
        "app.repos.knowledge_repo",
        "TicketKnowledgeLink",
    ):
        assert deleted_artifact not in server_codemap


def test_server_codemap_limits_knowledge_to_external_boundary_and_history() -> None:
    lines = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8").splitlines()
    allowed_boundary_markers = (
        "local Knowledge runtime",
        "KnowledgePort",
        "knowledge_unavailable",
        "knowledge_attempts",
        "future Knowledge and Registry Platforms",
        "Endpoint, Knowledge and Registry",
        "KNOWLEDGE_PLATFORM_API_V1.md",
        "Knowledge API integration target",
        "server/domain_ports/knowledge.py",
        "Knowledge request",
        "legacy Knowledge access",
        "KNOWLEDGE_PORT_MODE",
        "no local Knowledge RBAC",
    )

    for line_number, line in enumerate(lines, start=1):
        if "knowledge" in line.casefold():
            assert line_number <= 50, line
            assert any(marker in line for marker in allowed_boundary_markers), line
