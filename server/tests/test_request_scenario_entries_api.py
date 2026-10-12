"""Isolated PostgreSQL entrance ACL, resume, snapshot and catalog integration."""
from copy import deepcopy
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.request_scenario_models import RequestStudioScenarioVersion, RequestStudioScenario
from tests.test_request_scenario_session_api import seed, BASE, OWNER

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


async def publish_snapshot(session, version_id, definition):
    """Fixture publication creates a new version; never mutate immutable JSON."""
    previous = await session.get(RequestStudioScenarioVersion, version_id)
    scenario = await session.get(RequestStudioScenario, previous.scenario_id)
    previous.state = 'retired'
    await session.flush()
    replacement = RequestStudioScenarioVersion(scenario_id=scenario.id, offering_full_code=scenario.offering_full_code,
        version=previous.version + 1, schema_version=1, definition=deepcopy(definition), content_hash='b' * 64,
        source_snapshot={}, published_by='test')
    session.add(replacement)
    await session.flush()
    scenario.published_version_id = replacement.id
    return replacement.id


@pytest.mark.asyncio
async def test_entry_category_cannot_be_archived_by_either_admin_path(test_client_light, test_engine):
    from tests.test_request_scenario_admin_api import ADMIN, BASE as ADMIN_BASE
    from app.db.request_scenario_models import RequestStudioCategory
    definition, version_id = await seed(test_engine, guided=True)
    async with async_sessionmaker(test_engine)() as session:
        category = RequestStudioCategory(service_code=definition['service_code'], slug='entry_only', title='Entry category',
            visibility='public', lifecycle_status='published', created_by='test', updated_by='test')
        session.add(category)
        await session.flush()
        identifier = category.id
        version_id = await publish_snapshot(session, version_id, {**definition, 'entry_points': [dict(key='paper', title='Paper jam', target_block_id='instruction', category_id=identifier)]})
        await session.commit()
    response = await test_client_light.delete(ADMIN_BASE + '/categories/' + identifier + '?revision=1', headers=ADMIN)
    assert response.status == 409, await response.text()
    response = await test_client_light.put(ADMIN_BASE + '/categories/' + identifier, headers=ADMIN, json={
        'service_code': definition['service_code'], 'slug': 'entry_only', 'title': 'Entry category',
        'visibility': 'public', 'lifecycle_status': 'archived', 'revision': 1})
    assert response.status == 409, await response.text()

    # An archived map cannot run or resume sessions, so it no longer binds the
    # navigation category even though historical definitions remain immutable.
    async with async_sessionmaker(test_engine)() as session:
        version = await session.get(RequestStudioScenarioVersion, version_id)
        scenario = await session.get(RequestStudioScenario, version.scenario_id)
        scenario.archived, scenario.enabled = True, False
        await session.commit()
    response = await test_client_light.delete(ADMIN_BASE + '/categories/' + identifier + '?revision=1', headers=ADMIN)
    assert response.status == 200, await response.text()


@pytest.mark.asyncio
async def test_published_entrances_acl_resume_context_and_version_pin(test_client_light, test_engine):
    definition, version_id = await seed(test_engine, guided=True)
    public = dict(key='paper', title='Paper jam', target_block_id='instruction',
                  visibility='public', enabled=True, reported_symptom='Reported paper jam', synonyms=['jam'])
    definition['entry_points'] = [public,
        {**public, 'key': 'hidden', 'visibility': 'internal'},
        {**public, 'key': 'disabled', 'enabled': False},
        {**public, 'key': 'missing_category', 'category_id': '00000000-0000-0000-0000-000000000001'}]
    async with async_sessionmaker(test_engine)() as session:
        version_id = await publish_snapshot(session, version_id, definition)
        await session.commit()
    body = {'offering_full_code': definition['offering_full_code']}
    for key in ('hidden', 'disabled', 'missing_category', 'unknown'):
        response = await test_client_light.post(BASE, headers=OWNER, json={**body, 'entry_point_key': key})
        assert response.status == 404, await response.text()
    catalog = await (await test_client_light.get('/api/service-catalog/current', headers=OWNER)).json()
    service = next(item for item in catalog['services'] if item['service_code'] == definition['service_code'])
    assert [item['entry_point_key'] for item in service['offerings'][0]['catalog_items']] == ['paper']
    response = await test_client_light.post(BASE, headers=OWNER, json={**body, 'entry_point_key': 'paper'})
    assert response.status == 200, await response.text()
    selected = (await response.json())['data']
    assert selected['block']['id'] == 'instruction'
    assert selected['entry_point']['reported_symptom'] == 'Reported paper jam'
    legacy = (await (await test_client_light.post(BASE, headers=OWNER, json=body)).json())['data']
    assert legacy['id'] != selected['id'] and legacy['entry_point'] is None
    resumed = (await (await test_client_light.post(BASE, headers=OWNER, json={**body, 'entry_point_key': 'paper'})).json())['data']
    assert resumed['id'] == selected['id']
    async with async_sessionmaker(test_engine)() as session:
        changed = deepcopy(definition)
        changed['entry_points'][0].update(target_block_id='questions', reported_symptom='New description')
        await publish_snapshot(session, version_id, changed)
        await session.commit()
    pinned = (await (await test_client_light.get(BASE + '/' + selected['id'], headers=OWNER)).json())['data']
    assert pinned['version_id'] == version_id and pinned['entry_point'] == selected['entry_point']


@pytest.mark.asyncio
async def test_specialized_route_cannot_bypass_required_canonical_fields(test_client_light, test_engine):
    from app.db.request_scenario_models import RequestStudioDraft
    from tests.test_request_scenario_publication_api import ready
    from tests.test_request_scenario_admin_api import ADMIN, BASE as ADMIN_BASE
    identifier, definition = await ready(test_engine)
    definition['entry_points'] = [dict(key='skip', title='Skip required page', target_block_id='review')]
    async with async_sessionmaker(test_engine)() as session:
        draft = await session.get(RequestStudioDraft, identifier)
        draft.definition = deepcopy(definition)
        await session.commit()
    response = await test_client_light.post(ADMIN_BASE + '/scenarios/' + identifier + '/publish-preview', headers=ADMIN, json={'revision': 1})
    assert response.status == 200, await response.text()
    data = (await response.json())['data']
    assert data['readiness']['can_publish'] is False
    assert any(issue['code'] == 'processing_invalid' for issue in data['readiness']['issues'])
    assert data['confirmation_token'] is None
