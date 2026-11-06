"""PostgreSQL/HTTP checks for revisioned upgrades and retained fragments."""
from copy import deepcopy
from aiohttp import FormData
import pytest
from tests.test_request_scenario_admin_api import ADMIN, AUDITOR, BASE, seed, create

pytestmark = [pytest.mark.db_cleanup('full'), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_upgrade_is_atomic_admin_only_and_revision_guarded(test_client_light, test_engine):
    definition = await seed(test_engine)
    created = await create(test_client_light, definition)
    url = BASE + '/scenarios/' + created['scenario']['id']
    denied = await test_client_light.post(url + '/upgrade-v4', headers=AUDITOR, json={'revision': 1})
    assert denied.status == 403
    stale = await test_client_light.post(url + '/upgrade-v4', headers=ADMIN, json={'revision': 2})
    assert stale.status == 409
    modified = deepcopy(definition)
    modified.update(schema_version=4, execution_semantics=1, title='Not allowed')
    denied = await test_client_light.put(url + '/draft', headers=ADMIN, json={'revision': 1, 'definition': modified})
    assert denied.status == 409 and (await denied.json())['error_code'] == 'UPGRADE_REQUIRED'
    ok = await test_client_light.post(url + '/upgrade-v4', headers=ADMIN, json={'revision': 1})
    assert ok.status == 200, await ok.text()
    draft = (await ok.json())['data']['draft']
    assert draft['revision'] == 2 and draft['definition']['execution_semantics'] == 1
    assert draft['definition']['title'] == definition['title']
    retry = await test_client_light.post(url + '/upgrade-v4', headers=ADMIN, json={'revision': 1})
    assert retry.status == 409


@pytest.mark.asyncio
async def test_fragment_snapshot_assets_rebind_and_enforce_revisions(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr('web_api.request_scenario_asset_handlers.UPLOAD_DIR', tmp_path)
    definition = await seed(test_engine)
    created = await create(test_client_light, definition)
    scenario_id = created['scenario']['id']
    url = BASE + '/scenarios/' + scenario_id
    form = FormData()
    form.add_field('file', b'fragment content', filename='help.txt', content_type='text/plain')
    response = await test_client_light.post(url + '/attachments', headers=ADMIN, data=form)
    assert response.status == 200, await response.text()
    source_asset = (await response.json())['data']
    definition['blocks'][0]['fields'][0]['help_attachments'] = [source_asset]
    response = await test_client_light.put(url + '/draft', headers=ADMIN, json={'revision': 1, 'definition': definition})
    assert response.status == 200, await response.text()
    response = await test_client_light.post(BASE + '/fragments', headers=ADMIN, json={'title': 'Fragment',
        'source_scenario_id': scenario_id, 'source_revision': 2, 'block_ids': ['questions']})
    assert response.status == 200, await response.text()
    detail = (await response.json())['data']
    fragment_id = detail['fragment']['id']
    captured = detail['definition']['blocks'][0]['fields'][0]['help_attachments'][0]
    assert captured['asset_id'] != source_asset['asset_id']
    assert any(item['kind'] == 'fact' and item['key'] == 'summary' for item in detail['external_dependencies'])
    insert_url = url + '/fragments/' + fragment_id + '/insert'
    body = {'revision': 2, 'fragment_revision': 1, 'position': {'x': 0, 'y': 0},
            'mappings': {'facts': {'summary': 'other_summary'}}}
    response = await test_client_light.post(insert_url, headers=ADMIN, json=body)
    assert response.status == 409 and (await response.json())['error_code'] == 'UPGRADE_REQUIRED'
    upgraded = await test_client_light.post(url + '/upgrade-v4', headers=ADMIN, json={'revision': 2})
    assert upgraded.status == 200, await upgraded.text()
    body['revision'] = 3
    response = await test_client_light.post(insert_url, headers=ADMIN, json={**body, 'fragment_revision': 99})
    assert response.status == 409
    response = await test_client_light.post(insert_url, headers=ADMIN, json=body)
    assert response.status == 200, await response.text()
    result = (await response.json())['data']
    assert result['draft']['revision'] == 4
    block = next(block for block in result['draft']['definition']['blocks'] if block['id'] == result['inserted_block_ids'][0])
    target_asset = block['fields'][0]['help_attachments'][0]
    assert target_asset['asset_id'] not in {captured['asset_id'], source_asset['asset_id']}
    assert block['fields'][0]['process_mapping']['fact_key'] == 'other_summary'
    download = await test_client_light.get(target_asset['url'], headers=ADMIN)
    assert download.status == 200 and await download.read() == b'fragment content'
    listing = await test_client_light.get(BASE + '/fragments', headers=ADMIN)
    assert (await listing.json())['data']['total'] == 1

@pytest.mark.asyncio
async def test_upgraded_map_owned_v4_candidate_offering_can_publish(test_client_light, test_engine):
    from tests.test_request_scenario_v3_processing_api import configured
    identifier, definition, _, _ = await configured(test_engine, draft_offering=True)
    url = BASE + '/scenarios/' + identifier
    saved = await test_client_light.put(url + '/draft', headers=ADMIN, json={'revision': 1, 'definition': definition})
    assert saved.status == 200, await saved.text()
    response = await test_client_light.post(url + '/upgrade-v4', headers=ADMIN, json={'revision': 2})
    assert response.status == 200, await response.text()
    response = await test_client_light.post(url + '/publish-preview', headers=ADMIN, json={'revision': 3})
    assert response.status == 200, await response.text()
    preview = (await response.json())['data']
    assert preview['readiness']['can_publish'], preview['readiness']
    response = await test_client_light.post(url + '/publish', headers=ADMIN,
        json={'revision': 3, 'confirm': True, 'confirmation_token': preview['confirmation_token']})
    assert response.status == 200, await response.text()
