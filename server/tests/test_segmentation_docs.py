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

    assert "KnowledgePort" in boundaries
    assert "no local fallback" in boundaries
    assert "preceding verified application release" in normalized_boundaries
    assert "PR-11" in boundaries
    assert "not a Helpdesk route" in api
    assert "knowledge_unavailable" in api
    assert "never authorises a local Knowledge lookup or a local fallback" in api
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
