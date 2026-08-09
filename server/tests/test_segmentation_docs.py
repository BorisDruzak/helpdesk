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
