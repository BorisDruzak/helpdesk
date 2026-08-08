from pathlib import Path


def test_segmentation_docs_define_no_local_knowledge_fallback() -> None:
    text = Path("server/docs/SEGMENTATION_BOUNDARIES.md").read_text(encoding="utf-8")

    assert "KnowledgePort" in text
    assert "no local fallback" in text
