from copy import deepcopy
import pytest
from tests.test_request_scenario_unified import source
from tickets.request_scenario_fragments import extract_fragment, insert_fragment, FragmentDependencyError

pytestmark = pytest.mark.no_db


def destination_v4():
    raw = source()
    raw.update(schema_version=4, execution_semantics=2)
    return raw


def test_extraction_drops_outside_edges_but_reports_them():
    raw = source()
    fragment, dependencies = extract_fragment(raw, ['questions'])
    assert [block['id'] for block in fragment['blocks']] == ['questions']
    assert fragment['blocks'][0]['transitions'] == []
    assert fragment['entry_points'] == []
    assert {'kind': 'block', 'key': 'submit', 'label': 'submit'} in dependencies
    assert raw['blocks'][0]['transitions']


def test_insert_remaps_internal_fields_and_requires_external_mappings():
    raw = source()
    raw['blocks'].insert(1, {'id': 'additional', 'kind': 'form_page', 'title': 'More',
        'fields': [{'key': 'detail', 'label': 'Details', 'type': 'text', 'visible_when':
            {'op': 'eq', 'source': 'answer', 'field': 'affected', 'value': 'one'}}], 'transitions': []})
    fragment, dependencies = extract_fragment(raw, ['additional'])
    assert {'kind': 'field', 'key': 'affected', 'label': 'affected'} in dependencies
    with pytest.raises(FragmentDependencyError):
        insert_fragment(destination_v4(), fragment, position={'x': 0, 'y': 0}, mappings={})
    result, inserted = insert_fragment(destination_v4(), fragment, position={'x': 10, 'y': 20}, mappings={'fields': {'affected': 'affected'}, 'facts': {'detail': 'detail'}})
    added = next(block for block in result['blocks'] if block['id'] == inserted[0])
    assert added['id'] != 'additional'
    assert added['fields'][0]['key'] != 'detail'
    assert added['fields'][0]['visible_when']['field'] == 'affected'
    assert result['schema_version'] == 4 and result['execution_semantics'] == 2
    assert source()['schema_version'] == 2

def test_insert_remaps_internal_edges_fields_aliases_and_button_keys():
    raw = source()
    raw['schema_version'] = 4
    raw['execution_semantics'] = 2
    page = raw['blocks'][0]
    page['fields'][0]['aliases'] = ['legacy_affected']
    page['transition_mode'] = 'buttons'
    page['transitions'] = [{'to': 'submit', 'button': {'key': 'next', 'label': 'Next'}}]
    fragment, _ = extract_fragment(raw, ['questions', 'submit'])
    merged, inserted = insert_fragment(raw, fragment, position={'x': 20, 'y': 40}, mappings={'facts': {'affected': 'new_affected', 'hidden': 'new_hidden'}})
    page = next(block for block in merged['blocks'] if block['id'] == inserted[0])
    assert page['transitions'][0]['to'] == inserted[1]
    assert page['transitions'][0]['button']['key'] != 'next'
    assert page['fields'][0]['aliases'] and page['fields'][0]['aliases'][0] != 'legacy_affected'
    assert page['fields'][1]['visible_when']['field'] == page['fields'][0]['key']

def test_external_condition_mapping_rejects_incompatible_field_type():
    raw = source()
    raw['blocks'].insert(1, {'id': 'additional', 'kind': 'form_page', 'title': 'More',
        'fields': [{'key': 'detail', 'label': 'Details', 'type': 'text', 'visible_when':
            {'op': 'eq', 'source': 'answer', 'field': 'affected', 'value': 'all'}}], 'transitions': []})
    fragment, _ = extract_fragment(raw, ['additional'])
    destination = destination_v4()
    destination['blocks'][0]['fields'].append({'key': 'wrong', 'type': 'checkbox', 'label': 'Wrong'})
    with pytest.raises(FragmentDependencyError):
        insert_fragment(destination, fragment, position={'x': 0, 'y': 0}, mappings={'fields': {'affected': 'wrong'}, 'facts': {'detail': 'detail'}})

