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


def test_offering_name_is_searchable_even_when_none_of_its_problem_names_match():
    payload = catalog(("Не удаётся подписать документ", [], "Ошибка при работе с сертификатом"))
    payload['services'][0]['offerings'][0]['title'] = 'Электронная подпись и сертификаты'
    result = search(payload, 'электронная подпись')['results']
    assert result[0]['title'] == 'Электронная подпись и сертификаты'
    assert result[0]['result_kind'] == 'service'
    assert result[0]['entry_point_key'] is None

@pytest.mark.parametrize('query', ['принтер', 'ghbynth'])
def test_service_name_query_prioritizes_the_general_service_before_setup_problems(query):
    payload = symptom_catalog()
    payload['services'][0]['offerings'].append({
        'full_code': 'public.print_setup', 'title': 'Подключение и настройка принтеров',
        'guided_scenario_enabled': True,
        'catalog_items': [{'entry_point_key': 'pin', 'title': 'Принтер: настроить выдачу по PIN', 'synonyms': [], 'description': ''}],
    })
    rows = search(payload, query)['results']
    assert rows[0]['result_kind'] == 'service'
    assert rows[0]['offering_full_code'] == 'public.print'
    assert rows[1]['offering_full_code'] == 'public.print_setup'
    symptom = search(payload, 'принтер не печатает')['results'][0]
    assert symptom['result_kind'] == 'problem' and symptom['offering_full_code'] == 'public.print'


def test_service_section_names_find_only_the_public_offering_rows():
    result = search(catalog(("Не печатает документ", [], "")), 'рабочее место')['results']
    assert len(result) == 1
    assert result[0]['title'] == 'Печать'
    assert result[0]['result_kind'] == 'service'


def symptom_catalog():
    offerings = [
        ('print', 'Принтеры и МФУ', ['Принтер не печатает', 'Принтер отключён или недоступен', 'Не работает двусторонняя печать']),
        ('computer', 'Компьютеры и системные блоки', ['Компьютер не включается', 'Ноутбук не включается или не заряжается']),
        ('software', 'Установка и изменение программ', ['Установить новую программу', 'Программа не запускается']),
        ('os', 'Windows и ALT Linux', ['Система не загружается', 'Не получается войти в систему']),
        ('budget', 'Электронный бюджет', ['Электронный бюджет: не удаётся войти', 'Электронный бюджет: ошибка работы системы']),
        ('eis', 'ЕИС', ['ЕИС: не удаётся войти', 'ЕИС: ошибка электронной подписи']),
        ('mail', 'Электронная почта', ['Не удаётся открыть почту', 'Не отправляется письмо']),
        ('network', 'Сеть, интернет и VPN', ['Нет интернета', 'VPN не подключается']),
        ('meeting', 'Видеосвязь', ['Не получается подключиться к встрече']),
        ('new', 'Создание учётной записи', ['Создание учётной записи']),
        ('other', 'Другая проблема', ['Не нашёл свою проблему', 'Нужна консультация ИТ']),
    ]
    return {'services': [{'service_code': 'public', 'title': 'Услуги', 'offerings': [
        {'full_code': 'public.' + code, 'title': title, 'guided_scenario_enabled': True,
         'catalog_items': [{'entry_point_key': str(i), 'title': entry, 'synonyms': [], 'description': ''}
                           for i, entry in enumerate(entries)]}
        for code, title, entries in offerings]}]}


@pytest.mark.parametrize('query', ['не работает', 'перестало работать', 'сломалось', 'у меня не работает'])
def test_general_failure_search_finds_different_services_without_setup_or_fallback_noise(query):
    rows = search(symptom_catalog(), query)['results']
    codes = {r['offering_full_code'] for r in rows}
    assert {'public.print', 'public.computer', 'public.budget', 'public.mail', 'public.network'} <= codes
    assert not codes & {'public.new', 'public.other'}


@pytest.mark.parametrize('query', ['не включается', 'не запускается', 'не могу запустить', 'не загружается'])
def test_startup_phrases_cross_devices_programs_and_operating_systems(query):
    codes = {r['offering_full_code'] for r in search(symptom_catalog(), query)['results']}
    assert {'public.computer', 'public.software', 'public.os'} <= codes
    assert not codes & {'public.new', 'public.other'}


@pytest.mark.parametrize('query', ['не могу войти', 'не пускает', 'ошибка входа', 'не удается авторизоваться'])
def test_login_phrases_find_multiple_systems_without_conflating_a_meeting_connection(query):
    codes = {r['offering_full_code'] for r in search(symptom_catalog(), query)['results']}
    assert {'public.budget', 'public.eis', 'public.os'} <= codes
    assert 'public.meeting' not in codes
    assert 'public.eis' not in {r['offering_full_code'] for r in search(symptom_catalog(), query)['results']
                              if r['entry_point_key'] == '1'}  # signature error is not a login error


@pytest.mark.parametrize('query', ['не могу открыть', 'не открывается', 'неоткрывается'])
def test_opening_phrases_find_the_same_mail_problem(query):
    assert 'public.mail' in {r['offering_full_code'] for r in search(symptom_catalog(), query)['results']}


