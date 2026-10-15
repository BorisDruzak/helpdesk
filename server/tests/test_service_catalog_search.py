"""Deterministic requester search over the already authorized public projection."""
from copy import deepcopy

import pytest

pytestmark = pytest.mark.no_db


def catalog(*entries):
    return {"services": [{"service_code": "workplace", "title": "Рабочее место", "offerings": [{
        "full_code": "workplace.print", "title": "Печать", "guided_scenario_enabled": True,
        "catalog_items": [dict(key=str(index), entry_point_key=str(index), title=title,
            synonyms=synonyms, description=description, category_title="Оборудование", help_mode="guided")
            for index, (title, synonyms, description) in enumerate(entries)],
    }]}]}


def search(payload, query):
    from tickets.service_catalog_search import search_public_catalog
    return search_public_catalog(payload, query)


@pytest.mark.parametrize("query", ["ПРИНТЕР НЕ ПЕЧАТАЕТ!!!", " принтер   не печатает ",
    "печатает не принтер", "принтера не печатает", "принт не печ", "принтр не печатает", "ghbynth yt gtxfnftn"])
def test_russian_forms_tokens_prefix_typo_and_keyboard_layout_find_entrance(query):
    result = search(catalog(("Принтер не печатает", ["Не могу распечатать", "Ошибка печати"], "")), query)
    assert result["results"][0]["entry_point_key"] == "0"
    assert result["results"][0]["offering_full_code"] == "workplace.print"
    assert result["results"][0]["category"] == "Оборудование"
    assert result["results"][0]["help_mode"] == "guided"


def test_yo_normalization_synonyms_and_explanation():
    result = search(catalog(("Проблемы с печатью", ["Печать не идёт"], "")), "печать не идет")
    assert result["results"][0]["match_reason"] == "Совпало дополнительное поисковое выражение"


def test_ranking_exact_then_phrase_then_synonym_then_tokens_then_prefix_then_typo():
    payload = catalog(
        ("Принтер не печатает", [], ""),
        ("Офисный принтер не печатает документы", [], ""),
        ("Проблемы с печатью", ["Принтер не печатает"], ""),
        ("Не печатает офисный принтер", [], ""),
        ("Принтеры не печатают", [], ""),
        ("Принтр не печатает", [], ""),
    )
    assert [row["entry_point_key"] for row in search(payload, "принтер не печатает")["results"]] == ["0", "1", "2", "3", "4", "5"]


def test_negation_is_neither_discarded_nor_fuzzily_invented():
    payload = catalog(("Принтер печатает", [], ""), ("Принтер не печатает", [], ""))
    assert [r["entry_point_key"] for r in search(payload, "принтер не печатает")["results"]] == ["1"]
    assert [r["entry_point_key"] for r in search(payload, "принтер печатает")["results"]] == ["0"]
    assert not search(payload, "нет принтера")["results"]


def test_ties_are_stable_and_results_do_not_mutate_or_expose_source_fields():
    payload = catalog(("Сбой", [], "Принтер"), ("Сбой", [], "Принтер"))
    payload["services"][0]["offerings"][0]["catalog_items"][0]["queue_id"] = "private"
    before = deepcopy(payload)
    result = search(payload, "принтер")
    assert [r["entry_point_key"] for r in result["results"]] == ["0", "1"]
    assert "private" not in str(result)
    assert payload == before


def test_empty_unrelated_and_oversized_queries_are_bounded():
    payload = catalog(("Принтер не печатает", [], ""))
    assert not search(payload, "")["results"]
    assert not search(payload, "совсем другая проблема")["results"]
    assert not search(payload, "принтер " * 1000)["results"]
    assert search(payload, "принтр не печатает")["suggestions"] == ["Принтер не печатает"]


def test_legacy_guided_offering_without_named_entrances_remains_searchable():
    payload = catalog()
    result = search(payload, "печать")["results"][0]
    assert result['entry_point_key'] is None
    assert result['help_mode'] == 'guided'


@pytest.mark.asyncio
async def test_current_handler_searches_only_the_requester_runtime_projection(monkeypatch):
    import json
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from web_api import service_catalog_handlers as handlers

    @asynccontextmanager
    async def session():
        yield object()

    class PublicResolver:
        def __init__(self, session):
            pass

        async def current_catalog_for_requester(self):
            return catalog(("Принтер не печатает", [], ""))

    monkeypatch.setattr(handlers, "get_session", session)
    monkeypatch.setattr(handlers, "ServiceCatalogRuntimeResolver", PublicResolver)
    response = await handlers.handle_service_catalog_current(SimpleNamespace(query={"q": "принтр не печатает"}))
    payload = json.loads(response.text)
    assert payload["status"] == "ok"
    assert payload["search"]["results"][0]["entry_point_key"] == "0"
