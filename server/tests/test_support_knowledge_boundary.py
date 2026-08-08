from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.check_domain_import_boundaries import find_forbidden_imports
from web_api.support_handlers import _build_support_knowledge_suggestions_payload


pytestmark = pytest.mark.no_db

WORKSPACE = Path(__file__).resolve().parents[2]


class _ExplodingSession:
    async def execute(self, _statement: object) -> object:
        raise AssertionError("support Knowledge projection must not query local persistence")


@pytest.mark.asyncio
async def test_support_projection_marks_knowledge_unavailable_without_suggestions() -> None:
    payload = await _build_support_knowledge_suggestions_payload(
        _ExplodingSession(),
        SimpleNamespace(ticket_id="ticket-boundary"),
    )

    assert payload.model_dump() == {
        "ticket_id": "ticket-boundary",
        "status": "unavailable",
        "code": "knowledge_unavailable",
        "suggestions": [],
        "similar_tickets": [],
        "articles": [],
        "requester_attempts": [],
        "ai_summary": {
            "text": None,
            "sources": [],
            "confidence": "none",
            "source_count": 0,
        },
        "diagnostics": {
            "provider": "external_knowledge_port",
            "provider_version": "v1",
            "provider_status": "unavailable",
            "external_provider_status": "not_configured",
            "fallback_reason": "knowledge_unavailable",
            "catalog_entry_count": 0,
            "query_tokens": [],
            "source_counts": {},
            "query_signals": [],
            "article_matches": {},
            "similar_ticket_matches": {},
        },
    }


def test_support_handler_has_no_local_knowledge_dependency() -> None:
    violations = find_forbidden_imports(WORKSPACE)

    assert [
        violation.imported
        for violation in violations
        if violation.path == WORKSPACE / "server" / "web_api" / "support_handlers.py"
    ] == []
