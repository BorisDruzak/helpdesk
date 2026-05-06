from types import SimpleNamespace

from tickets.knowledge_provider import (
    KnowledgeArticleSuggestion,
    KnowledgeCatalogEntry,
    clean_knowledge_text,
    knowledge_source_summary,
    load_knowledge_catalog,
    search_catalog_articles_for_ticket,
    ticket_knowledge_search_text,
)


def test_knowledge_catalog_loader_reads_external_json_source(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        """
        [
          {"id": "KB-1", "title": "DNS article", "keywords": ["dns", "domain"]},
          {"id": "KB-1", "title": "Duplicate should be skipped", "keywords": ["duplicate"]},
          {"id": "", "title": "Invalid", "keywords": ["invalid"]}
        ]
        """,
        encoding="utf-8",
    )

    entries = load_knowledge_catalog(str(catalog_path))

    assert len(entries) == 1
    assert entries[0].id == "KB-1"
    assert entries[0].url == "/app/knowledge/KB-1"
    assert entries[0].keywords == ("dns", "domain")


def test_catalog_search_scores_and_deduplicates_existing_articles():
    ticket = SimpleNamespace(
        title="Portal shows HTTP 502 Bad Gateway",
        description={"symptom": "upstream gateway error", "host": "portal.example"},
        requester_resolution_summary=None,
        resolution_summary=None,
        ticket_type="incident",
        source="web",
        custom_fields={},
    )
    catalog = [
        KnowledgeCatalogEntry(
            id="KB-HTTP-502",
            title="РћС€РёР±РєР° 502 Bad Gateway",
            url="/app/knowledge/KB-HTTP-502",
            keywords=("502", "bad gateway", "upstream"),
        ),
        KnowledgeCatalogEntry(
            id="KB-DNS",
            title="DNS",
            url="/app/knowledge/KB-DNS",
            keywords=("dns",),
        ),
    ]

    assert "gateway error" in ticket_knowledge_search_text(ticket)
    assert search_catalog_articles_for_ticket(ticket, catalog=catalog, limit=2) == [
        KnowledgeArticleSuggestion(
            id="KB-HTTP-502",
            title="РћС€РёР±РєР° 502 Bad Gateway",
            url="/app/knowledge/KB-HTTP-502",
        )
    ]
    results = search_catalog_articles_for_ticket(ticket, catalog=catalog, limit=2)
    assert results[0].source_type == "catalog"
    assert results[0].score == 80
    assert results[0].match_reasons == ["502", "bad gateway", "upstream"]
    assert search_catalog_articles_for_ticket(ticket, {"KB-HTTP-502"}, catalog=catalog, limit=2) == []


def test_catalog_search_uses_token_index_for_reordered_keyword_phrases():
    ticket = SimpleNamespace(
        title="Nginx proxy returns 502",
        description="Upstream service unavailable after deploy",
        requester_resolution_summary=None,
        resolution_summary=None,
        ticket_type="incident",
        source="monitoring",
        custom_fields={},
    )
    catalog = [
        KnowledgeCatalogEntry(
            id="KB-REVERSE-PROXY",
            title="Reverse proxy upstream outage",
            url="/app/knowledge/KB-REVERSE-PROXY",
            keywords=("reverse proxy upstream", "backend service unavailable"),
        ),
    ]

    results = search_catalog_articles_for_ticket(ticket, catalog=catalog, limit=1)

    assert results
    assert results[0].id == "KB-REVERSE-PROXY"
    assert results[0].source_type == "catalog_index"
    assert results[0].score >= 40
    assert "reverse proxy upstream" in results[0].match_reasons


def test_knowledge_summary_is_source_visible_and_conservative():
    summary = knowledge_source_summary(
        articles=[
            KnowledgeArticleSuggestion(id="KB-HTTP-502", title="РћС€РёР±РєР° 502", url="/app/knowledge/KB-HTTP-502"),
            KnowledgeArticleSuggestion(id="KB-HTTP-502", title="Duplicate", url="/app/knowledge/KB-HTTP-502"),
        ],
        tickets=[SimpleNamespace(id="ticket-1", number="T-000101")],
    )

    assert summary.sources == ["KB-HTTP-502", "T-000101"]
    assert summary.confidence == "high"
    assert summary.source_count == 2
    assert summary.text is not None
    assert summary.text.startswith("AI-рекомендация / Бета:")
    assert "действия не запускаются автоматически" in summary.text


def test_clean_knowledge_text_handles_empty_values():
    assert clean_knowledge_text(None) is None
    assert clean_knowledge_text("  ") is None
    assert clean_knowledge_text(" KB-1 ") == "KB-1"
