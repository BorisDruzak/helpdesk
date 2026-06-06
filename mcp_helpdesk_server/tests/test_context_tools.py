from __future__ import annotations

import pytest

from mcp_helpdesk_server.tools import context_tools


@pytest.mark.asyncio
async def test_context_search_validates_empty_query() -> None:
    payload = await context_tools.helpdesk_context_search({"query": ""})

    assert payload["status"] == "error"
    assert payload["error_code"] == "QUERY_REQUIRED"


@pytest.mark.asyncio
async def test_context_search_caps_limit_and_returns_bounded_payload(monkeypatch) -> None:
    from scripts import context_index

    captured = {}

    def fake_search_index(**kwargs):
        captured.update(kwargs)
        return [
            {
                "kind": "doc",
                "title": "Observer",
                "path": "server/docs/OBSERVER_LAYER.md",
                "line_start": 1,
                "summary": "observer summary",
                "rank": 1.0,
            }
        ]

    monkeypatch.setattr(context_index, "search_index", fake_search_index)

    payload = await context_tools.helpdesk_context_search({"query": "observer", "limit": 999, "profile": "contract"})

    assert payload["status"] == "ok"
    assert captured["limit"] == 50
    assert payload["results"][0]["path"] == "server/docs/OBSERVER_LAYER.md"


@pytest.mark.asyncio
async def test_context_freshness_reports_without_rebuild(monkeypatch) -> None:
    from scripts import context_index

    def fake_freshness_status(**kwargs):
        return {
            "exists": True,
            "stale": True,
            "reason": "stale",
            "changed_paths": ["docs/QUICK_LOOKUP.md"],
            "missing_paths": [],
            "new_paths": [],
        }

    monkeypatch.setattr(context_index, "freshness_status", fake_freshness_status)

    payload = await context_tools.helpdesk_context_freshness({})

    assert payload["status"] == "stale"
    assert payload["stale_sources_count"] == 1
    assert payload["recommended_command"] == "python scripts/build_context_index.py --force"