def test_fragment_calendar_requires_explicit_matching_mapping():
    from tests.test_request_scenario_v3_processing import definition
    raw = definition().model_dump(mode='json')
    raw['processing']['sla_profiles']['urgent'].update(time_basis='business', calendar_id=7)
    fragment, deps = extract_fragment(raw, ['questions', 'submit'])
    assert {'kind': 'calendar', 'key': '7', 'label': '7'} in deps
    destination = deepcopy(raw)
    destination.update(schema_version=4, execution_semantics=3)
    destination['processing']['sla_profiles']['urgent']['calendar_id'] = 8
    with pytest.raises(FragmentDependencyError):
        insert_fragment(destination, fragment, position={'x': 0, 'y': 0}, mappings={'routes': {'printing': 'printing'}, 'sla_profiles': {'urgent': 'urgent'}, 'facts': {'affected': 'new_affected', 'hidden': 'new_hidden'}})
    result, ids = insert_fragment(destination, fragment, position={'x': 0, 'y': 0}, mappings={'routes': {'printing': 'printing'}, 'sla_profiles': {'urgent': 'urgent'}, 'calendars': {'7': 8}, 'facts': {'affected': 'new_affected', 'hidden': 'new_hidden'}})
    assert ids

@pytest.mark.asyncio
async def test_saved_fragment_captures_revision_and_retains_cloned_assets(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import uuid
    import tickets.request_scenario_fragment_library as library
    from web_api.dto.request_scenario_fragments import FragmentCreate
    from app.db.request_scenario_models import RequestStudioFragmentAsset
    raw = source()
    source_asset = {'asset_id': str(uuid.uuid4()), 'name': 'a.png', 'mime_type': 'image/png', 'size_bytes': 3, 'url': ''}
    source_asset['url'] = f"/api/web/request-scenario-assets/{source_asset['asset_id']}/download"
    raw['blocks'][0]['fields'][0]['help_attachments'] = [source_asset]
    clone = deepcopy(source_asset)
    clone['asset_id'] = str(uuid.uuid4())
    clone['url'] = f"/api/web/request-scenario-assets/{clone['asset_id']}/download"
    class Session:
        def __init__(self): self.added = []
        def add(self, value): self.added.append(value)
        async def flush(self):
            for row in self.added:
                if hasattr(row, 'title') and row.id is None: row.id = str(uuid.uuid4())
    session = Session()
    source_id = str(uuid.uuid4())
    row = SimpleNamespace(id=source_id, title='Source', archived=False, service_code='workplace')
    draft = SimpleNamespace(revision=4, definition=raw)
    repo = SimpleNamespace(session=session, auth=SimpleNamespace(actor_id='admin'), detail=AsyncMock(return_value=(row, draft)), _audit=AsyncMock(), _service_lock=AsyncMock())
    monkeypatch.setattr(library, 'copy_material_sources', AsyncMock(return_value={source_asset['asset_id']: object()}))
    async def clone_assets(session_, target, definition, sources, owner):
        assert target == source_id and source_asset['asset_id'] in sources
        copied = deepcopy(definition)
        copied['blocks'][0]['fields'][0]['help_attachments'] = [clone]
        return copied, {source_asset['asset_id']: clone}
    monkeypatch.setattr(library, 'clone_material_assets', clone_assets)
    payload = FragmentCreate(title='Example', source_scenario_id=source_id, source_revision=4, block_ids=['questions'])
    result = await library.create_fragment(repo, payload)
    assert result['definition']['blocks'][0]['fields'][0]['help_attachments'] == [clone]
    assert any(isinstance(item, RequestStudioFragmentAsset) and item.asset_id == clone['asset_id'] for item in session.added)
    raw['blocks'][0]['title'] = 'Changed later'
    assert result['definition']['blocks'][0]['title'] != 'Changed later'
    assert clone['asset_id'] != source_asset['asset_id']
    stale = payload.model_copy(update={'source_revision': 3})
    with pytest.raises(library.ScenarioAdminError) as error:
        await library.create_fragment(repo, stale)
    assert error.value.code == 'REVISION_CONFLICT'

@pytest.mark.asyncio
async def test_insert_rejects_stale_fragment_before_writes(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import tickets.request_scenario_fragment_library as library
    from web_api.dto.request_scenario_fragments import FragmentInsert
    fragment = SimpleNamespace(archived=False, revision=2)
    monkeypatch.setattr(library, 'get_fragment', AsyncMock(return_value=fragment))
    repo = SimpleNamespace(detail=AsyncMock(), session=SimpleNamespace())
    payload = FragmentInsert(revision=1, fragment_revision=1, position={'x': 0, 'y': 0})
    with pytest.raises(library.ScenarioAdminError) as error:
        await library.insert_saved_fragment(repo, 'destination', 'fragment', payload)
    assert error.value.code == 'FRAGMENT_REVISION_CONFLICT'
    repo.detail.assert_not_awaited()

def test_fragment_routes_registered_under_existing_studio_root():
    from aiohttp import web
    from routes import setup_routes
    app = web.Application()
    setup_routes(app)
    routes = {(route.method, route.resource.canonical) for route in app.router.routes()}
    base = '/api/web/admin/request-studio'
    assert ('GET', base + '/fragments') in routes
    assert ('POST', base + '/fragments') in routes
    assert ('GET', base + '/fragments/{fragment_id}') in routes
    assert ('POST', base + '/fragments/{fragment_id}/archive') in routes
    assert ('POST', base + '/scenarios/{identifier}/fragments/{fragment_id}/insert') in routes
    assert ('POST', base + '/scenarios/{identifier}/upgrade-v4') in routes

def test_duplicate_selected_field_or_alias_rejected():
    raw = source()
    raw['blocks'][0]['fields'][1]['key'] = raw['blocks'][0]['fields'][0]['key']
    with pytest.raises(ValueError):
        extract_fragment(raw, ['questions'])
    raw = source()
    raw['blocks'][0]['fields'][0]['aliases'] = ['duplicated']
    raw['blocks'][0]['fields'][1]['aliases'] = ['duplicated']
    with pytest.raises(ValueError):
        extract_fragment(raw, ['questions'])


def test_insert_requires_explicit_unique_fact_assignment():
    fragment, _ = extract_fragment(source(), ['questions'])
    with pytest.raises(FragmentDependencyError) as error:
        insert_fragment(destination_v4(), fragment, position={'x': 0, 'y': 0}, mappings={})
    assert {item['key'] for item in error.value.dependencies if item['kind'] == 'fact'} == {'affected', 'hidden'}
    with pytest.raises(FragmentDependencyError):
        insert_fragment(destination_v4(), fragment, position={'x': 0, 'y': 0}, mappings={'facts': {'affected': 'affected', 'hidden': 'new_hidden'}})
    mapped, ids = insert_fragment(destination_v4(), fragment, position={'x': 0, 'y': 0}, mappings={'facts': {'affected': 'new_affected', 'hidden': 'new_hidden'}})
    page = next(block for block in mapped['blocks'] if block['id'] == ids[0])
    assert [field['process_mapping']['fact_key'] for field in page['fields']] == ['new_affected', 'new_hidden']

@pytest.mark.asyncio
async def test_insert_rejects_legacy_destination_before_cloning(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import tickets.request_scenario_fragment_library as library
    from web_api.dto.request_scenario_fragments import FragmentInsert
    fragment = SimpleNamespace(archived=False, revision=1)
    monkeypatch.setattr(library, 'get_fragment', AsyncMock(return_value=fragment))
    clone = AsyncMock()
    monkeypatch.setattr(library, 'clone_material_assets', clone)
    row = SimpleNamespace(archived=False, service_code='service')
    draft = SimpleNamespace(revision=1, definition=source())
    repo = SimpleNamespace(detail=AsyncMock(return_value=(row, draft)), _service_lock=AsyncMock())
    payload = FragmentInsert(revision=1, fragment_revision=1, position={'x': 0, 'y': 0})
    with pytest.raises(library.ScenarioAdminError) as error:
        await library.insert_saved_fragment(repo, 'destination', 'fragment', payload)
    assert error.value.code == 'UPGRADE_REQUIRED'
    clone.assert_not_awaited()


def test_duplicate_destination_fact_and_alias_rejected():
    fragment, _ = extract_fragment(source(), ['questions'])
    target = destination_v4()
    target['blocks'][0]['fields'][0]['process_mapping'] = {'fact_key': 'shared'}
    target['blocks'][0]['fields'][1]['process_mapping'] = {'fact_key': 'shared'}
    with pytest.raises(ValueError):
        insert_fragment(target, fragment, position={'x': 0, 'y': 0}, mappings={})