@pytest.mark.parametrize('query,code', [('не работает электронный бюджет', 'public.budget'),
    ('не работает ЕИС', 'public.eis'), ('не работает интернет', 'public.network'),
    ('не работает принтр', 'public.print')])
def test_symptom_expansion_preserves_named_service_or_device(query, code):
    rows = search(symptom_catalog(), query)['results']
    assert rows and {r['offering_full_code'] for r in rows} == {code}
    assert all(r['offering_title'] for r in rows)


def test_named_service_is_browsable_when_its_exact_symptom_is_not_an_entrance():
    rows = search(symptom_catalog(), 'не включается принтер')['results']
    assert rows and {r['offering_full_code'] for r in rows} == {'public.print'}
    assert any(r['result_kind'] == 'service' and r['entry_point_key'] is None for r in rows)


def test_generic_symptom_interleaves_offerings_before_repeating_one_with_many_problems():
    from tickets.service_catalog_search import search_public_catalog
    payload = symptom_catalog()
    payload['services'][0]['offerings'][0]['catalog_items'] = [
        {'entry_point_key': str(i), 'title': f'А {i}: не работает печать'} for i in range(40)]
    before = deepcopy(payload)
    rows = search_public_catalog(payload, 'не работает', limit=5)['results']
    assert len(rows) == 5 and len({r['offering_full_code'] for r in rows}) == 5
    assert payload == before
    assert search_public_catalog(payload, 'не работает', limit=5)['results'] == rows


def test_semantics_do_not_erase_unknown_entities_or_positive_negative_distinctions():
    payload = symptom_catalog()
    for query in ['не работает космопульт', 'не включается единорог', 'включается', 'принтер работает', 'нет принтера']:
        assert not search(payload, query)['results'], query


@pytest.mark.parametrize('query', ['нет интернета', 'пропал интернет', 'нет сети'])
def test_connection_phrases_keep_the_internet_or_network_entity(query):
    rows = search(symptom_catalog(), query)['results']
    assert rows and {r['offering_full_code'] for r in rows} == {'public.network'}


def test_generic_failures_do_not_promote_setup_description_with_unrelated_negation():
    payload = symptom_catalog()
    payload['services'][0]['offerings'][-2]['description'] = 'Укажите отдел и дату начала работы. Пароли не указывайте.'
    assert 'public.new' not in {r['offering_full_code'] for r in search(payload, 'не работает')['results']}


def test_generic_error_keeps_complete_literal_matches_of_specific_error_families():
    payload = catalog(('Ошибка входа', [], ''), ('Ошибка электронной подписи', [], ''),
                      ('Ошибка печати', [], ''), ('Ошибка работы системы', [], ''))
    assert {r['entry_point_key'] for r in search(payload, 'ошибка')['results']} == {'0', '1', '2', '3'}
    assert [r['entry_point_key'] for r in search(payload, 'ошибка входа')['results']] == ['0']


def test_configured_fallback_must_resolve_to_one_public_published_entrance():
    from tickets.service_catalog_runtime import configured_requester_fallback
    offering = {'full_code': 'other.actual', 'service_code': 'other', 'visibility': 'public',
        'lifecycle_status': 'published', 'metadata': {'requester_fallback': {'entry_point_key': 'not_found'}}}
    entries = {'other.actual': [{'entry_point_key': 'not_found'}]}
    assert configured_requester_fallback([offering], entries, {'other'}) == (offering, 'not_found')
    assert configured_requester_fallback([offering], entries, {'internal'}) is None
    assert configured_requester_fallback([offering], {}, {'other'}) is None
    assert configured_requester_fallback([offering, {**offering, 'full_code': 'other.second'}],
        {**entries, 'other.second': entries['other.actual']}, {'other'}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('visibility', ['public', 'internal'])
async def test_runtime_fallback_uses_real_parent_visibility_before_synthetic_defaults(monkeypatch, visibility):
    from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver
    from tickets import request_scenario_catalog
    offering = {'service_code': 'other', 'code': 'actual', 'full_code': 'other.actual', 'public_title': 'Другая проблема',
        'visibility': 'public', 'lifecycle_status': 'published', 'metadata': {'requester_fallback': {'entry_point_key': 'not_found'}}}
    class Repo:
        async def list_services(self, **kwargs):
            return [{'code': 'other', 'public_title': 'Другое', 'visibility': visibility, 'lifecycle_status': 'published'}]
        async def list_offerings(self, **kwargs):
            return [offering]
    async def published(session):
        return {'other.actual': [{'entry_point_key': 'not_found'}]}
    monkeypatch.setattr(request_scenario_catalog, 'published_catalog_entries', published)
    resolver = ServiceCatalogRuntimeResolver(None)
    resolver.repo = Repo()
    payload = await resolver.current_catalog_for_requester()
    assert payload['fallback']['full_code'] == ('other.actual' if visibility == 'public' else 'other.unknown')


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
